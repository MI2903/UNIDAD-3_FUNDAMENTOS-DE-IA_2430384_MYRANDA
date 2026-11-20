# -*- coding: utf-8 -*-
"""
red.py
------
Este archivo se encarga SOLO de pedir páginas a internet (la flecha "http"
del pizarrón -> me regresa el HTML).

Lo hice aparte porque aquí va todo lo "delicado":
  - esperar entre peticiones para no saturar al servidor,
  - respetar el robots.txt (las reglas que pone el sitio para los bots),
  - reintentar si la red falla,
  - aguantar si me cambio de red o se va el internet un rato,
  - frenarme si el servidor me dice "vas muy rápido" (error 429).

Autora: Myranda Belén Infante Castillo  |  Matrícula: 2430384
"""

import logging
import random
import time
from urllib import robotparser
from urllib.parse import urlparse

import requests

import config

log = logging.getLogger("crawler")


class BloqueoError(Exception):
    """La lanzo si el servidor me niega el acceso varias veces seguidas.
    Así el crawler guarda lo que lleva y se detiene en lugar de insistir
    (insistir es justo lo que hace que te bloqueen)."""


class SinInternetError(Exception):
    """La lanzo si pasa demasiado tiempo sin internet."""


class ClienteHTTP:
    """Mi "navegador" para el crawler. Guarda una sola sesión abierta
    (reutiliza la conexión, así gasta menos red y menos memoria)."""

    def __init__(self):
        self.sesion = requests.Session()
        self.sesion.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        })
        self.ultima_peticion = 0.0
        self.peticiones_hechas = 0
        self.rechazos_seguidos = 0
        self.robots = self._cargar_robots()

    # ------------------------------------------------------------------
    # robots.txt
    # ------------------------------------------------------------------
    def _cargar_robots(self):
        """Descargo el robots.txt del sitio y lo leo. Si el sitio dice
        que una ruta no se puede visitar, el crawler no la visita."""
        rp = robotparser.RobotFileParser()
        url_robots = config.SITIO_BASE + "/robots.txt"
        try:
            r = self.sesion.get(url_robots, timeout=config.TIMEOUT)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
                log.info("robots.txt cargado correctamente.")
                return rp
            log.warning("No pude leer robots.txt (HTTP %s). Sigo con cuidado.",
                        r.status_code)
        except requests.RequestException as e:
            log.warning("No pude descargar robots.txt (%s). Sigo con cuidado.", e)
        return None

    def puedo_visitar(self, url):
        """True si robots.txt me deja entrar a esa URL."""
        if self.robots is None:
            return True
        return self.robots.can_fetch(config.USER_AGENT, url)

    # ------------------------------------------------------------------
    # Esperas
    # ------------------------------------------------------------------
    def _esperar_turno(self):
        """Duermo un rato al azar entre petición y petición. Al azar para
        no parecer una ametralladora de peticiones."""
        espera = random.uniform(config.ESPERA_MINIMA, config.ESPERA_MAXIMA)
        transcurrido = time.time() - self.ultima_peticion
        if transcurrido < espera:
            time.sleep(espera - transcurrido)

    def _hay_internet(self):
        """Pruebo si hay conexión pidiendo algo muy ligero."""
        try:
            self.sesion.head(config.SITIO_BASE, timeout=(5, 10))
            return True
        except requests.RequestException:
            return False

    def _esperar_internet(self):
        """Si se fue el internet (me cambié de red, se cayó el WiFi de la
        escuela, etc.) me quedo esperando a que regrese en vez de tronar."""
        inicio = time.time()
        aviso = 0
        while not self._hay_internet():
            esperado = time.time() - inicio
            if esperado > config.ESPERA_MAXIMA_SIN_INTERNET:
                raise SinInternetError(
                    "Llevo demasiado tiempo sin internet. Guardo y me salgo.")
            if aviso % 3 == 0:
                log.warning("Sin conexión... espero a que regrese el internet "
                            "(%d s esperando). Puedes cambiarte de red.",
                            int(esperado))
            aviso += 1
            time.sleep(20)
        log.info("¡Volvió el internet! Continúo.")

    # ------------------------------------------------------------------
    # La petición en sí
    # ------------------------------------------------------------------
    def obtener_html(self, url):
        """Pido una URL y regreso (html, url_final).
        Regreso (None, None) si la página no existe o no la puedo visitar.
        """
        if not self.puedo_visitar(url):
            log.info("robots.txt no deja visitar: %s", url)
            return None, None

        for intento in range(1, config.MAX_REINTENTOS + 1):
            self._esperar_turno()
            try:
                r = self.sesion.get(url, timeout=config.TIMEOUT)
                self.ultima_peticion = time.time()
                self.peticiones_hechas += 1
            except (requests.ConnectionError, requests.Timeout) as e:
                self.ultima_peticion = time.time()
                log.warning("Error de red (intento %d/%d): %s",
                            intento, config.MAX_REINTENTOS, type(e).__name__)
                self._esperar_internet()
                time.sleep(5 * intento)          # espero un poco más cada vez
                continue
            except requests.RequestException as e:
                log.warning("Error raro pidiendo %s: %s", url, e)
                return None, None

            # --- Revisar qué me contestó el servidor ---
            if r.status_code == 200:
                self.rechazos_seguidos = 0
                r.encoding = r.encoding or "utf-8"
                return r.text, r.url

            if r.status_code == 404:
                log.info("No existe (404): %s", url)
                return None, None

            if r.status_code in (429, 503):
                # "Vas muy rápido" o "estoy ocupado": me espero lo que diga
                # el servidor (Retry-After) o un tiempo que va creciendo.
                espera = r.headers.get("Retry-After")
                espera = int(espera) if espera and espera.isdigit() else 30 * intento
                log.warning("El servidor pide calma (HTTP %s). Espero %d s.",
                            r.status_code, espera)
                time.sleep(espera)
                continue

            if r.status_code == 403:
                self.rechazos_seguidos += 1
                log.warning("Acceso negado (403) %d vez/veces seguidas.",
                            self.rechazos_seguidos)
                if self.rechazos_seguidos >= 3:
                    raise BloqueoError(
                        "El servidor me negó el acceso 3 veces seguidas. "
                        "Revisa que pusiste tu correo en config.py, espera "
                        "unos minutos o cambia de red y vuelve a correrlo "
                        "(se reanuda donde se quedó).")
                time.sleep(60)
                continue

            if 500 <= r.status_code < 600:
                log.warning("Error del servidor (HTTP %s), reintento.", r.status_code)
                time.sleep(10 * intento)
                continue

            log.info("Respuesta inesperada HTTP %s en %s", r.status_code, url)
            return None, None

        log.warning("Me rendí con %s después de %d intentos.",
                    url, config.MAX_REINTENTOS)
        return None, None

    def cerrar(self):
        self.sesion.close()


def es_mismo_sitio(url):
    """True si la URL es de Wikipedia en inglés (no me salgo del sitio)."""
    return urlparse(url).netloc == urlparse(config.SITIO_BASE).netloc
