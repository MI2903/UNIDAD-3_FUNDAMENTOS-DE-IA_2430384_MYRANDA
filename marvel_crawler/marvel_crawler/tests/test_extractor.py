# -*- coding: utf-8 -*-
"""
test_extractor.py
-----------------
Pruebas SIN internet del extractor. Uso páginas HTML de ejemplo (carpeta
fixtures/) que tienen la misma estructura que Wikipedia, en sus dos
formatos (el nuevo y el viejo), para comprobar que saco bien cada dato.

Correr:   python -m pytest tests -v
   o:     python tests/test_extractor.py

Autora: Myranda Belén Infante Castillo  |  Matrícula: 2430384
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import extractor  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
W = "https://en.wikipedia.org/wiki/"


def leer(nombre):
    return (FIX / nombre).read_text(encoding="utf-8")


def test_pelicula_formato_nuevo():
    p = extractor.extraer_pelicula(leer("pelicula_nueva.html"), W + "Iron_Man_2")
    assert p["titulo"] == "Iron Man 2"
    assert p["anio"] == "2010"
    assert p["generos"] == ["Science Fiction", "Action", "Superhero"]
    assert p["generos_es"] == ["Ciencia ficción", "Acción", "Superhéroes"]
    assert p["es_marvel"] is True
    assert p["url"] == W + "Iron_Man_2"
    assert p["wikidata_id"] == "Q205028"
    # Resumen = Plot, sin las notitas [2]
    assert p["resumen"].startswith("In Russia, the media covers Tony Stark's")
    assert "[2]" not in p["resumen"] and "Six months later" in p["resumen"]
    # Reseña = Critical response (no Box office)
    assert p["resena"].startswith("The review aggregator Rotten Tomatoes")
    assert "grossed" not in p["resena"] and "[90]" not in p["resena"]
    assert "Roger Ebert" in p["resena"]
    assert p["descripcion"].startswith("Iron Man 2 is a 2010 American superhero")
    # Similares: solo títulos en cursiva, sin la propia, sin categorías
    assert p["urls_similares"] == [W + "Iron_Man_(2008_film)",
                                   W + "The_Incredible_Hulk_(film)",
                                   W + "Thor_(film)", W + "Iron_Man_3"]
    # URLs de géneros: solo las 2 categorías de género
    assert p["urls_generos"] == [W + "Category:2010_science_fiction_action_films",
                                 W + "Category:American_superhero_films"]


def test_pelicula_formato_viejo():
    p = extractor.extraer_pelicula(leer("pelicula_vieja.html"), W + "Blade_(1998_film)")
    assert p["titulo"] == "Blade"
    assert p["anio"] == "1998"
    assert p["generos"] == ["Superhero", "Vampire", "Black Comedy"]
    assert p["resumen"].startswith("In 1967")
    assert p["resena"].startswith("On Rotten Tomatoes")
    assert p["es_marvel"] is True          # por "blade (franchise)"


def test_no_peliculas():
    assert extractor.extraer_pelicula(leer("serie_tv.html"), W + "WandaVision") is None
    assert extractor.extraer_pelicula(leer("actor.html"), W + "RDJ") is None


def test_categoria():
    c = extractor.extraer_categoria(leer("categoria.html"))
    assert c["peliculas"] == [W + "Ant-Man_(film)", W + "Aquaman_(film)"]
    assert W + "Category:Spider-Man_films" in c["subcategorias"]
    assert c["siguiente"] == W + "Category:American_superhero_films?pagefrom=Hulk%20%28film%29"


def test_lista():
    assert extractor.extraer_lista(leer("lista.html")) == [
        W + "Howard_the_Duck_(film)", W + "Blade_(1998_film)", W + "Black_Panther_(film)"]


def test_generos_de_categoria():
    g = extractor.generos_de_categoria
    assert g("2019 science fiction action films") == [
        ("Science Fiction", "Ciencia ficción"), ("Action", "Acción")]
    assert g("Films set in New York City") == []
    assert g("Live-action films based on comics") == []
    assert g("American films") == []
    assert g("Comedy-drama films") == [("Comedy-drama", "Comedia dramática")]


if __name__ == "__main__":
    for nombre, funcion in list(globals().items()):
        if nombre.startswith("test_"):
            funcion()
            print("OK", nombre)
    print("Todas las pruebas pasaron.")
