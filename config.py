####################################################################
# Constantes globales de la configuración deL software (OLFAMETRIC)#
####################################################################

#-----COMUNICACIÓN---------------------------------
URI_WEBSOCKET_DEFECTO = "ws://olfatometro.local:8765"
INTERVALO_DE_ACTUALIZACION_UI_MS = 100
INTERVALO_SONDEO_COLA_WS_MS = 50
RECONEXION_AUTOMATICA_S = 0.5

#-----CONFIGURACIÓN DEL OLFATÓMETRO-----------------
NUM_CANALES = 6
COLORES_CANALES = ["Verde Claro", "Negro", "Blanco", "Azul", "Amarillo", "Rojo"]
CANAL_BLANCO = 2

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


#-----COLORES DE LA UI------------------------------
COLOR_ESTADO_OK = "#7deb7d"
COLOR_ESTADO_ERROR = "#fa8989"
COLOR_ESTADO_CONECTANDO = "#f0c060"
COLOR_ESTADO_DESCONECTADO = "#fa8989"

#-----FORMATOS DE TIEMPO---------------------------
FORMATO_HORA = "%H:%M:%S"
FORMATO_TIMESTAMP = "%d-%m-%Y %H:%M:%S"

