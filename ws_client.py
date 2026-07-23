"""
=============================================================
  ws_client.py — Cliente WebSocket para OlfaMetric
=============================================================
  Conecta la app con el simulador (olfato_sim.py) o con el
  ESP32 real.  Corre en un hilo de fondo para no bloquear
  la interfaz gráfica de CustomTkinter.

  Uso dentro de App.__init__():
    from ws_client import WSClient
    self.ws_client = WSClient(
        uri        = "ws://localhost:8765",   # o IP del ESP32
        on_estado  = self._on_estado_ws,
    )
    self.ws_client.iniciar()

  Envío de comandos (desde cualquier método de App):
    self.ws_client.enviar({"cmd": "activar", "canal": 2, "velocidad_pct": 80})
    self.ws_client.enviar({"cmd": "parar",   "canal": 2})
    self.ws_client.enviar({"cmd": "parar_todos"})
=============================================================
  Dependencias:
    pip install websockets
=============================================================
"""

import asyncio
import websockets
import json
import threading
import logging
import time
import queue
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class WSClient:
    """
    Cliente WebSocket no bloqueante para OlfaMetric.

    Parámetros
    ----------
    uri : str
        Dirección del servidor WebSocket.
        Simulador local : "ws://localhost:8765"
        ESP32 real      : "ws://192.168.1.XX:8765"  (cambiar IP)

    on_datos : Callable[[dict], None]
        Callback llamado en el hilo principal (vía queue) cada vez
        que llega un paquete de telemetría.  Recibe el dict completo.

    on_estado : Callable[[str], None]
        Callback para cambios de estado de la conexión.
        Posibles valores: "conectando", "conectado", "desconectado", "error"

    reconectar_s : float
        Segundos entre intentos de reconexión automática.
    """

    def __init__(
        self,
        uri:           str,
        on_estado:     Callable[[str], None],
        reconectar_s:  float = 0.5,
    ):
        self.uri          = uri
        self._on_estado   = on_estado
        self._reconectar  = reconectar_s

        self._cola_tx: queue.Queue = queue.Queue()   # mensajes pendientes de envío a ESP32
        self._cola_rx: queue.Queue = queue.Queue()   # mensajes recibidos pendientes de envío a App
        self._loop:    Optional[asyncio.AbstractEventLoop] = None
        self._hilo:    Optional[threading.Thread]          = None
        self._activo   = False
        self.conectado = False

    # ── API pública ───────────────────────────────────────────

    def iniciar(self):
        """Arranca el hilo de fondo con el event-loop de asyncio."""
        self._activo = True
        self._hilo   = threading.Thread(target=self._ejecutar_loop, daemon=True)
        self._hilo.start()
        logger.info(f"WSClient iniciado → {self.uri}")

    def detener(self):
        """Para la conexión y el hilo de fondo."""
        self._activo = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("WSClient detenido.")

    def enviar(self, datos: dict):
        """
        Encola un mensaje para enviarlo al ESP32 / simulador.
        Seguro para llamar desde el hilo principal de Tkinter.
        """
        self._cola_tx.put_nowait(json.dumps(datos))

    # ── Internos ──────────────────────────────────────────────

    def _ejecutar_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._ciclo_conexion())
        self._loop.close()

    async def _ciclo_conexion(self):
        """Intenta conectar y reconectar indefinidamente."""

        while self._activo:
            self._on_estado("conectando")
            try:
                async with websockets.connect(self.uri, ping_interval=20 , ping_timeout=15) as ws:
                    self.conectado = True
                    self._on_estado("conectado")
                    logger.info(f"Conectado a {self.uri}")

                    # Dos corutinas en paralelo: recibir y enviar
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
    """
    async def _recibir(self, ws):
        async for mensaje in ws:
            try:
                datos = json.loads(mensaje)
                self._on_datos(datos)
            except json.JSONDecodeError as e:
                logger.warning(f"Mensaje no parseable: {e} | contenido: {mensaje[:100]}")
    """

    # En ws_client.py — modificar _recibir:
    async def _recibir(self, ws):
        async for mensaje in ws:
            try:
                datos = json.loads(mensaje)
                if "timestamp" in datos:
                    #se incluye el cálculo de la latencia
                    latencia_ms = (time.time() - datos["timestamp"]) * 1000
                    datos["latencia"] = round(latencia_ms,1)
                # Mete en cola los datos recibidos para que el hilo principal los procese
                self._cola_rx.put_nowait(datos)
            except json.JSONDecodeError as e:
                logger.warning(f"Mensaje no parseable: {e}")

    async def _enviar(self, ws):
        """Drena la cola de salida y envía mensajes al servidor."""
        while True:
            # Espera no bloqueante de mensajes en la cola
            await asyncio.sleep(0.05)
            while not self._cola_tx.empty():
                try:
                    msg = self._cola_tx.get_nowait()
                    await ws.send(msg)
                except websockets.ConnectionClosed:
                    return
                except Exception as e:
                    logger.warning(f"Error enviando: {e}")
