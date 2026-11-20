# -*- coding: utf-8 -*-
"""
config.py
---------
Aquí junté TODOS los valores que se pueden mover del crawler, para no andar
buscando números perdidos dentro del código. Si quiero cambiar cuántas
películas sacar, qué tan rápido va o dónde guarda, lo cambio aquí y listo.

Autora: Myranda Belén Infante Castillo  |  Matrícula: 2430384
Materia: (proyecto del recomendador)  |  UPV - ITIID 7.º cuatrimestre
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# 1) ¿De dónde saco los datos?
# ---------------------------------------------------------------------------
# Decidí usar Wikipedia en inglés y NO páginas oficiales (marvel.com, Disney)
# ni sitios como IMDb o TMDB, porque esos prohíben el scraping y bloquean la IP.
# Wikipedia sí deja que entren crawlers siempre y cuando:
#   - te identifiques con un User-Agent que diga quién eres y un contacto,
#   - no hagas peticiones demasiado rápido.
# Además en inglés hay muchísimas más películas con sección de crítica.
SITIO_BASE = "https://en.wikipedia.org"

# >>> IMPORTANTE: cambia este correo por el tuyo de la escuela. <<<
# Wikipedia pide un contacto en el User-Agent; si lo dejas genérico
# es más probable que te frenen.
CORREO_CONTACTO = "tu_correo@upv.edu.mx"

USER_AGENT = (
    "MarvelCrawlerUPV/1.0 (proyecto escolar de recomendador; "
    f"contacto: {CORREO_CONTACTO}) python-requests"
)

# ---------------------------------------------------------------------------
# 2) ¿Cuántas películas quiero?
# ---------------------------------------------------------------------------
# El doctor pidió entre 500 y 1000. Dejo 700 por defecto para quedar
# cómodos dentro del rango (se puede cambiar con --objetivo en la terminal).
OBJETIVO_PELICULAS = 700
MINIMO_PELICULAS = 500
MAXIMO_PELICULAS = 1000

# ---------------------------------------------------------------------------
# 3) Velocidad (para que no me bloqueen y no se trabe la laptop)
# ---------------------------------------------------------------------------
# Entre una petición y otra espero un tiempo al azar entre estos dos valores.
# Con 1–2.5 s salen más o menos 700 películas en unos 30–40 minutos.
ESPERA_MINIMA = 1.0
ESPERA_MAXIMA = 2.5

# Tiempo máximo para conectar / para leer la respuesta (segundos).
TIMEOUT = (10, 30)

# Cuántas veces reintento una página si falla la red o el servidor.
MAX_REINTENTOS = 5

# Si se cae el internet (o me cambio de red), cuánto tiempo espero
# a que regrese antes de guardar todo y salirme (en segundos).
ESPERA_MAXIMA_SIN_INTERNET = 30 * 60   # 30 minutos

# ---------------------------------------------------------------------------
# 4) Límites del recorrido (para que la cola no crezca sin control)
# ---------------------------------------------------------------------------
# Cuántas páginas de una categoría de GÉNERO leo como máximo
# (cada página de categoría trae hasta 200 enlaces).
MAX_PAGINAS_POR_CATEGORIA_GENERO = 2

# En las categorías de Marvel sí leo todas las páginas.
MAX_PAGINAS_POR_CATEGORIA_MARVEL = 10

# Qué tan profundo me meto en subcategorías de Marvel
# (ej. "Films based on Marvel Comics" -> "Spider-Man films").
PROFUNDIDAD_SUBCATEGORIAS_MARVEL = 2

# Cuántos títulos similares guardo en el CSV por película.
MAX_SIMILARES_EN_CSV = 25

# Límite de caracteres por campo de texto (para que el CSV no pese de más
# y Excel no se vuelva loco con celdas gigantes).
MAX_CARACTERES_RESUMEN = 2500
MAX_CARACTERES_RESENA = 2500
MAX_CARACTERES_DESCRIPCION = 1200

# ¿Qué campos son obligatorios para guardar una película?
# - Título, resumen y géneros SIEMPRE.
# - La reseña (crítica) es obligatoria para las que NO son de Marvel
#   (como hay muchísimas, me puedo dar el lujo de escoger solo las completas).
# - Para las de Marvel la guardo aunque no tenga sección de crítica,
#   porque el chiste del dataset es que estén las de Marvel.
RESENA_OBLIGATORIA_NO_MARVEL = True

# ---------------------------------------------------------------------------
# 5) Semillas: por dónde empieza el crawler
# ---------------------------------------------------------------------------
# Primero entra a puras páginas de Marvel (lista y categorías). De ahí
# salta a "títulos similares" y luego a las URLs de los géneros,
# tal como lo dibujó el doctor en el pizarrón.
SEMILLA_LISTA_MARVEL = [
    "/wiki/List_of_films_based_on_Marvel_Comics_publications",
    "/wiki/List_of_Marvel_Cinematic_Universe_films",
]

SEMILLA_CATEGORIAS_MARVEL = [
    "/wiki/Category:Marvel_Cinematic_Universe_films",
    "/wiki/Category:Films_based_on_Marvel_Comics",
    "/wiki/Category:Marvel_Studios_films",
    "/wiki/Category:Sony%27s_Spider-Man_Universe_films",
    "/wiki/Category:X-Men_films",
    "/wiki/Category:Spider-Man_films",
    "/wiki/Category:Fantastic_Four_films",
    "/wiki/Category:Marvel_Animation_films",
]

# Palabras que, si aparecen en las categorías de una película,
# me dicen que es de Marvel.
PALABRAS_MARVEL = [
    "marvel", "spider-man", "x-men", "avengers", "fantastic four",
    "deadpool", "wolverine", "blade (franchise)", "ghost rider",
    "punisher", "venom", "iron man", "captain america", "thor (",
    "guardians of the galaxy", "black panther", "ant-man", "hulk",
    "doctor strange", "daredevil",
]

# ---------------------------------------------------------------------------
# 6) Archivos de salida
# ---------------------------------------------------------------------------
CARPETA_PROYECTO = Path(__file__).resolve().parent
CARPETA_DATOS = CARPETA_PROYECTO / "datos"

ARCHIVO_CSV = CARPETA_DATOS / "peliculas_marvel.csv"
ARCHIVO_ESTADO = CARPETA_DATOS / "estado_crawler.json"   # para reanudar
ARCHIVO_LOG = CARPETA_DATOS / "crawler.log"

# Cada cuántas páginas guardo el avance (checkpoint).
GUARDAR_ESTADO_CADA = 10

# Columnas del CSV (en este orden).
COLUMNAS_CSV = [
    "id",               # número consecutivo
    "titulo",           # nombre de la película
    "anio",             # año de estreno
    "generos",          # géneros en inglés separados por |
    "generos_es",       # los mismos géneros en español
    "resumen",          # de qué trata (sección Plot / Synopsis)
    "resena",           # crítica (sección Critical response / Reception)
    "descripcion",      # primer párrafo de la página (resumen corto)
    "es_marvel",        # 1 si es de Marvel, 0 si llegó por similitud o género
    "url",              # URL de la página de la película
    "urls_similares",   # URLs de títulos similares separadas por |
    "urls_generos",     # URLs de las categorías de género separadas por |
    "wikidata_id",      # identificador único (sirve para cruzar datasets)
    "origen",           # cómo llegó el crawler: semilla_marvel / similar / genero
]
