# -*- coding: utf-8 -*-
"""
crawler.py   <-- ESTE ES EL QUE SE EJECUTA
----------
Web crawler de películas de Marvel. Sigue el diagrama del pizarrón:

     URL (http) ──► HTML ──► título, reseña/resumen, géneros ──► CSV
                     │
                     ├──► URLs de títulos similares ──► (vuelvo a empezar)
                     │
                     └──► URLs de los géneros ──► me listan otras URLs
                                                     └──► (vuelvo a empezar)

Cómo funciona, en mis palabras:
  1. Empiezo con páginas que SÍ son de Marvel (una lista de películas de
     Marvel y varias categorías como "Marvel Cinematic Universe films").
  2. Cada película que visito la leo, saco sus datos y la escribo al CSV.
  3. De esa misma página saco los enlaces a títulos similares y los enlaces
     a sus géneros, y los formo en una cola para visitarlos después.
  4. La cola tiene prioridades: primero Marvel, luego las similares y al
     final las que salen por género. Así el CSV queda "Marvel primero" y se
     completa con películas parecidas hasta llegar a 500–1000.
  5. Me detengo cuando llego al objetivo (700 por defecto).

Uso rápido (en la terminal de VS Code, con el entorno activado):
    python crawler.py                       # corre con 700 películas
    python crawler.py --objetivo 1000       # cambia la cantidad
    python crawler.py --probar "https://en.wikipedia.org/wiki/Iron_Man_2"
    python crawler.py --reiniciar           # borra el avance y empieza de cero

Autora: Myranda Belén Infante Castillo  |  Matrícula: 2430384
"""

import argparse
import csv
import logging
import shutil
import sys
import time
from datetime import datetime

import config
import extractor
from estado import PRIORIDAD, Estado
from red import BloqueoError, ClienteHTTP, SinInternetError, es_mismo_sitio

log = logging.getLogger("crawler")


# ===========================================================================
# Preparación
# ===========================================================================
def preparar_consola_y_log():
    """En Windows la consola a veces no muestra bien los acentos; con esto
    la obligo a usar UTF-8. Además todo lo que sale en pantalla también se
    guarda en datos/crawler.log por si necesito revisar algo después."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    config.CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    log.setLevel(logging.INFO)
    log.handlers.clear()
    formato = logging.Formatter("%(asctime)s | %(message)s", "%H:%M:%S")

    pantalla = logging.StreamHandler(sys.stdout)
    pantalla.setFormatter(formato)
    archivo = logging.FileHandler(config.ARCHIVO_LOG, encoding="utf-8")
    archivo.setFormatter(formato)
    log.addHandler(pantalla)
    log.addHandler(archivo)


def abrir_csv():
    """Abro el CSV en modo "agregar" para no borrar lo que ya llevaba.
    Uso utf-8-sig para que Excel en Windows muestre bien los acentos.
    Si el archivo es nuevo le escribo los encabezados."""
    nuevo = not config.ARCHIVO_CSV.exists() or config.ARCHIVO_CSV.stat().st_size == 0
    f = open(config.ARCHIVO_CSV, "a", encoding="utf-8-sig", newline="")
    escritor = csv.DictWriter(f, fieldnames=config.COLUMNAS_CSV,
                              quoting=csv.QUOTE_ALL)
    if nuevo:
        escritor.writeheader()
        f.flush()
    return f, escritor


def sembrar(estado):
    """Meto a la cola las páginas de inicio (todas de Marvel)."""
    for ruta in config.SEMILLA_LISTA_MARVEL:
        estado.agregar(extractor.normalizar_url(ruta), "lista",
                       PRIORIDAD["semilla_marvel"], marvel=True)
    for ruta in config.SEMILLA_CATEGORIAS_MARVEL:
        estado.agregar(extractor.normalizar_url(ruta), "categoria_marvel",
                       PRIORIDAD["semilla_marvel"], marvel=True)


# ===========================================================================
# Procesar cada tipo de página
# ===========================================================================
def procesar_lista(estado, html):
    """Lista de Marvel -> todas sus películas a la cola con prioridad alta."""
    urls = extractor.extraer_lista(html)
    nuevas = sum(estado.agregar(u, "pelicula", PRIORIDAD["pelicula_marvel"],
                                marvel=True) for u in urls)
    log.info("   Lista de Marvel: %d títulos encontrados (%d nuevos en cola).",
             len(urls), nuevas)


def procesar_categoria(estado, html, url, tipo, profundidad, paginas):
    """Página de categoría (de Marvel o de género) -> sus películas a la cola.
    Esta es la parte de "URL de los géneros que me va a listar otras URL"."""
    datos = extractor.extraer_categoria(html)
    es_marvel = tipo == "categoria_marvel"
    prioridad_peli = PRIORIDAD["pelicula_marvel"] if es_marvel \
        else PRIORIDAD["pelicula_de_genero"]

    nuevas = sum(estado.agregar(u, "pelicula", prioridad_peli, marvel=es_marvel)
                 for u in datos["peliculas"])
    log.info("   Categoría '%s': %d enlaces (%d nuevos en cola).",
             extractor.nombre_de_categoria(url), len(datos["peliculas"]), nuevas)

    # Subcategorías: solo las sigo en Marvel (ej. "Spider-Man films").
    # En géneros NO, porque se volvería infinito.
    if es_marvel and profundidad < config.PROFUNDIDAD_SUBCATEGORIAS_MARVEL:
        for sub in datos["subcategorias"]:
            nombre = extractor.nombre_de_categoria(sub).lower()
            if "film" in nombre and not any(
                    x in nombre for x in ("character", "actor", "poster",
                                          "soundtrack", "video game",
                                          "television", "crew", "image")):
                estado.agregar(sub, "categoria_marvel", PRIORIDAD["semilla_marvel"],
                               marvel=True, profundidad=profundidad + 1)

    # Siguiente página de la categoría (cada página trae máximo 200).
    if datos["siguiente"]:
        limite = config.MAX_PAGINAS_POR_CATEGORIA_MARVEL if es_marvel \
            else config.MAX_PAGINAS_POR_CATEGORIA_GENERO
        prioridad = PRIORIDAD["semilla_marvel"] if es_marvel \
            else PRIORIDAD["categoria_genero"]
        if paginas + 1 < limite:
            estado.agregar(datos["siguiente"], tipo, prioridad, es_marvel,
                           profundidad, paginas + 1)
        elif not es_marvel:
            # No la visito ahorita, pero la guardo por si me faltan películas.
            estado.reserva.append((prioridad, 0, datos["siguiente"], tipo,
                                   False, profundidad, paginas + 1))


def pelicula_completa(peli):
    """Reviso que la película tenga lo que pidió el doctor."""
    if not peli["titulo"] or not peli["resumen"] or not peli["generos"]:
        return False
    if config.RESENA_OBLIGATORIA_NO_MARVEL and not peli["es_marvel"] \
            and not peli["resena"]:
        return False
    return True


def procesar_pelicula(estado, escritor, archivo_csv, html, url, marvel_hint, origen):
    """Película -> extraigo datos, la escribo en el CSV y meto a la cola sus
    títulos similares y sus géneros. Regreso True si la guardé."""
    peli = extractor.extraer_pelicula(html, url)
    if peli is None:
        estado.rechazadas += 1
        return False                       # no era película (actor, cómic, serie...)

    # Puede que haya llegado por una redirección a una que ya tenía.
    if peli["url"] in estado.guardadas:
        return False
    estado.visitados.add(peli["url"])

    peli["es_marvel"] = peli["es_marvel"] or marvel_hint

    # 1) Títulos similares -> a la cola (vuelta al inicio del diagrama)
    prioridad_sim = PRIORIDAD["similar_de_marvel"] if peli["es_marvel"] \
        else PRIORIDAD["similar"]
    for u in peli["urls_similares"]:
        if es_mismo_sitio(u):
            estado.agregar(u, "pelicula", prioridad_sim)

    # 2) URLs de géneros -> a la cola (me van a listar más URLs)
    for u in peli["urls_generos"]:
        estado.agregar(u, "categoria_genero", PRIORIDAD["categoria_genero"])

    if not pelicula_completa(peli):
        estado.rechazadas += 1
        log.info("   (incompleta, no la guardo) %s", peli["titulo"])
        return False

    # 3) Escribo la fila en el CSV
    estado.total_guardadas += 1
    escritor.writerow({
        "id": estado.total_guardadas,
        "titulo": peli["titulo"],
        "anio": peli["anio"],
        "generos": "|".join(peli["generos"]),
        "generos_es": "|".join(peli["generos_es"]),
        "resumen": peli["resumen"],
        "resena": peli["resena"],
        "descripcion": peli["descripcion"],
        "es_marvel": 1 if peli["es_marvel"] else 0,
        "url": peli["url"],
        "urls_similares": "|".join(peli["urls_similares"][:config.MAX_SIMILARES_EN_CSV]),
        "urls_generos": "|".join(peli["urls_generos"]),
        "wikidata_id": peli["wikidata_id"],
        "origen": origen,
    })
    archivo_csv.flush()      # lo mando al disco ya, por si se va la luz
    estado.guardadas.add(peli["url"])
    return peli


# ===========================================================================
# Ciclo principal
# ===========================================================================
def origen_de(prioridad):
    if prioridad <= PRIORIDAD["pelicula_marvel"]:
        return "semilla_marvel"
    if prioridad <= PRIORIDAD["similar"]:
        return "similar"
    return "genero"


def correr(objetivo):
    estado = Estado()
    reanudado = estado.cargar()
    if reanudado:
        log.info("Reanudando: ya llevo %d películas en el CSV y %d URLs en cola.",
                 estado.total_guardadas, estado.pendientes())
    else:
        if estado.total_guardadas:
            log.info("Hay %d películas en el CSV pero no hay estado; "
                     "empiezo la cola de nuevo sin repetirlas.",
                     estado.total_guardadas)
        sembrar(estado)

    if estado.total_guardadas >= objetivo:
        log.info("Ya tengo %d películas (objetivo %d). No hay nada que hacer. "
                 "Usa --objetivo con un número mayor o --reiniciar.",
                 estado.total_guardadas, objetivo)
        return

    cliente = ClienteHTTP()
    archivo_csv, escritor = abrir_csv()
    inicio = time.time()
    paginas = 0
    log.info("Objetivo: %d películas. ¡Empezamos! (Ctrl+C para pausar)", objetivo)

    try:
        while estado.total_guardadas < objetivo:
            item = estado.siguiente()
            if item is None:
                log.warning("Se acabaron las URLs antes de llegar al objetivo. "
                            "Sube MAX_PAGINAS_POR_CATEGORIA_GENERO en config.py "
                            "y vuelve a correr (se reanuda).")
                break
            prioridad, _, url, tipo, marvel, profundidad, pags = item

            html, url_final = cliente.obtener_html(url)
            estado.visitados.add(url)
            paginas += 1
            if html is None:
                continue

            if tipo == "lista":
                procesar_lista(estado, html)
            elif tipo in ("categoria_marvel", "categoria_genero"):
                procesar_categoria(estado, html, url, tipo, profundidad, pags)
            else:
                peli = procesar_pelicula(estado, escritor, archivo_csv, html,
                                         url_final or url, marvel, origen_de(prioridad))
                if peli:
                    etiqueta = "MARVEL" if peli["es_marvel"] else origen_de(prioridad)
                    log.info("[%d/%d] %s (%s) | %s | %s",
                             estado.total_guardadas, objetivo, peli["titulo"],
                             peli["anio"] or "s/f", ", ".join(peli["generos"][:4]),
                             etiqueta)

            if paginas % config.GUARDAR_ESTADO_CADA == 0:
                estado.guardar()
                minutos = (time.time() - inicio) / 60
                log.info("   -- avance guardado | %d páginas en %.1f min | "
                         "cola: %d --", paginas, minutos, estado.pendientes())

    except KeyboardInterrupt:
        log.info("Pausado por ti (Ctrl+C). Guardo el avance...")
    except (BloqueoError, SinInternetError) as e:
        log.error("Me detuve: %s", e)
    finally:
        estado.guardar()
        archivo_csv.close()
        cliente.cerrar()

    minutos = (time.time() - inicio) / 60
    log.info("=" * 70)
    log.info("Películas en el CSV: %d | páginas pedidas: %d | descartadas: %d | "
             "tiempo: %.1f min", estado.total_guardadas, cliente.peticiones_hechas,
             estado.rechazadas, minutos)
    log.info("CSV: %s", config.ARCHIVO_CSV)
    if estado.total_guardadas < objetivo:
        log.info("Aún no llego al objetivo; vuelve a correr el mismo comando "
                 "y continúa donde se quedó.")
    else:
        log.info("¡Listo! Revisa el CSV con:  python validar_csv.py")


def probar(url):
    """Modo prueba: descargo UNA sola página y muestro lo que extraje, sin
    tocar el CSV. Sirve para comprobar que todo jala antes de la corrida larga."""
    cliente = ClienteHTTP()
    html, url_final = cliente.obtener_html(extractor.normalizar_url(url))
    cliente.cerrar()
    if html is None:
        log.error("No pude descargar la página.")
        return
    # Guardo el HTML que descargué por si algo sale vacío y lo quiero revisar.
    copia = config.CARPETA_DATOS / "prueba.html"
    copia.write_text(html, encoding="utf-8")
    log.info("(HTML guardado en %s)", copia)
    peli = extractor.extraer_pelicula(html, url_final)
    if peli is None:
        log.info("Esa página NO es de una película.")
        return
    for campo, valor in peli.items():
        if isinstance(valor, list):
            log.info("%-15s (%d) %s", campo, len(valor), " | ".join(valor[:6]))
        else:
            texto = str(valor)
            log.info("%-15s %s", campo, texto[:300] + ("…" if len(texto) > 300 else ""))
    log.info("¿Completa para el CSV?: %s", "SÍ" if pelicula_completa(peli) else "NO")


def reiniciar():
    """Muevo el CSV y el estado a una copia de respaldo (no los borro de a
    tiro, por si me equivoqué)."""
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    for archivo in (config.ARCHIVO_CSV, config.ARCHIVO_ESTADO):
        if archivo.exists():
            respaldo = archivo.with_name(f"{archivo.stem}_respaldo_{sello}{archivo.suffix}")
            shutil.move(str(archivo), str(respaldo))
            log.info("Respaldo: %s", respaldo.name)


def main():
    preparar_consola_y_log()
    parser = argparse.ArgumentParser(
        description="Web crawler de películas de Marvel (Wikipedia) -> CSV")
    parser.add_argument("--objetivo", type=int, default=config.OBJETIVO_PELICULAS,
                        help="cuántas películas quiero en el CSV (500 a 1000)")
    parser.add_argument("--probar", metavar="URL",
                        help="descarga una sola página y muestra lo que extrae")
    parser.add_argument("--reiniciar", action="store_true",
                        help="respalda el CSV y el avance y empieza de cero")
    args = parser.parse_args()

    if args.probar:
        probar(args.probar)
        return
    if args.reiniciar:
        reiniciar()
    if not (config.MINIMO_PELICULAS <= args.objetivo <= config.MAXIMO_PELICULAS):
        log.warning("Ojo: el doctor pidió entre %d y %d películas y pusiste %d.",
                    config.MINIMO_PELICULAS, config.MAXIMO_PELICULAS, args.objetivo)
    if config.CORREO_CONTACTO.startswith("tu_correo"):
        log.warning("Aún no pones tu correo en config.py (CORREO_CONTACTO). "
                    "Funciona igual, pero es mejor ponerlo para que Wikipedia "
                    "no te confunda con un bot anónimo.")

    correr(args.objetivo)


if __name__ == "__main__":
    main()