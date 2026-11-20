# -*- coding: utf-8 -*-
"""
estado.py
---------
Aquí guardo la "memoria" del crawler para poder REANUDAR.

¿Por qué lo hice? Porque yo me conecto a diferentes redes (la de la escuela,
la de mi casa, datos del celular) y si se corta el internet o cierro la
laptop no quiero empezar desde cero. Cada cierto número de páginas guardo:
  - la cola de URLs pendientes (con su prioridad),
  - las URLs que ya visité,
  - las películas que ya están en el CSV.
Si vuelvo a correr el programa, sigue justo donde se quedó.

Autora: Myranda Belén Infante Castillo  |  Matrícula: 2430384
"""

import csv
import heapq
import json
import logging
import os
from itertools import count

import config

log = logging.getLogger("crawler")

# Prioridades de la cola (número más chico = se visita primero).
# Así me aseguro de que PRIMERO saque todas las de Marvel, luego las
# similares a Marvel y al final las que encuentre por género.
PRIORIDAD = {
    "semilla_marvel": 0,       # listas y categorías de Marvel
    "pelicula_marvel": 1,      # películas encontradas en esas listas
    "similar_de_marvel": 2,    # "títulos similares" de una peli de Marvel
    "similar": 4,              # "títulos similares" de otra película
    "categoria_genero": 5,     # URL de un género (lista de más URLs)
    "pelicula_de_genero": 6,   # películas que salen en la página del género
}


class Estado:
    def __init__(self):
        self.cola = []                 # montículo (heap) de pendientes
        self.mejor_prioridad = {}      # url -> mejor prioridad con la que entró
        self.visitados = set()         # URLs que ya descargué
        self.guardadas = set()         # URLs canónicas que ya están en el CSV
        self.reserva = []              # páginas extra de géneros por si me faltan
        self.total_guardadas = 0
        self.rechazadas = 0            # páginas que no eran película o venían incompletas
        self._contador = count()       # desempate para el heap (orden de llegada)

    # ------------------------------------------------------------------
    # Cola
    # ------------------------------------------------------------------
    def agregar(self, url, tipo, prioridad, marvel=False, profundidad=0, paginas=0):
        """Meto una URL a la cola. Si ya estaba pero ahora llega con mejor
        prioridad (por ejemplo, la encontré primero por género y luego
        resultó estar en la lista de Marvel) la vuelvo a meter adelante."""
        if url in self.visitados or url in self.guardadas:
            return False
        anterior = self.mejor_prioridad.get(url)
        if anterior is not None and anterior <= prioridad:
            return False
        self.mejor_prioridad[url] = prioridad
        heapq.heappush(self.cola, (prioridad, next(self._contador),
                                   url, tipo, marvel, profundidad, paginas))
        return True

    def siguiente(self):
        """Saco la siguiente URL más importante que no haya visitado."""
        while self.cola or self.reserva:
            if self.cola:
                item = heapq.heappop(self.cola)
            else:
                # Ya no hay nada en la cola: uso las páginas extra de géneros
                log.info("Cola vacía: uso páginas extra de géneros de la reserva.")
                item = self.reserva.pop(0)
            prioridad, _, url = item[0], item[1], item[2]
            if url in self.visitados or url in self.guardadas:
                continue
            if self.mejor_prioridad.get(url, prioridad) < prioridad:
                continue          # hay una copia mejor de esta URL en la cola
            return item
        return None

    def pendientes(self):
        return len(self.cola)

    # ------------------------------------------------------------------
    # Guardar / cargar
    # ------------------------------------------------------------------
    def guardar(self):
        """Guardo el estado en JSON. Primero escribo un archivo temporal y
        luego lo renombro, así si se apaga la laptop justo en ese momento
        no se me corrompe el archivo."""
        datos = {
            "cola": self.cola,
            "visitados": sorted(self.visitados),
            "reserva": self.reserva,
            "rechazadas": self.rechazadas,
        }
        temporal = str(config.ARCHIVO_ESTADO) + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
        os.replace(temporal, config.ARCHIVO_ESTADO)

    def cargar(self):
        """Si hay un estado guardado lo cargo. Regreso True si reanudé."""
        # Lo que ya está en el CSV SIEMPRE manda (es lo más confiable).
        self._leer_csv_existente()

        if not config.ARCHIVO_ESTADO.exists():
            return False
        try:
            with open(config.ARCHIVO_ESTADO, encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("El archivo de estado está dañado (%s); empiezo la "
                        "cola de nuevo, pero respeto lo que ya hay en el CSV.", e)
            return False

        self.visitados = set(datos.get("visitados", []))
        self.rechazadas = datos.get("rechazadas", 0)
        self.reserva = [tuple(x) for x in datos.get("reserva", [])]
        for item in datos.get("cola", []):
            prioridad, _, url, tipo, marvel, prof, pags = item
            self.agregar(url, tipo, prioridad, marvel, prof, pags)
        return True

    def _leer_csv_existente(self):
        """Leo las URLs que ya están en el CSV para no repetirlas."""
        if not config.ARCHIVO_CSV.exists():
            return
        with open(config.ARCHIVO_CSV, encoding="utf-8-sig", newline="") as f:
            for fila in csv.DictReader(f):
                if fila.get("url"):
                    self.guardadas.add(fila["url"])
        self.total_guardadas = len(self.guardadas)
