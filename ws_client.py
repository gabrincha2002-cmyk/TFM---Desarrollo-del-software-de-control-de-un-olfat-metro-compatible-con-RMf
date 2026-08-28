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
import config

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
        reconectar_s:  float = config.RECONEXION_AUTOMATICA_S,
    ):
        self._ws = None
        self.uri          = uri
        self._on_estado   = on_estado
        self._reconectar  = reconectar_s

        self._cola_tx: queue.Queue = queue.Queue()   # mensajes pendientes de envío a ESP32
        self._cola_rx: queue.Queue = queue.Queue()   # mensajes recibidos pendientes de envío a App
        self._loop:    Optional[asyncio.AbstractEventLoop] = None
        self._hilo:    Optional[threading.Thread]          = None
        self._tarea_principal: Optional[asyncio.Task]      = None #para guardar la tarea asíncrona que correrá en el bucle de 
                                                                    #eventos de conexión y poder cancelarlo cunado se quiera
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
        """Para la conexión y el hilo de fondo.

        Cancela activamente la tarea en curso (esté conectada, intentando conectar
        o esperando entre reintentos) y espera a que el hilo de fondo termine antes
        de devolver el control. Sin esto, un iniciar() llamado justo después (p.ej.
        al reconectar con una URI encontrada por mDNS) podía arrancar un segundo
        hilo/event-loop mientras el anterior seguía vivo —atascado en un intento de
        conexión a una URI inalcanzable, que puede tardar bastante en fallar por sí
        solo—, dejando dos bucles de reconexión compitiendo por los mismos atributos
        (_ws, _loop, conectado) con URIs distintas.
        """
        self._activo = False
        self.conectado = False
        if self._loop and self._loop.is_running():
            if self._ws:
                asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
            if self._tarea_principal and not self._tarea_principal.done():
                # cancel() debe programarse desde dentro del propio loop (call_soon_threadsafe),
                # ya que los objetos de asyncio no son seguros de tocar desde otro hilo. Esto
                # interrumpe de inmediato cualquier await en curso, incluido uno bloqueado
                # dentro de websockets.connect(), sin esperar a que falle por su cuenta.
                self._loop.call_soon_threadsafe(self._tarea_principal.cancel)
        if self._hilo and self._hilo.is_alive():
            self._hilo.join(timeout=3.0)
            if self._hilo.is_alive():
                logger.warning("El hilo de WSClient no terminó a tiempo al detener; puede quedar una reconexión en curso con la URI anterior.")
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
        self._tarea_principal = self._loop.create_task(self._ciclo_conexion())
        try:
            self._loop.run_until_complete(self._tarea_principal)
        except asyncio.CancelledError:
            pass
        #se procede a la limpieza en caso de que el hilo esté a punto de morir
        finally:
            #se realiza la limpieza de la tarea principal realizada
            self._tarea_principal = None
            #se cierra el bucle ejecutado para la conexión del cliente websocket con el servidor liberando recursos
            self._loop.close()

    async def _ciclo_conexion(self):
        """Intenta conectar y reconectar indefinidamente."""

        while self._activo:
            self._on_estado("conectando")
            try:
                async with websockets.connect(self.uri, ping_interval=15, ping_timeout=15, open_timeout=5) as ws:
                    self._ws = ws
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

            finally:
                self._ws = None

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
                datos["latencia"] = await self.calcular_latencia(ws)
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

    async def calcular_latencia(self, ws):
            tiempo_ping = time.perf_counter()
            espera_pong = await ws.ping()
            await espera_pong
            tiempo_pong = time.perf_counter()
            return round((tiempo_pong - tiempo_ping)*1000,1)
