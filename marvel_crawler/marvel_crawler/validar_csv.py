# -*- coding: utf-8 -*-
"""
validar_csv.py
--------------
Lo corro al final para revisar que el CSV cumpla con lo que pidió el doctor
ANTES de mandárselo a mi compañero:
  - que tenga entre 500 y 1000 películas,
  - que no haya películas repetidas,
  - que título, resumen, géneros y reseña estén llenos,
  - cuántas son de Marvel y qué géneros salieron más.

Solo uso librerías que ya trae Python (sin pandas) para no cargar la RAM.

Uso:   python validar_csv.py
       python validar_csv.py datos/otro_archivo.csv

Autora: Myranda Belén Infante Castillo  |  Matrícula: 2430384
"""

import csv
import sys
from collections import Counter
from pathlib import Path

import config


def main():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else config.ARCHIVO_CSV
    if not ruta.exists():
        print(f"No encontré el archivo {ruta}. ¿Ya corriste crawler.py?")
        sys.exit(1)

    with open(ruta, encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))

    total = len(filas)
    print("=" * 60)
    print(f" Revisión de {ruta.name}")
    print("=" * 60)

    # 1) Columnas
    faltan = [c for c in config.COLUMNAS_CSV if filas and c not in filas[0]]
    print(f"Columnas: {'OK' if not faltan else 'FALTAN ' + ', '.join(faltan)}")

    # 2) Cantidad
    en_rango = config.MINIMO_PELICULAS <= total <= config.MAXIMO_PELICULAS
    print(f"Películas: {total}  ->  "
          f"{'OK (dentro de 500–1000)' if en_rango else 'FUERA DEL RANGO 500–1000'}")

    # 3) Repetidas (por URL y por título+año)
    urls = Counter(f["url"] for f in filas)
    rep_url = [u for u, n in urls.items() if n > 1]
    tit = Counter((f["titulo"].lower(), f["anio"]) for f in filas)
    rep_tit = [t for t, n in tit.items() if n > 1]
    print(f"Repetidas por URL: {len(rep_url)}  |  por título+año: {len(rep_tit)}")
    for t in rep_tit[:5]:
        print(f"   - {t[0]} ({t[1]})")

    # 4) Campos vacíos
    print("\nCampos vacíos:")
    for campo in ("titulo", "anio", "generos", "resumen", "resena", "descripcion"):
        vacios = sum(1 for f in filas if not f[campo].strip())
        marca = "OK" if vacios == 0 else f"{vacios} vacíos"
        print(f"   {campo:<12} {marca}")
    sin_resena_marvel = sum(1 for f in filas
                            if f["es_marvel"] == "1" and not f["resena"].strip())
    if sin_resena_marvel:
        print(f"   (de las reseñas vacías, {sin_resena_marvel} son de Marvel: "
              "Wikipedia no tiene sección de crítica para esas)")

    # 5) Marvel y origen
    marvel = sum(1 for f in filas if f["es_marvel"] == "1")
    print(f"\nDe Marvel: {marvel}  |  Otras (similares o por género): {total - marvel}")
    print("Origen:", dict(Counter(f["origen"] for f in filas)))

    # 6) Géneros más comunes
    generos = Counter(g for f in filas for g in f["generos"].split("|") if g)
    print("\nTop 12 géneros:")
    for g, n in generos.most_common(12):
        print(f"   {g:<18} {n}")

    # 7) Promedio de largo de textos
    if total:
        prom_res = sum(len(f["resumen"]) for f in filas) / total
        prom_rev = sum(len(f["resena"]) for f in filas) / total
        print(f"\nLargo promedio -> resumen: {prom_res:.0f} caracteres | "
              f"reseña: {prom_rev:.0f} caracteres")

    print("=" * 60)
    ok = en_rango and not rep_url and not faltan
    print("RESULTADO:", "LISTO PARA ENTREGAR" if ok else "REVISAR LO DE ARRIBA")


if __name__ == "__main__":
    main()
