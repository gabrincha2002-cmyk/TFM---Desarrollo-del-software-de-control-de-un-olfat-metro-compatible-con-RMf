"""
=============================================================
  ws_client.py — Cliente WebSocket para OlfaMetric
=============================================================
"""

#Imports necesarios
import asyncio
import json
import logging
import queue
import threading
import time
from typing import Callable, Optional

import websockets

#Definición del logger para este módulo (se necesita futura vinculación con el logger principal de la app)
logger = logging.getLogger(__name__)


class WSClient:
    """
    Agente cliente del protocolo WebSocket no bloqueante para el software desarrollado
    """

    def __init__(
        self,
        uri:          str,
        on_datos:     Callable[[dict], None],
        on_estado:    Callable[[str], None],
        reconectar_s: float = 0.5,
    ):
        self.uri         = uri
        self._on_datos   = on_datos
        self._on_estado  = on_estado
        self._reconectar = reconectar_s

        #Definición de las colas búfer para gestionar el envío de mensajes enter el hilo de asyncio del hilo principal de Tkinter
        self._cola_tx: queue.Queue = queue.Queue()   #Cola búfer del almacenamiento de datos pendiente a enviar al ESP32-WROOM-32U
        self._cola_rx: queue.Queue = queue.Queue()   #Cola búfer de los mensajes recibidos pendientes de envío a la App

        #Definición del bucle de eventos de asyncio y el hilo que lo contiene
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._hilo: Optional[threading.Thread]          = None

        #Definición de las variables de estado del cliente WebSocket
        self._activo   = False
        self.conectado = False

    ##########################################
    # MÉTODOS PÚBLICOS DEL CLIENTE WEBSOCKET
    ##########################################

    def iniciar(self):
        """Arranca el hilo de fondo con el búcle de eventos de asyncio"""
        self._activo = True
        self._hilo   = threading.Thread(target=self._ejecutar_loop, daemon=True)
        self._hilo.start()
        logger.info(f"WSClient iniciado -> {self.uri}")

    def detener(self):
        """Para la conexión y el hilo de fondo."""
        self._activo = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("WSClient detenido.")

    def enviar(self, datos: dict):
        """
        Agrega un mensaje a la cola (_cola_tx) para enviarlo al futuro ESP32-WROOM-32U y actual simulador.
        (Es un método seguro para llamar desde el hilo principal de Tkinter)
        """
        self._cola_tx.put_nowait(json.dumps(datos))

    ##########################################
    # MÉTODOS PRIVADOS DEL CLIENTE WEBSOCKET
    ##########################################

    def _ejecutar_loop(self):
        #Crea un búcle de eventos propio para el hilo de fondo y lo ejecuta hasta que se detenga
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._ciclo_conexion())
        self._loop.close()

    async def _ciclo_conexion(self):
        """Intento de conectar y reconectar indefinidamente"""

        while self._activo:
            self._on_estado("conectando")
            try:
                #ping_interval y ping_timeout mantienen viva la conexión
                async with websockets.connect(
                    self.uri, ping_interval=20, ping_timeout=15
                ) as ws:
                    self.conectado = True
                    self._on_estado("conectado")
                    logger.info(f"Conectado a {self.uri}")

                    #Se ejecutan dos corutinas en paralelo: recibir y enviar
                    await asyncio.gather(
                        self._recibir(ws),
                        self._enviar(ws),
                    )

            except (OSError, ConnectionRefusedError, Exception) as e:
                logger.warning(f"Sin conexión ({e}). Reintentando en {self._reconectar} s…")
                self.conectado = False
                self._on_estado("desconectado")

            if self._activo:
                await asyncio.sleep(self._reconectar)

    
    async def _recibir(self, ws):
        """Recibe mensajes del ESP32-WROOM-32U y los pone en la cola de recepción (_cola_rx)"""
        async for mensaje in ws:
            try:
                datos = json.loads(mensaje)
                if "timestamp" in datos:
                    #Cálculo de la latencia en ms respecto al timestamp del mensaje recibido de ESP32-WROOM-32U
                    latencia_ms = (time.time() - datos["timestamp"]) * 1000
                    datos["latencia"] = round(latencia_ms, 1)
                #Se agregan los datos obtenidos del mensaje recibido a la cola de recepción
                self._cola_rx.put_nowait(datos)
            except json.JSONDecodeError as e:
                logger.warning(f"Mensaje no parseable: {e}")

    async def _enviar(self, ws):
        """Consume la cola de salida (_cola_tx) y envía mensajes al ESP32-WROOM-32U"""
        while True:
            #Espera no bloqueante para realizar las comprobaciones de la cola
            await asyncio.sleep(0.05)
            while not self._cola_tx.empty():
                try:
                    msg = self._cola_tx.get_nowait()
                    await ws.send(msg)
                except websockets.ConnectionClosed:
                    return
                except Exception as e:
                    logger.warning(f"Error enviando: {e}")