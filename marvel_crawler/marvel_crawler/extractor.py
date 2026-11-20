# -*- coding: utf-8 -*-
"""
extractor.py
------------
Aquí está la parte de "leer" el HTML (la flecha HTML -> datos del pizarrón).
Recibe el HTML que ya descargó red.py y saca:

  1. De una PELÍCULA:  título, año, géneros, resumen (Plot), reseña (crítica),
                       descripción corta, URLs de títulos similares y
                       URLs de las categorías de género.
  2. De una CATEGORÍA (página de género o de Marvel): las URLs de películas
                       que lista, sus subcategorías y la "siguiente página".
  3. De una LISTA (ej. "List of films based on Marvel Comics"): las URLs
                       de las películas que aparecen en las tablas.

No hace ninguna petición a internet; solo lee texto. Por eso lo puedo
probar sin conexión con los archivos de la carpeta tests/.

Autora: Myranda Belén Infante Castillo  |  Matrícula: 2430384
"""

import re
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

from bs4 import BeautifulSoup

import config

# Uso lxml porque es mucho más rápido y gasta menos memoria que el parser
# que trae Python. Si por algo no está instalado, uso el normal.
try:
    import lxml  # noqa: F401
    PARSER = "lxml"
except ImportError:
    PARSER = "html.parser"


# ===========================================================================
# Diccionario de géneros
# ===========================================================================
# Wikipedia no tiene un campo "género" como tal; los géneros vienen en las
# CATEGORÍAS de la página, por ejemplo:
#     "2019 science fiction action films"  -> Science Fiction, Action
#     "American superhero films"           -> Superhero
# Así que busco estas palabras dentro del nombre de cada categoría.
# Formato: (palabra a buscar, nombre en inglés, nombre en español)
# OJO: van de la más larga a la más corta para que "black comedy" no se
# cuente también como "comedy".
GENEROS = [
    ("science fiction", "Science Fiction", "Ciencia ficción"),
    ("post-apocalyptic", "Post-apocalyptic", "Postapocalíptico"),
    ("coming-of-age", "Coming-of-age", "Crecimiento personal"),
    ("comedy-drama", "Comedy-drama", "Comedia dramática"),
    ("black comedy", "Black Comedy", "Comedia negra"),
    ("dark fantasy", "Dark Fantasy", "Fantasía oscura"),
    ("martial arts", "Martial Arts", "Artes marciales"),
    ("psychological", "Psychological", "Psicológico"),
    ("supernatural", "Supernatural", "Sobrenatural"),
    ("biographical", "Biographical", "Biográfico"),
    ("documentary", "Documentary", "Documental"),
    ("historical", "Historical", "Histórico"),
    ("superhero", "Superhero", "Superhéroes"),
    ("adventure", "Adventure", "Aventura"),
    ("dystopian", "Dystopian", "Distopía"),
    ("cyberpunk", "Cyberpunk", "Cyberpunk"),
    ("christmas", "Christmas", "Navideño"),
    ("political", "Political", "Político"),
    ("satirical", "Satire", "Sátira"),
    ("animated", "Animation", "Animación"),
    ("thriller", "Thriller", "Suspenso"),
    ("disaster", "Disaster", "Desastres"),
    ("neo-noir", "Neo-noir", "Neo-noir"),
    ("romantic", "Romance", "Romance"),
    ("romance", "Romance", "Romance"),
    ("mystery", "Mystery", "Misterio"),
    ("fantasy", "Fantasy", "Fantasía"),
    ("musical", "Musical", "Musical"),
    ("vampire", "Vampire", "Vampiros"),
    ("monster", "Monster", "Monstruos"),
    ("western", "Western", "Western"),
    ("slasher", "Slasher", "Slasher"),
    ("parody", "Parody", "Parodia"),
    ("sports", "Sports", "Deportes"),
    ("action", "Action", "Acción"),
    ("comedy", "Comedy", "Comedia"),
    ("horror", "Horror", "Terror"),
    ("family", "Family", "Familiar"),
    ("zombie", "Zombie", "Zombis"),
    ("drama", "Drama", "Drama"),
    ("crime", "Crime", "Crimen"),
    ("heist", "Heist", "Atracos"),
    ("buddy", "Buddy", "Compañeros"),
    ("teen", "Teen", "Adolescentes"),
    ("spy", "Spy", "Espionaje"),
    ("war", "War", "Bélica"),
]

# Si la categoría tiene alguna de estas frases, NO es de género
# (ej. "Films set in New York City", "Films scored by Alan Silvestri").
FRASES_QUE_NO_SON_GENERO = (
    " about ", " set in ", " shot in ", " based on ", " by ", " directed",
    " produced", " scored", " featuring ", " with ", " using ", " from ",
)

# Precompilo las expresiones regulares una sola vez (más rápido).
# Los "lookaround" evitan que "action" haga match dentro de "live-action".
_REGEX_GENEROS = [
    (re.compile(r"(?<![\w-])" + re.escape(clave) + r"(?![\w-])"), en, es)
    for clave, en, es in GENEROS
]

TITULOS_RESUMEN = ("plot", "synopsis", "premise", "story", "summary")
TITULOS_SIMILARES = ("see also",)


# ===========================================================================
# Utilidades pequeñas
# ===========================================================================
def ruta_wiki(href):
    """Wikipedia escribe los enlaces de varias formas según la versión de su
    HTML. Las convierto todas a la forma /wiki/Titulo:
        /wiki/Iron_Man_3                       (formato clásico)
        ./Iron_Man_3                           (formato nuevo "Parsoid")
        //en.wikipedia.org/wiki/Iron_Man_3
        https://en.wikipedia.org/wiki/Iron_Man_3
    Regreso None si no es un enlace a una página de Wikipedia."""
    if not href:
        return None
    href = href.strip()
    if href.startswith("./"):
        return "/wiki/" + href[2:]
    if href.startswith("/wiki/"):
        return href
    partes = urlparse(urljoin(config.SITIO_BASE, href))
    if partes.netloc == urlparse(config.SITIO_BASE).netloc \
            and partes.path.startswith("/wiki/"):
        ruta = partes.path
        return ruta + ("?" + partes.query if partes.query else "")
    return None


def normalizar_url(href):
    """Convierto cualquier enlace en una URL completa y "limpia":
    - le pego el dominio si viene relativo (/wiki/...),
    - le quito el #fragmento,
    - decodifico los %XX para que la misma página no cuente dos veces.
    """
    href = ruta_wiki(href) or href
    absoluta = urljoin(config.SITIO_BASE, href)
    partes = urlparse(absoluta)
    ruta = unquote(partes.path).replace(" ", "_")
    url = f"{partes.scheme}://{partes.netloc}{ruta}"
    if partes.query:
        url += "?" + partes.query
    return url


def es_articulo(href):
    """True si el enlace es un artículo normal de Wikipedia (no categoría,
    no archivo, no plantilla, no página especial, etc.)."""
    ruta = ruta_wiki(href)
    if not ruta:
        return False
    nombre = unquote(ruta[len("/wiki/"):]).split("#")[0].split("?")[0]
    if not nombre or ":" in nombre or nombre == "Main_Page":
        return False
    return True


def limpiar_texto(texto):
    """Quito espacios dobles, saltos de línea y espacios antes de signos."""
    texto = re.sub(r"\s+", " ", texto or "").strip()
    texto = re.sub(r"\s+([,.;:!?)])", r"\1", texto)
    texto = re.sub(r"\(\s+", "(", texto)
    return texto


def recortar(texto, maximo):
    """Si el texto es muy largo lo corto en la última palabra completa."""
    if len(texto) <= maximo:
        return texto
    corte = texto[:maximo].rsplit(" ", 1)[0]
    return corte.rstrip(",;:") + "…"


def _quitar_basura(raiz):
    """Borro del HTML lo que estorba en el texto: las notitas [1][2] de las
    referencias, los botones de [editar] y los estilos."""
    for basura in raiz.select(
        "sup.reference, sup.noprint, span.mw-editsection, style, "
        "script, .mw-ref, span.mw-cite-backlink, .reference"
    ):
        basura.decompose()


def _nivel_de_encabezado(tag):
    """Si el elemento es un título de sección regreso (nivel, texto).
    Wikipedia tiene dos formatos de títulos y soporto los dos:
      Nuevo:  <div class="mw-heading mw-heading2"><h2 id="Plot">Plot</h2></div>
      Viejo:  <h2><span class="mw-headline" id="Plot">Plot</span></h2>
    """
    if tag.name in ("h2", "h3", "h4", "h5", "h6"):
        return int(tag.name[1]), limpiar_texto(tag.get_text(" "))
    if tag.name == "div" and "mw-heading" in (tag.get("class") or []):
        h = tag.find(["h2", "h3", "h4", "h5", "h6"])
        if h:
            return int(h.name[1]), limpiar_texto(h.get_text(" "))
    return None


def _hijos_planos(raiz):
    """En el formato nuevo de Wikipedia cada parte de la página viene
    envuelta en <section>...</section>. Me meto dentro de esas cajas para
    que quede una sola fila de elementos, igual que en el formato viejo."""
    for hijo in raiz.find_all(recursive=False):
        if hijo.name == "section":
            yield from _hijos_planos(hijo)
        else:
            yield hijo


def _dividir_en_secciones(raiz):
    """Recorro el contenido de arriba a abajo y lo parto en secciones.
    Regreso:
      intro     -> lista de elementos antes del primer título (la "entrada")
      secciones -> lista de [nivel, titulo, [elementos]]
    """
    intro, secciones, actual = [], [], None
    for hijo in _hijos_planos(raiz):
        enc = _nivel_de_encabezado(hijo)
        if enc:
            actual = [enc[0], enc[1], []]
            secciones.append(actual)
        elif actual is None:
            intro.append(hijo)
        else:
            actual[2].append(hijo)
    return intro, secciones


def _elementos_de_seccion(secciones, condicion):
    """Busco la PRIMERA sección cuyo título cumpla la condición y regreso sus
    elementos, incluyendo los de sus subsecciones (las de nivel más bajo)."""
    for i, (nivel, titulo, elementos) in enumerate(secciones):
        if condicion(titulo.lower()):
            todos = list(elementos)
            for nivel2, _t, elementos2 in secciones[i + 1:]:
                if nivel2 <= nivel:
                    break
                todos.extend(elementos2)
            return todos
    return []


def _parrafos(elementos, max_parrafos=None):
    """De una lista de elementos me quedo con el texto de los <p>."""
    textos = []
    for el in elementos:
        if el.name != "p":
            continue
        # get_text() sin separador: así "Tony <a>Stark</a>'s" queda
        # "Tony Stark's" y no "Tony Stark 's".
        t = limpiar_texto(el.get_text())
        if len(t) > 20:                 # me salto párrafos vacíos o de 1 palabra
            textos.append(t)
        if max_parrafos and len(textos) >= max_parrafos:
            break
    return " ".join(textos)


def _enlaces_de_titulos(contenedores):
    """De varios bloques HTML saco los enlaces que están en cursiva <i>.
    Truco: en Wikipedia los títulos de películas, series y cómics SIEMPRE
    van en cursiva, así que eso me ayuda a separar las películas de los
    enlaces a actores, directores, ciudades, etc."""
    urls = []
    for cont in contenedores:
        for a in cont.find_all("a", href=True):
            if not es_articulo(a["href"]):
                continue
            if a.find_parent("i") is None and a.find("i") is None:
                continue
            urls.append(normalizar_url(a["href"]))
    return urls


def _sin_repetir(lista):
    """Quito duplicados sin cambiar el orden."""
    vistos, salida = set(), []
    for x in lista:
        if x not in vistos:
            vistos.add(x)
            salida.append(x)
    return salida


# ===========================================================================
# Géneros
# ===========================================================================
def generos_de_categoria(nombre_categoria):
    """Regreso la lista de (genero_en, genero_es) que hay en el nombre de una
    categoría. Lista vacía si la categoría no es de género."""
    nombre = " " + nombre_categoria.lower().strip() + " "
    # Solo las que terminan en "films" y no empiezan con "Films ..."
    # ("Films about...", "Films set in..." son temas, no géneros).
    if not nombre.rstrip().endswith(" films") or nombre.strip().startswith("films "):
        return []
    if any(frase in nombre for frase in FRASES_QUE_NO_SON_GENERO):
        return []
    encontrados = []
    for regex, en, es in _REGEX_GENEROS:
        if regex.search(nombre):
            encontrados.append((en, es))
            nombre = regex.sub(" | ", nombre)   # lo tacho para no contarlo 2 veces
    return encontrados


# ===========================================================================
# 1) Página de PELÍCULA
# ===========================================================================
def _etiquetas_infobox(infobox):
    """Regreso un diccionario {etiqueta: texto} del cuadro gris de la derecha
    (infobox): "Directed by", "Release date", "Running time", etc."""
    datos = {}
    if infobox is None:
        return datos
    for fila in infobox.find_all("tr"):
        th = fila.find("th", class_="infobox-label") or fila.find("th")
        td = fila.find("td", class_="infobox-data") or fila.find("td")
        if th and td:
            datos[limpiar_texto(th.get_text(" "))] = limpiar_texto(td.get_text(" "))
    return datos


def _raiz_contenido(soup):
    """Busco la caja donde está el texto del artículo. A veces hay varias
    con la clase mw-parser-output (avisos, indicadores), así que me quedo
    con la que tiene más párrafos."""
    candidatos = soup.select("#mw-content-text .mw-parser-output") \
        or soup.select(".mw-parser-output") \
        or soup.select("#mw-content-text") or [soup.body or soup]
    return max(candidatos, key=lambda c: len(c.find_all("p")))


def es_pagina_de_pelicula(soup):
    """Reviso si la página es de una película (y no de un actor, un cómic o
    una serie de TV). Lo sé porque el infobox de película siempre tiene
    "Directed by" y "Release date"/"Running time", y el de serie tiene
    "No. of episodes"."""
    infobox = soup.select_one("table.infobox")
    etiquetas = _etiquetas_infobox(infobox)
    if not etiquetas:
        return False
    tiene_director = any(e.startswith("Directed by") for e in etiquetas)
    tiene_estreno = any(e.startswith(("Release date", "Running time"))
                        for e in etiquetas)
    es_serie = any(e.startswith(("No. of episodes", "No. of seasons",
                                 "Original network", "Original release"))
                   for e in etiquetas)
    return tiene_director and tiene_estreno and not es_serie


def _titulo(soup, infobox):
    """El título bonito sale de arriba del infobox. Si no hay, uso el <h1>
    y le quito lo de "(2008 film)" que Wikipedia agrega para distinguir."""
    if infobox is not None:
        arriba = infobox.select_one(".infobox-above, th.summary")
        if arriba:
            t = limpiar_texto(arriba.get_text(" "))
            if t:
                return t
    h1 = soup.select_one("#firstHeading")
    t = limpiar_texto(h1.get_text(" ")) if h1 else ""
    return re.sub(r"\s*\([^()]*\bfilm\)$", "", t)


def _anio(etiquetas, categorias):
    """El año lo saco de "Release date" del infobox; si no, de la categoría
    "2008 films"."""
    for etiqueta, valor in etiquetas.items():
        if etiqueta.startswith("Release date"):
            m = re.search(r"\b(19\d{2}|20\d{2})\b", valor)
            if m:
                return m.group(1)
    for cat in categorias:
        m = re.match(r"^(19\d{2}|20\d{2}) films$", cat)
        if m:
            return m.group(1)
    return ""


def extraer_pelicula(html, url):
    """Recibo el HTML de una película y regreso un diccionario con todo,
    o None si la página no es de película."""
    soup = BeautifulSoup(html, PARSER)
    try:
        if not es_pagina_de_pelicula(soup):
            return None

        # URL "oficial" de la página (canonical): sirve para no repetir
        # películas cuando llego por una redirección con otro nombre.
        canon = soup.select_one('link[rel="canonical"]')
        url_canonica = normalizar_url(canon["href"]) if canon and canon.get("href") \
            else normalizar_url(url)

        raiz = _raiz_contenido(soup)
        infobox = soup.select_one("table.infobox")
        etiquetas = _etiquetas_infobox(infobox)

        # --- Categorías (las uso para géneros, año y saber si es Marvel) ---
        categorias, urls_generos = [], []
        generos_en, generos_es = [], []
        for a in soup.select('#mw-normal-catlinks a[href^="/wiki/Category:"]'):
            nombre = limpiar_texto(a.get_text(" "))
            categorias.append(nombre)
            encontrados = generos_de_categoria(nombre)
            if encontrados:
                urls_generos.append(normalizar_url(a["href"]))
                for en, es in encontrados:
                    if en not in generos_en:
                        generos_en.append(en)
                        generos_es.append(es)

        texto_cats = " ".join(categorias).lower()
        es_marvel = any(p in texto_cats for p in config.PALABRAS_MARVEL)

        # --- Títulos similares (cuadros de navegación de abajo + "See also") ---
        # Esto lo saco ANTES de limpiar el HTML.
        navboxes = soup.select("div.navbox, table.navbox")
        intro, secciones = _dividir_en_secciones(raiz) if raiz else ([], [])
        ver_tambien = _elementos_de_seccion(
            secciones, lambda t: t.startswith(TITULOS_SIMILARES))
        similares = _enlaces_de_titulos(list(navboxes) + ver_tambien)
        similares = [u for u in _sin_repetir(similares) if u != url_canonica]

        # --- Ahora sí limpio y saco los textos ---
        if raiz is not None:
            _quitar_basura(raiz)

        # Resumen = sección "Plot" (o Synopsis/Premise)
        resumen = _parrafos(_elementos_de_seccion(
            secciones, lambda t: t.startswith(TITULOS_RESUMEN)))

        # Reseña = sección de crítica. Primero busco "Critical response" /
        # "Critical reception"; si no hay, uso toda la sección "Reception".
        resena = _parrafos(_elementos_de_seccion(
            secciones, lambda t: "critical" in t), max_parrafos=3)
        if not resena:
            resena = _parrafos(_elementos_de_seccion(
                secciones, lambda t: t.startswith(("reception", "response"))),
                max_parrafos=3)

        # Descripción = primeros párrafos de la página (antes del primer título)
        descripcion = _parrafos(intro, max_parrafos=2)

        # Si no hay "Plot" (pasa en películas muy viejas o muy nuevas)
        # uso la descripción como resumen para no dejarlo vacío.
        if not resumen:
            resumen = descripcion

        # ID de Wikidata (único por película, sirve para cruzar con los CSV
        # de mis compañeros si también usaron Wikipedia).
        wikidata = ""
        enlace_wd = soup.select_one('#t-wikibase a[href*="wikidata.org"]')
        if enlace_wd:
            m = re.search(r"(Q\d+)", enlace_wd["href"])
            wikidata = m.group(1) if m else ""

        return {
            "titulo": _titulo(soup, infobox),
            "anio": _anio(etiquetas, categorias),
            "generos": generos_en,
            "generos_es": generos_es,
            "resumen": recortar(resumen, config.MAX_CARACTERES_RESUMEN),
            "resena": recortar(resena, config.MAX_CARACTERES_RESENA),
            "descripcion": recortar(descripcion, config.MAX_CARACTERES_DESCRIPCION),
            "es_marvel": es_marvel,
            "url": url_canonica,
            "urls_similares": similares,
            "urls_generos": _sin_repetir(urls_generos),
            "wikidata_id": wikidata,
        }
    finally:
        # Libero la memoria del árbol HTML de inmediato
        # (mi laptop anda con la RAM al 80%, cada MB cuenta).
        soup.decompose()


# ===========================================================================
# 2) Página de CATEGORÍA (géneros y categorías de Marvel)
# ===========================================================================
def _url_siguiente_pagina(soup):
    """Las categorías muestran 200 enlaces por página y abajo tienen
    "next page". Ese enlace usa /w/index.php, que el robots.txt de Wikipedia
    no deja visitar, así que lo convierto a la forma /wiki/...?pagefrom=...
    que sí está permitida y da la misma página."""
    for a in soup.select("#mw-pages a[href]"):
        if limpiar_texto(a.get_text()).lower() != "next page":
            continue
        partes = urlparse(a["href"])
        params = parse_qs(partes.query)
        titulo = params.get("title", [None])[0]
        desde = params.get("pagefrom", [None])[0]
        if partes.path.startswith("/wiki/"):
            titulo = titulo or unquote(partes.path[len("/wiki/"):])
        if titulo and desde:
            return (f"{config.SITIO_BASE}/wiki/{titulo.replace(' ', '_')}"
                    f"?pagefrom={quote(desde)}")
    return None


def extraer_categoria(html):
    """De una página de categoría regreso:
       peliculas      -> URLs de los artículos que lista
       subcategorias  -> URLs de las subcategorías
       siguiente      -> URL de la siguiente página (o None)
    """
    soup = BeautifulSoup(html, PARSER)
    try:
        peliculas = [normalizar_url(a["href"])
                     for a in soup.select("#mw-pages .mw-category a[href], "
                                          "#mw-pages li a[href]")
                     if es_articulo(a["href"])]
        subcats = [normalizar_url(a["href"])
                   for a in soup.select("#mw-subcategories a[href]")
                   if (ruta_wiki(a["href"]) or "").startswith("/wiki/Category:")]
        return {
            "peliculas": _sin_repetir(peliculas),
            "subcategorias": _sin_repetir(subcats),
            "siguiente": _url_siguiente_pagina(soup),
        }
    finally:
        soup.decompose()


# ===========================================================================
# 3) Página de LISTA (List of films based on Marvel Comics...)
# ===========================================================================
def extraer_lista(html):
    """Saco las URLs de películas que vienen en las tablas de una página de
    lista. Uso otra vez el truco de la cursiva para quedarme solo con
    títulos."""
    soup = BeautifulSoup(html, PARSER)
    try:
        tablas = soup.select("#mw-content-text table.wikitable")
        return _sin_repetir(_enlaces_de_titulos(tablas))
    finally:
        soup.decompose()


def nombre_de_categoria(url):
    """'https://en.wikipedia.org/wiki/Category:X-Men_films' -> 'X-Men films'"""
    ruta = urlparse(url).path
    return unquote(ruta.split("Category:", 1)[-1]).replace("_", " ")