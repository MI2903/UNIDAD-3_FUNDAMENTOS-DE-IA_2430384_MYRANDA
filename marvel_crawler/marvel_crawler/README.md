# Web crawler de películas de Marvel → CSV

**Autora:** Myranda Belén Infante Castillo · **Matrícula:** 2430384
**Programa:** ITIID-2024 · Universidad Politécnica de Victoria · 7.º cuatrimestre
**Para qué es:** armar mi parte del dataset (500 a 1000 películas). Mi compañero lo junta con los CSV de los demás y el doctor lo usa para el recomendador.

---

## 1. Qué hace (el diagrama del pizarrón)

```
URL (http) ──► HTML ──► título, reseña/resumen, géneros ──► CSV
                │
                ├──► URLs de títulos similares ──► se vuelven a visitar (ciclo)
                │
                └──► URLs de los géneros ──► me listan otras URLs ──► (ciclo)
```

1. Empieza con páginas que **sí son de Marvel**: la lista de películas basadas en Marvel Comics y categorías como *Marvel Cinematic Universe films*, *X-Men films*, *Spider-Man films*, etc.
2. Entra a cada película, saca sus datos y los escribe en el CSV.
3. De la misma página toma:
   - los **títulos similares** (los cuadros de navegación de abajo y la sección *See also*),
   - las **URLs de sus géneros** (por ejemplo `Category:American_superhero_films`), que listan muchas películas más.
4. Usa una cola con prioridades: **primero Marvel**, luego las similares y al final las que salen por género. Así el CSV queda con todas las de Marvel y se completa con películas parecidas hasta llegar al número pedido.

> **Nota importante:** no existen 500 películas de Marvel. Contando el MCU, las de Sony, las de Fox (X-Men) y las animadas hay alrededor de 100 a 150. Por eso el crawler hace lo que pide el diagrama: sigue los títulos similares y los géneros para completar. La columna `es_marvel` dice cuáles son de Marvel (1) y cuáles llegaron por similitud o género (0).

## 2. Por qué Wikipedia y no páginas oficiales

| Opción | ¿Por qué no o por qué sí? |
|---|---|
| marvel.com / Disney | Son oficiales y bloquean bots. Descartadas, como pidió el profe. |
| IMDb, TMDB, Rotten Tomatoes, Letterboxd | Prohíben el scraping en sus términos y bloquean la IP. |
| **Wikipedia (en inglés)** ✅ | Permite crawlers que se identifican y van despacio. Tiene sinopsis (*Plot*), crítica (*Critical response*), géneros (categorías), títulos similares (cuadros de navegación) y páginas de género que listan más URLs. Es justo lo que pide el diagrama. |

El crawler además:
- **Respeta `robots.txt`**, las reglas que publica el sitio para los bots.
- **Espera de 1 a 2.5 s** al azar entre peticiones, para no saturar el servidor ni arriesgar la IP.
- **Se frena solo** si el servidor contesta "vas muy rápido" (429/503) y se detiene si le niegan el acceso varias veces (403).

## 3. Pensado para mi laptop

- **RAM:** mi laptop tiene 7.2 GB y ya va al 82 %. Por eso **no uso Selenium ni un navegador**, que gastan más de 1 GB. Uso `requests` + `BeautifulSoup` con `lxml`, que ocupan unos 60 a 100 MB. Además borro cada página de memoria en cuanto la leo y no uso pandas.
  - 💡 Si tienes abierta la máquina virtual de VMware (Kali), ciérrala mientras corre el crawler. Es lo que más RAM se come.
- **Redes que cambian (escuela / casa / datos):** si se va el internet, el crawler espera hasta 30 min a que regrese. Si cierras la laptop o pulsas `Ctrl+C`, **guarda el avance**. Cuando vuelves a ejecutar el mismo comando, sigue donde se quedó, sin repetir películas.
- **Disco:** el CSV final pesa unos 3 a 5 MB.

## 4. Instalación y ejecución (Windows + VS Code)

Abre la carpeta del proyecto en VS Code (**Archivo → Abrir carpeta…**) y luego la terminal (**Terminal → Nueva terminal**, que es PowerShell). Escribe estos comandos uno por uno:

```powershell
# 1) Crear el entorno virtual (solo la primera vez)
py -m venv .venv

# 2) Activarlo (cada vez que abras una terminal nueva)
.\.venv\Scripts\Activate.ps1
#    Si sale un error de "ejecución de scripts deshabilitada", corre esto y repite el paso 2:
#    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3) Instalar las librerías (solo la primera vez)
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4) (Opcional) Correr las pruebas sin internet
python -m pytest tests -v

# 5) Probar con UNA película antes de la corrida larga (no toca el CSV)
python crawler.py --probar "https://en.wikipedia.org/wiki/Iron_Man_2"

# 6) Corrida completa (700 películas por defecto, unos 30–45 min)
python crawler.py

#    O si quieres otra cantidad (entre 500 y 1000):
python crawler.py --objetivo 1000

# 7) Revisar que el CSV cumpla todo
python validar_csv.py
```

**Antes del paso 6:** abre `config.py` y cambia `CORREO_CONTACTO = "tu_correo@upv.edu.mx"` por tu correo. Wikipedia pide un contacto en el *User-Agent* de los bots.

**Si se interrumpe:** vuelve a correr `python crawler.py` y continúa donde se quedó.
**Para empezar de cero:** `python crawler.py --reiniciar` guarda una copia de respaldo del CSV anterior y empieza otra vez.

También puedes ejecutar todo desde el botón ▶ de VS Code (**Ejecutar y depurar**). Ya vienen configuradas tres opciones: *Probar una película*, *Crawler completo* y *Validar el CSV*.

## 5. El CSV que se genera: `datos/peliculas_marvel.csv`

Usa codificación UTF-8 con BOM para que Excel muestre bien los acentos. Todos los campos van entre comillas y las listas se separan con `|`.

| Columna | Qué tiene |
|---|---|
| `id` | Número consecutivo |
| `titulo` | Nombre de la película |
| `anio` | Año de estreno |
| `generos` | Géneros en inglés (`Action\|Superhero\|Science Fiction`) |
| `generos_es` | Los mismos géneros en español |
| `resumen` | De qué trata (sección *Plot*) |
| `resena` | Crítica (sección *Critical response* / *Reception*) |
| `descripcion` | Primer párrafo de la página (resumen corto) |
| `es_marvel` | 1 si es de Marvel y 0 si llegó por similitud o género |
| `url` | URL de la página de la película (el HTML de donde salió) |
| `urls_similares` | URLs de títulos similares |
| `urls_generos` | URLs de las páginas de género (cada una lista más películas) |
| `wikidata_id` | ID único (ej. `Q205028`); sirve para quitar repetidas al juntar los CSV del equipo |
| `origen` | Cómo llegó: `semilla_marvel`, `similar` o `genero` |

Reglas de calidad:
- Toda película guardada tiene **título, resumen y géneros**.
- Las que **no** son de Marvel solo se guardan si también tienen **reseña**.
- Las de Marvel se guardan aunque Wikipedia no tenga sección de crítica (pasa con muy pocas, casi siempre películas viejas o animadas). `validar_csv.py` dice cuántas son.
- Los textos vienen **en inglés** porque salen de Wikipedia en inglés, que es mucho más completa que la de español.

## 6. Archivos del proyecto

```
marvel_crawler/
├── crawler.py        ← el que se ejecuta (ciclo principal y la cola)
├── extractor.py      ← lee el HTML y saca los datos (título, géneros, etc.)
├── red.py            ← pide las páginas: esperas, robots.txt, reintentos, sin internet
├── estado.py         ← guarda el avance para poder reanudar
├── config.py         ← todos los ajustes (cantidad, velocidad, semillas, columnas)
├── validar_csv.py    ← revisa el CSV antes de entregarlo
├── requirements.txt
├── tests/            ← pruebas sin internet con HTML de ejemplo
├── datos/            ← aquí sale el CSV, el log y el avance
└── .vscode/          ← configuración lista para VS Code
```

## 7. Notas para el docente

- **Fuente:** Wikipedia (en.wikipedia.org), con contenido bajo licencia CC BY-SA 4.0. Se eligió por permitir el rastreo automatizado responsable. No se usó ningún sitio oficial ni sitios cuyos términos prohíben el scraping.
- **Ética del rastreo:** el crawler respeta `robots.txt`, se identifica con un User-Agent con contacto, va a una petición cada 1 a 2.5 s, hace una sola conexión a la vez y se detiene ante señales de rechazo.
- **Recorrido:** búsqueda por prioridad (*best-first*) con tres fuentes de enlaces, como en el diagrama: semillas de Marvel, títulos similares (*navboxes* y *See also*) y páginas de género (categorías), con paginación limitada.
- **Detección de géneros:** Wikipedia no tiene un campo de género. Los géneros se sacan de los nombres de las categorías con un vocabulario de unos 45 géneros y se excluyen las categorías temáticas (*Films set in…*, *Films based on…*).
- **Sin duplicados:** se usa la URL canónica de cada página, así que una película a la que se llega por redirección no se repite.
