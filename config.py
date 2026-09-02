####################################################################
# Constantes globales de la configuración deL software (OLFAMETRIC)#
####################################################################
import os 
#-----COMUNICACIÓN---------------------------------
URI_WEBSOCKET_DEFECTO = "ws://olfatometro.local:8765"
INTERVALO_DE_ACTUALIZACION_UI_MS = 100
INTERVALO_SONDEO_COLAS_RECIBIDOS_ESTADO_MS = 50
INTERVALO_SONDEO_COLA_ENVIO_S = 0.05
RECONEXION_AUTOMATICA_S = 0.5
SERVICIO_MDNS = "_olfatometro._tcp.local."
TIMEOUT_CIERRE_HILO_S = 3.0
TIMEOUT_SEGUNDOS = 5
PING_INTERVAL_S = 10
PING_TIMEOUT_S = 10
OPEN_TIMEOUT_S = 5

#-----CONFIGURACIÓN DEL OLFATÓMETRO-----------------
NUM_CANALES = 6
COLORES_CANALES = ["Verde", "Negro", "Blanco", "Azul", "Amarillo", "Rojo"]
CANAL_BLANCO = 2
PORCENTAJE_VELOCIDAD = 14

#-----CONFIGURACIÓN DEL PROTOCOLO-------------------
VALOR_MAX_TIEMPO_DESENSIBILIZACION = 120
VALOR_MIN_TIEMPO_DESENSIBILIZACION = 10 
VALOR_MAX_TIEMPO_EXPOSICION = 30
VALOR_MIN_TIEMPO_EXPOSICION = 3
VALOR_MAX_CICLOS = 10
VALOR_MIN_CICLOS = 1
VALOR_MAX_INTERVALO_CICLOS = 120
VALOR_MIN_INTERVALO_CICLOS = 10

#-----CONFIGURACIÓN DE LA CARACTERIZACIÓN-------------------
VALOR_MAXIMO_TIEMPO_CARACTERIZACION = 300
MUESTRAS_POR_SEGUNDO_CARACTERIZACION = 10
PARAMETROS_CARACTERIZACION = [
    ("flujo", "Flujo (ml/min)"),
    ("concentracion", "Concentración (µg/m³)"),
    ("velocidad", "Velocidad (rpm)"),
    ("latencia", "Latencia (ms)")
]
MUESTREO_CARACTERIZACION= 1 / MUESTRAS_POR_SEGUNDO_CARACTERIZACION
#-----CONFIGURACIÓN HARDWARE------------------------
POSICIONES_CANALES = {2: 0, 0: 200, 1: 400, 3: 600, 4: 800, 5: 1000, -1: 1200, -2: 1400}
PASOS_POR_CANAL = 200

#-----GRÁFICAS Y BUFFERS----------------------------
TAMANO_BUFFER_GRAFICAS = 61
TIEMPO_GRAFICAS = 61
LIMITESY = {"velocidad": [0,10000],
            "flujo": [0,500],
            "concentracion": [0,500],
            "latencia": [0,1000]
            }

#-----DIRECTORIOS Y FORMATOS------------------------
DIRECTORIO_DEL_PROYECTO = os.path.dirname(os.path.abspath(__file__))
DIRECTORIO_ARCHIVOS_TEMPORALES = os.path.join(DIRECTORIO_DEL_PROYECTO, "archivos_generados")
FORMATO_HORA = "%H:%M:%S"
FORMATO_TIMESTAMP = "%d-%m-%Y %H:%M:%S"

#-----COLORES DE LA UI------------------------------
COLOR_ESTADO_OK = "#7deb7d"
COLOR_ESTADO_CONECTANDO = "#f0c060"
COLOR_ESTADO_DESCONECTADO = "#fa8989"



