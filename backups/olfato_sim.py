"""
=============================================================
  olfato_sim.py — Simulador de hardware del Olfatómetro
=============================================================
  Simula el comportamiento físico de:
    · ESP32 ESP-WROOM-32        → servidor WebSocket
    · 6× Motor HUSETOO 775      → rampa arranque, inercia, ruido
    · 6× Sensor MiniPID 2 PPB   → respuesta con delay y saturación
    · 6× Flujómetro digital     → caudal proporcional a rpm

  Uso:
    1. Ejecutar este archivo en un terminal:
         python olfato_sim.py
    2. La app principal se conecta a  ws://localhost:8765

  Sustitución por hardware real:
    Cuando el ESP32 físico esté listo, simplemente deja de
    ejecutar este simulador y cambia WS_URI en la app a la
    IP del ESP32.  El protocolo JSON es idéntico.
=============================================================
  Dependencias:
    pip install websockets
=============================================================
"""

import asyncio
import json
import math
import random
import time
import websockets
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIM] %(message)s",
    datefmt="%H:%M:%S"
)

# ─────────────────────────────────────────────
#  CONSTANTES DEL SISTEMA FÍSICO
# ─────────────────────────────────────────────

# Motor HUSETOO 775 a 24 V
MOTOR_RPM_MAX       = 5000      # rpm máximas a 24 V (valor típico 775)
MOTOR_RPM_IDLE      = 0
MOTOR_RAMPA_S       = 2.0       # segundos hasta velocidad nominal
MOTOR_RUIDO_STD     = 40        # desviación estándar del ruido (rpm)

# Flujómetro: caudal proporcional a rpm
FLUJO_MAX_ML_MIN    = 500.0     # ml/min a rpm máximas
FLUJO_RUIDO_STD     = 2.5       # ml/min

# MiniPID 2 (fotoionización, escala ppb → µg/m³ aproximada COV genérico)
# Factor de conversión orientativo para olores de prueba (no específico)
PID_FACTOR_PPB_UGM3 = 4.9       # µg/m³ por ppb (benceno como referencia)
PID_DELAY_S         = 0.8       # retardo de respuesta del sensor (s)
PID_RISE_TAU_S      = 1.2       # constante de tiempo de subida (s)
PID_MAX_PPB         = 2000      # saturación del sensor
PID_RUIDO_STD       = 3.0       # ppb de ruido de fondo

# Red / ESP32
WS_HOST             = "localhost"
WS_PORT             = 8765
TICK_S              = 0.1       # intervalo de actualización (100 ms)


# ─────────────────────────────────────────────
#  MODELOS FÍSICOS
# ─────────────────────────────────────────────

class Motor775Sim:
    """
    Simula un motor de corriente continua HUSETOO 775.

    Comportamiento modelado:
      · Rampa de arranque exponencial (constante de tiempo MOTOR_RAMPA_S)
      · Ruido gaussiano sobre las rpm
      · Cálculo de flujo de aire proporcional a rpm
      · Cálculo de latencia de comunicación simulada (jitter WiFi)
    """

    def __init__(self, id_canal: int):
        self.id_canal   = id_canal
        self.rpm_objetivo = 0.0     # rpm deseadas (setpoint)
        self.rpm_actual   = 0.0     # rpm con dinámica
        self.activo       = False
        self._t_arranque  = None    # momento en que se ordenó arrancar

    # ── Control ──────────────────────────────

    def activar(self, velocidad_pct: float = 100.0):
        """
        Ordena arrancar el motor al porcentaje de velocidad indicado.
        velocidad_pct: 0–100 %
        """
        self.rpm_objetivo = MOTOR_RPM_MAX * max(0.0, min(100.0, velocidad_pct)) / 100.0
        self.activo       = True
        self._t_arranque  = time.time()
        logging.info(f"Motor canal {self.id_canal} ACTIVADO → {self.rpm_objetivo:.0f} rpm")

    def parar(self):
        self.rpm_objetivo = 0.0
        self.activo       = False
        logging.info(f"Motor canal {self.id_canal} DETENIDO")

    # ── Simulación ───────────────────────────

    def actualizar(self, dt: float) -> dict:
        """
        Avanza la simulación dt segundos y devuelve las métricas del canal.
        Llamar cada TICK_S segundos.
        """
        # Dinámica de primer orden: rpm_actual → rpm_objetivo con tau = MOTOR_RAMPA_S
        tau = MOTOR_RAMPA_S
        alfa = 1.0 - math.exp(-dt / tau)
        self.rpm_actual += alfa * (self.rpm_objetivo - self.rpm_actual)

        # Ruido gaussiano
        rpm_medida = self.rpm_actual + random.gauss(0, MOTOR_RUIDO_STD if self.activo else MOTOR_RUIDO_STD * 0.1)
        rpm_medida = max(0.0, rpm_medida)

        # Flujo proporcional a rpm (con ruido)
        flujo = (rpm_medida / MOTOR_RPM_MAX) * FLUJO_MAX_ML_MIN
        flujo += random.gauss(0, FLUJO_RUIDO_STD)
        flujo = max(0.0, flujo)

        # Latencia simulada (jitter WiFi + tiempo de proceso ESP32)
        latencia_ms = round(random.gauss(12, 3))   # media 12 ms, σ=3 ms
        latencia_ms = max(1, latencia_ms)

        return {
            "velocidad_motor": round(rpm_medida, 1),
            "flujo":           round(flujo, 2),
            "latencia":        latencia_ms,
        }


class MiniPID2Sim:
    """
    Simula el sensor de fotoionización MiniPID 2 PPB.

    Comportamiento modelado:
      · Retardo de respuesta (sensor tarda PID_DELAY_S en empezar a subir)
      · Subida exponencial con constante PID_RISE_TAU_S
      · Bajada al parar (purga del tubo de muestra)
      · Saturación a PID_MAX_PPB
      · Ruido de fondo gaussiano
      · Conversión orientativa a µg/m³

    Nota: el MiniPID 2 mide COVs totales (no especie-específico).
    En un sistema real, si hay varios canales activos simultáneamente,
    la lectura es la suma de todos los compuestos presentes.
    """

    def __init__(self, id_canal: int):
        self.id_canal       = id_canal
        self.activo         = False
        self._ppb_objetivo  = 0.0
        self._ppb_actual    = 0.0
        self._t_activacion  = None

        # Concentración "real" del cartucho (personalizable por canal)
        self._ppb_nominal   = random.uniform(80, 400)   # ppb nominal del olor en el cartucho

    def activar(self, ppb_nominal: float = None):
        self.activo         = True
        self._t_activacion  = time.time()
        if ppb_nominal is not None:
            self._ppb_nominal = ppb_nominal
        # El objetivo no sube inmediatamente (modelado por el delay)
        self._ppb_objetivo  = 0.0
        logging.info(f"PID canal {self.id_canal} ACTIVO → nominal {self._ppb_nominal:.0f} ppb")

    def parar(self):
        self.activo        = False
        self._ppb_objetivo = 0.0
        logging.info(f"PID canal {self.id_canal} DETENIDO (purga)")

    def actualizar(self, dt: float) -> dict:
        """
        Devuelve concentración en ppb y µg/m³.
        """
        # ── Delay de respuesta ──
        if self.activo and self._t_activacion is not None:
            elapsed = time.time() - self._t_activacion
            if elapsed >= PID_DELAY_S:
                self._ppb_objetivo = self._ppb_nominal
            else:
                self._ppb_objetivo = 0.0

        # ── Dinámica de primer orden ──
        tau  = PID_RISE_TAU_S
        alfa = 1.0 - math.exp(-dt / tau)
        self._ppb_actual += alfa * (self._ppb_objetivo - self._ppb_actual)

        # ── Ruido + saturación ──
        ppb = self._ppb_actual + random.gauss(0, PID_RUIDO_STD)
        ppb = max(0.0, min(PID_MAX_PPB, ppb))

        # ── Conversión a µg/m³ (orientativa) ──
        ugm3 = ppb * PID_FACTOR_PPB_UGM3

        return {
            "concentracion_ppb": round(ppb, 1),
            "concentracion":     round(ugm3, 2),   # µg/m³ (clave usada por la app)
        }


# ─────────────────────────────────────────────
#  SIMULADOR ESP32 (servidor WebSocket)
# ─────────────────────────────────────────────

class ESP32Sim:
    """
    Simula el ESP32 ESP-WROOM-32 como servidor WebSocket.

    Protocolo (mensajes JSON):

      App → ESP32 (comandos):
        {"cmd": "activar", "canal": 2, "velocidad_pct": 80}
        {"cmd": "parar",   "canal": 2}
        {"cmd": "parar_todos"}
        {"cmd": "set_ppb", "canal": 2, "ppb": 250}

      ESP32 → App (telemetría, cada TICK_S):
        {
          "canal":             2,
          "estado":            "activo",        # "activo" | "inactivo"
          "velocidad_motor":   3820.5,           # rpm
          "flujo":             256.4,            # ml/min
          "latencia":          11,               # ms
          "concentracion_ppb": 87.3,             # ppb (MiniPID)
          "concentracion":     427.7,            # µg/m³
          "timestamp":         1716000000.234
        }

      ESP32 → App (ACK de comando):
        {"ack": "activar", "canal": 2, "ok": true}
    """

    def __init__(self):
        self.motores = [Motor775Sim(i) for i in range(6)]
        self.sensores = [MiniPID2Sim(i) for i in range(6)]
        self._clientes: set = set()
        self._t_ultimo = time.time()

    # ── Servidor WebSocket ────────────────────

    async def arrancar(self):
        logging.info(f"Simulador ESP32 escuchando en ws://{WS_HOST}:{WS_PORT}")
        async with websockets.serve(self._manejar_cliente, WS_HOST, WS_PORT):
            await self._bucle_telemetria()

    async def _manejar_cliente(self, ws):
        """Gestiona una conexión entrante de la app."""
        ip = ws.remote_address
        logging.info(f"App conectada desde {ip}")
        self._clientes.add(ws)
        try:
            async for mensaje in ws:
                await self._procesar_comando(ws, mensaje)
        except websockets.ConnectionClosed:
            pass
        finally:
            self._clientes.discard(ws)
            logging.info(f"App desconectada ({ip})")

    async def _procesar_comando(self, ws, mensaje: str):
        """Interpreta los comandos JSON enviados por la app."""
        try:
            datos = json.loads(mensaje)
        except json.JSONDecodeError:
            logging.warning(f"Mensaje no válido: {mensaje}")
            return

        cmd   = datos.get("cmd", "")
        canal = datos.get("canal", -1)

        if cmd == "activar" and 0 <= canal < 6:
            vel = datos.get("velocidad_pct", 100.0)
            self.motores[canal].activar(vel)
            self.sensores[canal].activar()
            ack = {"ack": "activar", "canal": canal, "ok": True}

        elif cmd == "parar" and 0 <= canal < 6:
            self.motores[canal].parar()
            self.sensores[canal].parar()
            ack = {"ack": "parar", "canal": canal, "ok": True}

        elif cmd == "parar_todos":
            for i in range(6):
                self.motores[i].parar()
                self.sensores[i].parar()
            ack = {"ack": "parar_todos", "ok": True}

        elif cmd == "set_ppb" and 0 <= canal < 6:
            ppb = datos.get("ppb", 200.0)
            self.sensores[canal]._ppb_nominal = ppb
            ack = {"ack": "set_ppb", "canal": canal, "ppb": ppb, "ok": True}

        else:
            ack = {"ack": cmd, "ok": False, "error": "comando desconocido"}

        await ws.send(json.dumps(ack))

    # ── Bucle de telemetría ───────────────────

    async def _bucle_telemetria(self):
        """
        Cada TICK_S segundos calcula las métricas de todos los canales
        y las envía a todos los clientes conectados.
        """
        while True:
            await asyncio.sleep(TICK_S)

            ahora = time.time()
            dt    = ahora - self._t_ultimo
            self._t_ultimo = ahora

            # En _bucle_telemetria, sustituir el for actual por:
            for canal in range(6):
                motor_data  = self.motores[canal].actualizar(dt)
                sensor_data = self.sensores[canal].actualizar(dt)

            # Solo enviar si el canal está activo
                if not self.motores[canal].activo:
                    continue

                estado = "activo"
                paquete = {
                "canal":     canal,
                "estado":    estado,
                "timestamp": round(ahora, 3),
                **motor_data,
                **sensor_data,
                }

                if self._clientes:
                    mensaje = json.dumps(paquete)
                    caidos = set()
                    for ws in self._clientes:
                        try:
                            await ws.send(mensaje)
                        except websockets.ConnectionClosed:
                            caidos.add(ws)
                    self._clientes -= caidos


# ─────────────────────────────────────────────
#  PUNTO DE ENTRADA
# ─────────────────────────────────────────────

if __name__ == "__main__":
    sim = ESP32Sim()
    try:
        asyncio.run(sim.arrancar())
    except KeyboardInterrupt:
        logging.info("Simulador detenido por el usuario.")