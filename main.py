"""
=============================================================
 App de escritorio — Control remoto 6 motores 
 Controlador: ESP32 ESP-WROOM-32
 Dependencias: pip install customtkinter 
=============================================================
"""

import json

from CTkToolTip import CTkToolTip
import customtkinter as ctk
from tkinter import messagebox
import time

import datetime
import math

#Imports necesarios para la generación del informe:
#se utilizan para generar el pdf:
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER

import openpyxl #se utiliza para generar un excel
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.chart import LineChart, Reference
import matplotlib.pyplot as plt
import tempfile
import os
import csv #ya se encuentraya incluido en python
import matplotlib as mpl #para poder exportar las gráficas como imágenes


#para gráficas en tiempo real
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import collections
import numpy as np

#conexión con simulación del ESP32
from ws_client import WSClient

#para generar un hilo paralelo a la app
import threading
import zeroconf as zc


#para el cálculo de métricas de calibración
import statistics

#para generar números aleatorios en el protocolo aleatorio
import random

#Import de widgets personalizados
from widgets import Canal, SpinboxCTk, Consola

#Import de funciones para generar informes
import reports

#Import de funciones para buscar dispositivos en la red local mediante mDNS
import discovery

#Import de constates de configuración del software
import config




ctk.set_appearance_mode("dark")  # Modos: "System" (predeterminado), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Temas: "blue" (predeterminado), "dark-blue", "green"

# ─────────────────────────────────────────────────────────────
#  FUNCIONALIDADES
# ─────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────
#  INTERFAZ GRÁFICA
# ─────────────────────────────────────────────────────────────        
    
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("OlfaMetric")
        self.geometry("1920x1080")
        self.protocol("WM_DELETE_WINDOW", self._cerrar_aplicacion)
        self.colores_canales = config.COLORES_CANALES  # Colores para cada cartucho
        self.posicion_valvula = 0
        self.fase_actual = None
        # Diccionario para mapear los canales a sus posiciones en la gráfica
        self.posiciones_canales = config.POSICIONES_CANALES
        self.tiempo_grafica_flujo = list(range(config.TIEMPO_GRAFICAS))
        self.tiempo_grafica_concentracion = list(range(config.TIEMPO_GRAFICAS))
        self.tiempo_grafica_latencia = list(range(config.TIEMPO_GRAFICAS))
        self.tiempo_grafica_velocidad = list(range(config.TIEMPO_GRAFICAS))

        #buffers termporales
        self.olores = []
        self.historial_sesion= []
        self.ultimos_datos_telemetria = {}
        self.metricas_calibracion = {}
        # Los widgets de UI (p. ej. `e_tiempo_calibrado`) se crean en `crear_ui()` más abajo,
        # por eso no debemos usar `self.e_tiempo_calibrado.get()` aquí (aún no existe).
        # Usar el tamaño por defecto de las gráficas (`self.tiempo_grafica_flujo`) para inicializar buffers.
        self.buffer_flujo = collections.deque([np.nan]*config.TAMANO_BUFFER_GRAFICAS, maxlen=config.TAMANO_BUFFER_GRAFICAS)
        self.buffer_concentracion = collections.deque([np.nan]*config.TAMANO_BUFFER_GRAFICAS,maxlen=config.TAMANO_BUFFER_GRAFICAS)
        self.buffer_latencia = collections.deque([np.nan]*config.TAMANO_BUFFER_GRAFICAS,maxlen=config.TAMANO_BUFFER_GRAFICAS)
        self.buffer_velocidad = collections.deque([np.nan]*config.TAMANO_BUFFER_GRAFICAS,maxlen=config.TAMANO_BUFFER_GRAFICAS)

        os.makedirs(config.DIRECTORIO_ARCHIVOS_TEMPORALES, exist_ok=True)
        self.ruta_archivo_temporal = os.path.join(config.DIRECTORIO_ARCHIVOS_TEMPORALES, "historial_sesion_.jsonl")

        with open(self.ruta_archivo_temporal, "w", encoding = "utf-8"):
            pass

    
        #buffers históricos
        self.buffer_historico_flujo = []
        self.buffer_historico_concentracion = []
        self.buffer_historico_velocidad = []
        self.buffer_historico_latencia = []
        self.buffer_historico_timestamps = []
        self.buffer_historico_olores = []

        self.segundos_restantes_protocolo = 0
        self.segundos_restantes_velocidad = 0
        self.segundos_restantes_flujo = 0
        self.segundos_restantes_concentracion = 0
        self.segundos_restantes_latencia = 0
        self.tiempo_guardado = None

        #protocolo 
        self.canales_protocolo = []
        self.after_activo = None
        self.canal_activo= None
        self.canal_anterior= None
        self.canal_siguiente= None
        self.sv_canal_activo = ctk.StringVar(value="Ninguno")
        self.sv_canal_anterior = ctk.StringVar(value="Ninguno")
        self.sv_canal_siguiente = ctk.StringVar(value="Ninguno")
        self.protocolo_activo = False
        self.protocolo_parado = False
        self.orden_protocolo = None

        #espera de posición de válvula (compartido entre activación manual, calibrado y protocolo):
        #lista de (num_canal, funcion_periodo, args) pendientes de que el ESP32 confirme
        #que la válvula ha llegado a la posición de destino de ese canal.
        self.callbacks_pendientes_posicion_valvula = []
        #canal cuya rotación aún no se ha confirmado, o None. Solo puede haber uno a la vez:
        #la activación manual está bloqueada mientras hay protocolo o calibrado en curso, y
        #activar un canal nuevo cancela (para) el anterior, así que nunca coexisten dos esperas.
        self.canal_esperando_posicion = None

        #calibrado
        self.canal_calibrado = None
        self.calibrado_velocidad_parado = False
        self.calibrado_flujo_parado = False
        self.calibrado_concentracion_parado = False
        self.calibrado_latencia_parado = False
        self.canales_calibrados = dict.fromkeys(config.COLORES_CANALES, False)

        # flags por parámetro
        self.calibrando_velocidad        = False
        self.calibrando_flujo            = False
        self.calibrando_concentracion    = False
        self.calibrando_latencia         = False

        # buffers por parámetro
        self.buffer_historico_calibrado_velocidad      = []
        self.buffer_historico_calibrado_flujo          = []
        self.buffer_historico_calibrado_concentracion  = []
        self.buffer_historico_calibrado_latencia       = []
        self.contador_velocidad = 0
        self.contador_flujo = 0
        self.contador_concentracion = 0
        self.contador_latencia = 0

        # after por parámetro
        self.after_calibrado_velocidad       = None
        self.after_calibrado_flujo           = None
        self.after_calibrado_concentracion   = None
        self.after_calibrado_latencia        = None
        self.after_actualizar_graficas       = None

        #Cliente para establecer conexión con el controlador ESP32-WROOM (o simulador)
        self.ws_client = WSClient(
        uri        = config.URI_WEBSOCKET_DEFECTO,   # o IP del ESP32
        on_estado  = self._on_estado_ws,
    )

        self.grid_rowconfigure(0, weight=0)  # Cabecera
        self.grid_rowconfigure(1, weight=1)  # Canales y Protocolo se expande
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)  # Consola no se expande

        self.grid_columnconfigure(0, weight=2)  # Columna de canales y cabecera se expande
        self.grid_columnconfigure(1, weight=1) # Columna de protocolo se expande 

        #comienzo estableciendo conexión con ESP32
        self.ws_client.iniciar()
        #se llama a la función para procesar los mensajes recibidos de ws_client
        self._procesar_cola_ws()
        self.crear_ui()
        self.tiempo_sesion()



    def _cerrar_aplicacion(self):
        """Cierra la aplicación de manera segura, deteniendo el cliente WebSocket y liberando recursos."""
        if messagebox.askokcancel("Cerrar OlfaMetric", "¿Está seguro de que desea salir de la aplicación?"):
            self.ws_client.enviar({"cmd": "parar_todos"})  #todos los canales se detienen antes de cerrar
            self.ws_client.enviar({"cmd": "rotar", "canal": config.CANAL_BLANCO, "pasos": -self.posicion_valvula})  #se retorna al punto de origen (canal blanco) antes de cerrar
            #Detener el cliente WebSocket
            self.ws_client.detener()
            #Cerrar la ventana principal
            self.destroy()

    def asignar_tooltip_spinbox(self, spinbox: SpinboxCTk, mensaje_entry: str, mensaje_incrementar: str = "Incrementar valor", mensaje_decrementar: str = "Decrementar valor"):
        """Asigna un tooltip a un SpinboxCTk con el mensaje proporcionado."""
        spinbox._tooltip =[
        CTkToolTip(spinbox.e_spinbox, message=mensaje_entry, delay=0.5, font=ctk.CTkFont(size=12)),
        CTkToolTip(spinbox.b_decrementar, message=mensaje_decrementar, delay=0.5, font=ctk.CTkFont(size=12)),
        CTkToolTip(spinbox.b_incrementar, message=mensaje_incrementar, delay=0.5, font=ctk.CTkFont(size=12)),
        ]

    def _procesar_cola_ws(self):
        """Lee mensajes de la cola WS y los procesa en el hilo de Tkinter."""
        try:
            # Recorre y procesa todos los mensajes pendientes en la cola de recepción
            while not self.ws_client._cola_rx.empty():
                # Obtiene el siguiente mensaje sin esperar (get_nowait evita bloqueos)
                datos = self.ws_client._cola_rx.get_nowait()

                # Si es un mensaje de confirmación (ACK) o configuración, envía a su handler
                if "ack" in datos or datos.get("tipo") == "config":
                    self._datos_ack(datos)
                    
                # Si contiene datos de registro/log, procesa como entrada de log
                elif "log" in datos:
                    self._datos_log(datos)

                # Si contiene información de canal y estado, trata como dato de telemetría
                elif "canal" in datos and "estado" in datos:
                    self._datos_telemetria(datos)
                # Si no cumple ninguno de los formatos esperados, lo reporta como desconocido
                else:
                    self.consola.registro(f"[Ws_client] Mensaje recibido desconocido: {datos}")
        except Exception as e:
            # Si ocurre un error durante el procesamiento, lo registra en la consola
            self.consola.registro(f"Error procesando cola en el protocolo WebSocket: {e}", nivel="ERROR")
        # El bloque finally se ejecuta siempre, incluso si hay error. Asegura que
        # la función se reschedule cada 50ms para polling continuo de mensajes
        finally:
            self.after(config.INTERVALO_SONDEO_COLA_WS_MS, self._procesar_cola_ws)  # Verifica la cola cada 50 ms

    #CONSTRUCCIÓN DE INTERFAZ DE USUARIO
    def crear_ui(self):
        #Para crear un marco dentro de la ventana principal
        self.f_cabecera = ctk.CTkFrame(self,fg_color="#1e1e1e",border_color="#4a4c4e", border_width=1, corner_radius=10)  # Fondo transparente para el marco
        self.f_cabecera.grid(row=0,column=0,sticky="nsew",columnspan=2)  # Usamos grid para colocar el marco

        self.f_cabecera.grid_columnconfigure((0,1), weight=1) 
        self.f_cabecera.grid_rowconfigure(0, weight=1)
        #self.f_cabecera.grid_rowconfigure(1, weight=1)
        #self.f_cabecera.grid_columnconfigure(2, weight=0) 


        #CABECERA
        self.l_titulo = ctk.CTkLabel(self.f_cabecera,text="OlfaMetric",corner_radius=10,
                                  text_color="#0f7780", font=ctk.CTkFont(size=60, overstrike=False, weight="bold"))
        self.l_titulo.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        self.l_estado_conexion = ctk.CTkLabel(self.f_cabecera,text="○ Desconectado",fg_color="#1e1e1e",text_color="#fa8989",
                                     font=ctk.CTkFont(size=18,weight="bold"))
        self.l_estado_conexion.grid(row=0, column=1,padx=30, pady=10, sticky="en") 
        
        self.b_buscar_dispositivos = ctk.CTkButton(self.f_cabecera, text="Buscar dispositivos", fg_color="#1e1e1e",
                                                 text_color="#828282",corner_radius=10,border_width=1,
                                                  command=self.iniciar_busqueda_mdns,font=ctk.CTkFont(size=14, weight="bold"))
        self.b_buscar_dispositivos.grid(row=0, column=1, padx=10, pady=(0,5), sticky="es")
        

        #CONSOLA
        #La creo antes que canales para que la creación de estos no me den ningún problema (están relacionados por
        # la función registro de la clase Consola) 
        self.f_consola = ctk.CTkFrame(self, fg_color="#1e1e1e",border_color="#4a4c4e", border_width=1, corner_radius=10, height=100)
        self.f_consola.grid(row=3,column=0,columnspan=1,padx=5,pady=(5,10),sticky="ew")
        self.consola= Consola(self.f_consola)
        self.consola.grid(row=0,column=0,padx=10,pady=(10,5),sticky="ew")


        
        self.tv_canales_calibracion = ctk.CTkTabview(master=self, fg_color="transparent",border_color="#4a4c4e", border_width=1, corner_radius=10, width=450)
        self.tv_canales_calibracion.grid(row=1,column=0,padx=5,pady=10,sticky="nsew", rowspan=2)
        self.tv_canales_calibracion.add("Canales")
        self.tv_canales_calibracion.add("Calibración")
        self.tv_canales_calibracion._segmented_button.configure(text_color="#ffffff", border_width=1, corner_radius=10, width = 200,height =30, font=ctk.CTkFont(size=20, weight="bold"))

        self.tv_canales_calibracion.tab("Canales").grid_columnconfigure(0, weight=1)
        self.tv_canales_calibracion.tab("Calibración").grid_columnconfigure(0, weight=1)

        self.tv_canales_calibracion.set("Canales")

        self.f_canales = ctk.CTkScrollableFrame(self.tv_canales_calibracion.tab("Canales"),fg_color="transparent")  # Fondo transparente para el marco
        self.f_canales.grid(row=0,column=0,padx=5,pady=10,sticky="nsew",rowspan=2)  # Usamos grid para colocar el marco
        self.tv_canales_calibracion.tab("Canales").grid_rowconfigure(0, weight=1)
        self.tv_canales_calibracion.tab("Canales").grid_columnconfigure(0, weight=1)
        self.f_canales.grid_columnconfigure(0, weight=1)
        self.f_canales.grid_columnconfigure(1, weight=1)




        #self.l_canales= ctk.CTkLabel(self.f_canales, text="Canales",text_color="#458B8D", font=ctk.CTkFont(size=22, weight="bold"))
        #self.l_canales.grid(row=0, column=0, padx=10, pady=(10,5), sticky="w")

         #CANALES
        #-----------
        self.cuadros_canales = []
        for i in range(0,6):
            columna = i//3
            fila = i%3
            cuadro_canal= Canal(self.f_canales,color_canal=self.colores_canales[i],num_canal=i,registro=self.consola.registro, actualizar_canal=self.actualizar_canales)
            cuadro_canal.grid(row=fila+1, column=columna, padx=10, pady=10, sticky="nsew")
            #actualiza el CombBox de calibración cada vez que se modifica el nombre del canal
            cuadro_canal.e_olor_canal.bind("<FocusOut>", lambda e: self.actualizar_comb_canales_calibrados())
            self.cuadros_canales.append(cuadro_canal)
       
        self.cuadros_canales[self.colores_canales.index("Blanco")].e_olor_canal.destroy()  # El canal blanco no tiene entrada de olor, por lo que se destruye el widget de entrada

        #----------
        #CALIBRACIÓN
        # Crea un frame deslizante dentro del tabview
        self.f_calibracion_scroll = ctk.CTkScrollableFrame(self.tv_canales_calibracion.tab("Calibración"), fg_color="transparent")
        self.f_calibracion_scroll.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.tv_canales_calibracion.tab("Calibración").grid_rowconfigure(0, weight=1)
        self.tv_canales_calibracion.tab("Calibración").grid_columnconfigure(0, weight=1)
        self.f_calibracion_scroll.grid_columnconfigure(0, weight=1)
        self.f_calibracion_scroll.grid_columnconfigure(1, weight=1)
        #self.f_calibracion_scroll.grid_rowconfigure(2, weight=1)
        #self.f_calibracion_scroll.grid_rowconfigure(3, weight=1)   

        
        #self.l_calibracion = ctk.CTkLabel(self.f_calibracion_scroll, text="Calibración", text_color="#458B8D", font=ctk.CTkFont(size=22, weight="bold"))
        #self.l_calibracion.grid(row=0, column=0, padx=10, pady=(10,5), sticky="n")

        # Selección de canales a calibrar
        self.f_calibracion_canales_tiempo = ctk.CTkFrame(self.f_calibracion_scroll, fg_color="transparent", width=30, height=15, corner_radius=10 ,border_width=0)
        self.f_calibracion_canales_tiempo.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        sv_canales_calibrado = ctk.StringVar(value="Canal a calibrar")
        self.comb_canales_calibrados = ctk.CTkComboBox(self.f_calibracion_canales_tiempo, values=[],
                                             width=180, height=36, text_color="#ffffff",command=self.seleccionar_calibrado,dropdown_fg_color="#0a5f70", variable=sv_canales_calibrado)
        self.comb_canales_calibrados.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        CTkToolTip(self.comb_canales_calibrados, message="Seleccione una canal con olor predefinido para calibrar", delay=0.5, font=ctk.CTkFont(size=12))



        self.l_tiempo_calibrado = ctk.CTkLabel(self.f_calibracion_canales_tiempo, text="Tiempo:", text_color="#458B8D", font=ctk.CTkFont(size=14, weight="bold"))
        self.l_tiempo_calibrado.grid(row=0, column=1, padx=0, pady=5, sticky="e")
        self.e_tiempo_calibrado = SpinboxCTk(self.f_calibracion_canales_tiempo, valor=30, valor_min=1, valor_max=config.VALOR_MAXIMO_TIEMPO_CALIBRACION, escalon=1, width=60, height=15)
        self.e_tiempo_calibrado.grid(row=0, column=2, padx=0, pady=5, sticky="w")
        self.asignar_tooltip_spinbox(self.e_tiempo_calibrado, mensaje_entry="Introduzca el tiempo de la duración (en segundos) de la fase de calibración (tanto induvidual como general)")


        self.f_botones_calibrado_general = ctk.CTkFrame(self.f_calibracion_scroll, fg_color="transparent", width=30, height=15, corner_radius=10 ,border_width=0)
        self.f_botones_calibrado_general.grid(row=0, column=1, padx=15, pady=5, sticky="e")
        #Iniciar calibrado general
        self.b_iniciar_calibrado_general = ctk.CTkButton(self.f_botones_calibrado_general, text="Inicio General", text_color="#ffffff", fg_color= "#85ad75", width= 10, height=15,
                                                   hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=10,command=self.iniciar_calibrado_general,font=ctk.CTkFont(size=18, weight="bold"))
        self.b_iniciar_calibrado_general.grid(row=0, column=0, ipadx=0, padx=5, pady=5, sticky="wsne")

        #reiniciar calibrado general
        self.b_reiniciar_calibrado_general = ctk.CTkButton(self.f_botones_calibrado_general, text="Reinicio General", text_color="#ffffff", fg_color= "#C7BE19" , width=10, height=15,
                                                   hover_color="#9da31e", border_color="#F6F04F", border_width= 1, corner_radius=10,command=self._consultar_reiniciar_calibrado_general,font=ctk.CTkFont(size=18, weight="bold"))
        self.b_reiniciar_calibrado_general.grid(row=0, column=1, ipadx=0, padx=5, pady=5, sticky="wsne")

        #parar calibrado general
        self.b_parar_calibrado_general = ctk.CTkButton(self.f_botones_calibrado_general, text="Parada General", text_color="#ffffff", fg_color= "#f56a6a", width=10, height=15,
                                                   hover_color="#ee4242", border_color="#ff0000", border_width= 1, corner_radius=10,command=self._consultar_parar_calibrado_general,font=ctk.CTkFont(size=18, weight="bold"))
        self.b_parar_calibrado_general.grid(row=0, column=2, ipadx=0 ,padx=5, pady=5, sticky="wsne")

        #Calibración Velocidad
        self.l_calibrado_velocidad = ctk.CTkLabel(self.f_calibracion_scroll, text="Velocidad", text_color="#458B8D", font=ctk.CTkFont(size=20, weight="bold"))
        self.l_calibrado_velocidad.grid(row=1, column=0, padx=60, pady=0, sticky="ws")

        #Gráfica en tiempo real - Velocidad
        #se establece un tamaño específico de fuente por defecto a cada eje de cada gráfica
        mpl.rcParams["axes.labelsize"] = 16
        fig_velocidad = Figure(figsize=(10,5),dpi=60)
        self.ax_velocidad = fig_velocidad.add_subplot(111)
        self.ax_velocidad.set_xlim(0,int(self.e_tiempo_calibrado.get()))
        self.ax_velocidad.set_ylim(config.LIMITESY["velocidad"][0],config.LIMITESY["velocidad"][1])  # Ajusta el rango del eje y según tus datos esperados
        self.ax_velocidad.set_xlabel("Tiempo (s)")
        self.ax_velocidad.set_ylabel("Velocidad (m/s)")
        #fig_velocidad.set_facecolor("#222526")  # Fondo de la figura transparente
        #self.ax_velocidad.set_facecolor("#222526")  # Fondo del gráfico transparente
        fig_velocidad.set_facecolor("#242424")  # Fondo de la figura transparente
        self.ax_velocidad.set_facecolor("#242424")
        self.ax_velocidad.tick_params(colors = "#ffffff") 
        self.ax_velocidad.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
        self.ax_velocidad.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
        self.ax_velocidad.spines['bottom'].set_color('#ffffff')  # Color de la línea del eje x
        self.ax_velocidad.spines['left'].set_color('#ffffff')  # Color de
        self.ax_velocidad.spines['top'].set_color('#ffffff')  # Color de la línea superior
        self.ax_velocidad.spines['right'].set_color('#ffffff')  # Color de la línea derecha
        self.ax_velocidad.plot(self.tiempo_grafica_velocidad,list(self.buffer_velocidad)[::-1])
        fig_velocidad.tight_layout()
        self.canvas_velocidad = FigureCanvasTkAgg(fig_velocidad, master=self.f_calibracion_scroll)
        self.canvas_velocidad.get_tk_widget().grid(row=2, column=0, padx=10, pady=0, sticky="nesw")
        self.canvas_velocidad.draw()

        self.f_botones_calibrado_velocidad = ctk.CTkFrame(self.f_calibracion_scroll, fg_color="transparent", width=75, height=15, corner_radius=10,border_width=1)
        self.f_botones_calibrado_velocidad.grid(row=1, column=0, padx=10, pady=0, sticky="se")
        self.f_botones_calibrado_velocidad.grid_columnconfigure(0, weight=1)
        self.f_botones_calibrado_velocidad.grid_columnconfigure(1, weight=1)
        self.f_botones_calibrado_velocidad.grid_columnconfigure(2, weight=1)


        self.b_iniciar_calibrado_velocidad = ctk.CTkButton(self.f_botones_calibrado_velocidad, text="▶", text_color = "#ffffff", fg_color="#85ad75", width=25, height=15, 
        hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=5,command=self.iniciar_calibrado_velocidad,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibrado_velocidad.grid(row=0, column=0, ipadx = 0, padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_iniciar_calibrado_velocidad, message="Iniciar calibrado de velocidad", delay=0.5, font=ctk.CTkFont(size=12))

       

        self.b_reiniciar_calibrado_velocidad = ctk.CTkButton(self.f_botones_calibrado_velocidad, text="↻" , text_color = "#ffffff", fg_color="#C7BE19",width=25, height=15,
                                                   hover_color="#9da31e", border_color="#CFC61B", border_width=1, corner_radius=5,command=self.reiniciar_calibrado_velocidad,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_velocidad.grid(row=0, column=1, ipadx = 0, padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_reiniciar_calibrado_velocidad, message="Reiniciar calibrado de velocidad", delay=0.5, font=ctk.CTkFont(size=12))

        self.b_parar_calibrado_velocidad = ctk.CTkButton(self.f_botones_calibrado_velocidad, text="◼", text_color = "#ffffff",width=25, height=15, 
        fg_color="#f56a6a", hover_color = "#ee4242", border_color="#ff0000",corner_radius=5,border_width=1, command=self.parar_calibrado_velocidad,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_velocidad.grid(row=0, column=2, ipadx = 0 ,padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_parar_calibrado_velocidad, message="Detener el calibrado de velocidad ya iniciado", delay=0.5, font=ctk.CTkFont(size=12))


        #Calibración Flujo
        self.l_calibrado_flujo = ctk.CTkLabel(self.f_calibracion_scroll, text="Flujo", text_color="#458B8D", font=ctk.CTkFont(size=20, weight="bold"))
        self.l_calibrado_flujo.grid(row=1, column=1, padx=60, pady=0, sticky="ws")

        #Gráfica en tiempo real - Flujo
        fig_flujo = Figure(figsize=(10,5),dpi=60)
        self.ax_flujo = fig_flujo.add_subplot(111)
        self.ax_flujo.set_xlim(0,int(self.e_tiempo_calibrado.get()))
        self.ax_flujo.set_ylim(config.LIMITESY["flujo"][0],config.LIMITESY["flujo"][1])  # Ajusta el rango del eje y según tus datos esperados
        self.ax_flujo.set_xlabel("Tiempo (s)")
        self.ax_flujo.set_ylabel("Flujo (ml/min)")
        self.ax_flujo.plot(self.tiempo_grafica_flujo,self.buffer_flujo)
        fig_flujo.set_facecolor('#242424')  # Fondo de la figura transparente
        self.ax_flujo.set_facecolor("#242424")  # Fondo del gráfico transparente
        self.ax_flujo.tick_params(colors = "#ffffff") 
        self.ax_flujo.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
        self.ax_flujo.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
        self.ax_flujo.spines['bottom'].set_color('#ffffff')  # Color de la línea del eje x
        self.ax_flujo.spines['left'].set_color('#ffffff')  # Color de
        self.ax_flujo.spines['top'].set_color('#ffffff')  # Color de la línea superior
        self.ax_flujo.spines['right'].set_color('#ffffff')  # Color de la línea derecha
        fig_flujo.tight_layout()
        self.canvas_flujo = FigureCanvasTkAgg(fig_flujo, master=self.f_calibracion_scroll)
        self.canvas_flujo.get_tk_widget().grid(row=2, column=1, padx=10, pady=0, sticky="nsew")
        self.canvas_flujo.draw()

        self.f_botones_calibrado_flujo = ctk.CTkFrame(self.f_calibracion_scroll, fg_color="transparent", width=75, height=15, corner_radius=10,border_width=1)
        self.f_botones_calibrado_flujo.grid(row=1, column=1, padx=10, pady=0, sticky="se")
        self.f_botones_calibrado_flujo.grid_columnconfigure(0, weight=1)
        self.f_botones_calibrado_flujo.grid_columnconfigure(1, weight=1)
        self.f_botones_calibrado_flujo.grid_columnconfigure(2, weight=1)

        self.b_iniciar_calibrado_flujo = ctk.CTkButton(self.f_botones_calibrado_flujo, text="▶", text_color = "#ffffff", fg_color="#85ad75", width=25, height=15, 
        hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=5,command=self.iniciar_calibrado_flujo,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibrado_flujo.grid(row=0, column=0, ipadx = 0, padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_iniciar_calibrado_flujo, message="Iniciar calibrado de flujo", delay=0.5, font=ctk.CTkFont(size=12))
       

        self.b_reiniciar_calibrado_flujo = ctk.CTkButton(self.f_botones_calibrado_flujo, text="↻" , text_color = "#ffffff", fg_color="#C7BE19",width=25, height=15,
                                                   hover_color="#9da31e", border_color="#CFC61B", border_width=1, corner_radius=5,command=self.reiniciar_calibrado_flujo,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_flujo.grid(row=0, column=1, ipadx = 0, padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_reiniciar_calibrado_flujo, message="Reiniciar calibrado de flujo", delay=0.5, font=ctk.CTkFont(size=12))


        self.b_parar_calibrado_flujo = ctk.CTkButton(self.f_botones_calibrado_flujo, text="◼", text_color = "#ffffff",width=25, height=15, 
        fg_color="#f56a6a", hover_color = "#ee4242", border_color="#ff0000",corner_radius=5,border_width=1, command=self.parar_calibrado_flujo,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_flujo.grid(row=0, column=2, ipadx = 0 ,padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_parar_calibrado_flujo, message="Detener el calibrado de flujo ya iniciado", delay=0.5, font=ctk.CTkFont(size=12))
        



        #Calibración Concentración
        self.l_calibrado_concentracion = ctk.CTkLabel(self.f_calibracion_scroll, text="Concentración", text_color="#458B8D", font=ctk.CTkFont(size=20, weight="bold"))
        self.l_calibrado_concentracion.grid(row=3, column=0, padx=60, pady=0, sticky="ws")

        #Gráfica en tiempo real - Concentración
        fig_concentracion = Figure(figsize=(10,5),dpi=60)
        self.ax_concentracion = fig_concentracion.add_subplot(111)
        self.ax_concentracion.set_xlim(0,int(self.e_tiempo_calibrado.get()))
        self.ax_concentracion.set_ylim(config.LIMITESY["concentracion"][0],config.LIMITESY["concentracion"][1])  # Ajusta el rango del eje y según tus datos esperados
        self.ax_concentracion.set_xlabel("Tiempo (s)")
        self.ax_concentracion.set_ylabel("Concentracion (µg/m\u00B3)")
        self.ax_concentracion.plot(self.tiempo_grafica_concentracion,self.buffer_concentracion)
        fig_concentracion.set_facecolor('#242424')  # Fondo de la figura transparente
        self.ax_concentracion.set_facecolor("#242424")  # Fondo del gráfico transparente
        self.ax_concentracion.tick_params(colors = "#ffffff") 
        self.ax_concentracion.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
        self.ax_concentracion.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
        self.ax_concentracion.spines['bottom'].set_color('#ffffff')  # Color de la línea del eje x
        self.ax_concentracion.spines['left'].set_color('#ffffff')  # Color de
        self.ax_concentracion.spines['top'].set_color('#ffffff')  # Color de la línea superior
        self.ax_concentracion.spines['right'].set_color('#ffffff')  # Color de la línea derecha
        fig_concentracion.tight_layout()
        self.canvas_concentracion = FigureCanvasTkAgg(fig_concentracion, master=self.f_calibracion_scroll)
        self.canvas_concentracion.get_tk_widget().grid(row=4, column=0, padx=10, pady=0, sticky="nsew")
        self.canvas_concentracion.draw()

        self.f_botones_calibrado_concentracion = ctk.CTkFrame(self.f_calibracion_scroll, fg_color="transparent", width=75, height=15, corner_radius=10,border_width=1)
        self.f_botones_calibrado_concentracion.grid(row=3, column=0, padx=10, pady=0, sticky="se")
        self.f_botones_calibrado_concentracion.grid_columnconfigure(0, weight=1)
        self.f_botones_calibrado_concentracion.grid_columnconfigure(1, weight=1)
        self.f_botones_calibrado_concentracion.grid_columnconfigure(2, weight=1)

        self.b_iniciar_calibrado_concentracion = ctk.CTkButton(self.f_botones_calibrado_concentracion, text="▶", text_color = "#ffffff", fg_color="#85ad75", width=25, height=15, 
        hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=5,command=self.iniciar_calibrado_concentracion,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibrado_concentracion.grid(row=0, column=0, ipadx = 0, padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_iniciar_calibrado_concentracion, message="Iniciar calibrado de concentración", delay=0.5, font=ctk.CTkFont(size=12))
       

        self.b_reiniciar_calibrado_concentracion = ctk.CTkButton(self.f_botones_calibrado_concentracion, text="↻" , text_color = "#ffffff", fg_color="#C7BE19",width=25, height=15,
                                                   hover_color="#9da31e", border_color="#CFC61B", border_width=1, corner_radius=5,command=self.reiniciar_calibrado_concentracion,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_concentracion.grid(row=0, column=1, ipadx = 0, padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_reiniciar_calibrado_concentracion, message="Reiniciar calibrado de concentración", delay=0.5, font=ctk.CTkFont(size=12))


        self.b_parar_calibrado_concentracion = ctk.CTkButton(self.f_botones_calibrado_concentracion, text="◼", text_color = "#ffffff",width=25, height=15, 
        fg_color="#f56a6a", hover_color = "#ee4242", border_color="#ff0000",corner_radius=5,border_width=1, command=self.parar_calibrado_concentracion,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_concentracion.grid(row=0, column=2, ipadx = 0 ,padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_parar_calibrado_concentracion, message="Detener el calibrado de concentración ya iniciado", delay=0.5, font=ctk.CTkFont(size=12))




        #Calibración Latencia
        self.l_calibrado_latencia = ctk.CTkLabel(self.f_calibracion_scroll, text="Latencia", text_color="#458B8D", font=ctk.CTkFont(size=20, weight="bold"))
        self.l_calibrado_latencia.grid(row=3, column=1, padx=60, pady=0, sticky="ws")

        #Gráfica en tiempo real - Latencia
        fig_latencia = Figure(figsize=(10,5),dpi=60)
        self.ax_latencia = fig_latencia.add_subplot(111)
        self.ax_latencia.set_xlim(0,int(self.e_tiempo_calibrado.get()))
        self.ax_latencia.set_ylim(config.LIMITESY["latencia"][0],config.LIMITESY["latencia"][1])  # Ajusta el rango del eje y según tus datos esperados
        self.ax_latencia.set_xlabel("Tiempo (s)")
        self.ax_latencia.set_ylabel("Latencia (ms)")
        self.ax_latencia.plot(self.tiempo_grafica_latencia,self.buffer_latencia)
        fig_latencia.set_facecolor('#242424')  # Fondo de la figura transparente
        self.ax_latencia.set_facecolor("#242424")  # Fondo del gráfico transparente
        self.ax_latencia.tick_params(colors = "#ffffff") 
        self.ax_latencia.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
        self.ax_latencia.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
        self.ax_latencia.spines['bottom'].set_color('#ffffff')  # Color de la línea del eje x
        self.ax_latencia.spines['left'].set_color('#ffffff')  # Color de
        self.ax_latencia.spines['top'].set_color('#ffffff')  # Color de la línea superior
        self.ax_latencia.spines['right'].set_color('#ffffff')  # Color de la línea derecha
        fig_latencia.tight_layout()
        self.canvas_latencia = FigureCanvasTkAgg(fig_latencia, master=self.f_calibracion_scroll)
        self.canvas_latencia.get_tk_widget().grid(row=4, column=1, padx=10, pady=0, sticky="nsew")
        self.canvas_latencia.draw()

        self.f_botones_calibrado_latencia = ctk.CTkFrame(self.f_calibracion_scroll, fg_color="transparent", width=75, height=15, corner_radius=10,border_width=1)
        self.f_botones_calibrado_latencia.grid(row=3, column=1, padx=10, pady=0, sticky="se")
        self.f_botones_calibrado_latencia.grid_columnconfigure(0, weight=1)
        self.f_botones_calibrado_latencia.grid_columnconfigure(1, weight=1)
        self.f_botones_calibrado_latencia.grid_columnconfigure(2, weight=1)

        self.b_iniciar_calibrado_latencia = ctk.CTkButton(self.f_botones_calibrado_latencia, text="▶", text_color = "#ffffff", fg_color="#85ad75", width=25, height=15, 
        hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=5,command=self.iniciar_calibrado_latencia,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibrado_latencia.grid(row=0, column=0, ipadx = 0, padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_iniciar_calibrado_latencia, message="Iniciar calibrado de latencia", delay=0.5, font=ctk.CTkFont(size=12))
       

        self.b_reiniciar_calibrado_latencia = ctk.CTkButton(self.f_botones_calibrado_latencia, text="↻" , text_color = "#ffffff", fg_color="#C7BE19",width=25, height=15,
                                                   hover_color="#9da31e", border_color="#CFC61B", border_width=1, corner_radius=5,command=self.reiniciar_calibrado_latencia,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_latencia.grid(row=0, column=1, ipadx = 0, padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_reiniciar_calibrado_latencia, message="Reiniciar calibrado de latencia", delay=0.5, font=ctk.CTkFont(size=12))

        self.b_parar_calibrado_latencia = ctk.CTkButton(self.f_botones_calibrado_latencia, text="◼", text_color = "#ffffff",width=25, height=15, 
        fg_color="#f56a6a", hover_color = "#ee4242", border_color="#ff0000",corner_radius=5,border_width=1, command=self.parar_calibrado_latencia,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_latencia.grid(row=0, column=2, ipadx = 0 ,padx=0, pady=0, sticky="nswe")
        CTkToolTip(self.b_parar_calibrado_latencia, message="Detener el calibrado de latencia ya iniciado", delay=0.5, font=ctk.CTkFont(size=12))



        self.actualizar_graficas()


        """
        self.f_canales = ctk.CTkScrollableFrame(self,fg_color="transparent")  # Fondo transparente para el marco
        self.f_canales.grid(row=1,column=0,padx=5,pady=10,sticky="nsew",rowspan=2)  # Usamos grid para colocar el marco
        self.f_canales.grid_columnconfigure((0,1), weight=1)
        self.f_canales.grid_rowconfigure((0,1), weight=1)


        self.l_canales= ctk.CTkLabel(self.f_canales, text="Canales",text_color="#458B8D", font=ctk.CTkFont(size=22, weight="bold"))
        self.l_canales.grid(row=0, column=0, padx=10, pady=(10,5), sticky="w")

        self.cuadros_canales = []
        for i in range(0,6):
            columna = i//3
            fila = i%3
            cuadro_canal= Canal(self.f_canales,color_canal=self.colores_canales[i],num_canal=i,registro=self.consola.registro, actualizar_canal=self.actualizar_canales)
            cuadro_canal.grid(row=fila+1, column=columna, padx=10, pady=10, sticky="nsew")
            self.cuadros_canales.append(cuadro_canal)
        
        """
        self.tv_prot_cal_est = ctk.CTkTabview(master=self, fg_color="transparent",border_color="#4a4c4e", border_width=1, corner_radius=10, width=400)
        self.tv_prot_cal_est.grid(row=1,column=1,padx=5,pady=10,sticky="nsew", rowspan=3)
        self.tv_prot_cal_est.add("Protocolo")
        #self.tv_prot_cal_est.add("Calibración")
        self.tv_prot_cal_est.add("Estado")
        self.tv_prot_cal_est._segmented_button.configure(text_color="#ffffff", border_width=1, corner_radius=10, width = 200,height =30, font=ctk.CTkFont(size=20, weight="bold"))

        self.tv_prot_cal_est.tab("Protocolo").grid_columnconfigure(0, weight=1)
        #self.tv_prot_cal_est.tab("Calibración").grid_columnconfigure(0, weight=1)
        self.tv_prot_cal_est.tab("Estado").grid_columnconfigure(0, weight=1)

        self.tv_prot_cal_est.set("Protocolo")

        #self.b_protocolo = ctk.CTkButton(master=self.tv_prot_cal_est.tab("Protocolo"), text="Protocolo")
        #self.b_protocolo.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")



        
        #PROTOCOLO 
        #self.f_protocolo = ctk.CTkFrame(self, fg_color="#1e1e1e",border_color="#4a4c4e", border_width=1, corner_radius=10)   
        #self.f_protocolo.grid(row=1,column=1,padx=5,pady=10,sticky="nsew")
        #self.f_protocolo.grid_columnconfigure(0, weight=1)

        #self.l_protocolo= ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"), bg_color= "transparent",text="Protocolo de Olfatometría", text_color="#458B8D", 
                                       #font=ctk.CTkFont(size=22, weight="bold"))
        #self.l_protocolo.grid(row=0, column=0, padx=5, pady=(20,5), sticky="we")

        #Número de Ciclos
        self.l_num_ciclos = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"), text="Número de ciclos", font=ctk.CTkFont(size=14,weight="bold"))
        self.l_num_ciclos.grid(row=0, column=0, padx=10, pady=(10,2), sticky="we", rowspan=1)
        self.e_num_ciclos =SpinboxCTk(self.tv_prot_cal_est.tab("Protocolo"), valor= 3, valor_max=config.VALOR_MAX_CICLOS, valor_min=config.VALOR_MIN_CICLOS)
        self.e_num_ciclos.grid(row=1, column=0, padx=5, pady=(4,2), sticky="n")
        self.asignar_tooltip_spinbox(self.e_num_ciclos, mensaje_entry="Introduzca el número de ciclos de exposición y desensibilización que se realizarán durante el protocolo.\nCada ciclo consiste en un período de exposición seguido de un período de desensibilización.")

        #Intervalo entreciclos
        self.l_intervalo_ciclos = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"), text="Intervalo entre ciclos (en sec)", font=ctk.CTkFont(size=14,weight="bold"))
        self.l_intervalo_ciclos.grid(row=2, column=0, padx=10, pady=(4,2), sticky="we", rowspan=1)
        self.e_intervalo_ciclos =SpinboxCTk(self.tv_prot_cal_est.tab("Protocolo"), valor= 60, valor_max=config.VALOR_MAX_INTERVALO_CICLOS, valor_min=config.VALOR_MIN_INTERVALO_CICLOS)
        self.e_intervalo_ciclos.grid(row=3, column=0, padx=5, pady=(4,2), sticky="n")
        self.asignar_tooltip_spinbox(self.e_intervalo_ciclos, mensaje_entry="Introduzca el intervalo entre ciclos del protocolo (en segundos).")


        #Tiempo de Exposición
        self.l_tiempo_exposicion = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"), text="Exposición (en sec)", font=ctk.CTkFont(size=14,weight="bold"))
        self.l_tiempo_exposicion.grid(row=4, column=0, padx=10, pady=(4,2), sticky="we")
        self.e_tiempo_exposicion = SpinboxCTk(self.tv_prot_cal_est.tab("Protocolo"), valor=3, valor_max=config.VALOR_MAX_TIEMPO_EXPOSICION, valor_min=config.VALOR_MIN_TIEMPO_EXPOSICION)
        self.e_tiempo_exposicion.grid(row=5, column=0, padx=5, pady=(4,2), sticky="n")
        self.asignar_tooltip_spinbox(self.e_tiempo_exposicion, mensaje_entry="Introduzca el tiempo de exposición (en segundos) de los odorantes introducidos en el protocolo.")


        #Tiempo de Desensibilización
        self.l_tiempo_desensibilizacion = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"), text="Desensibilización (en sec)", font=ctk.CTkFont(size=14,weight="bold"))
        self.l_tiempo_desensibilizacion.grid(row=6, column=0, padx=10, pady=(4,2), sticky="we")
        self.e_tiempo_desensibilizacion = SpinboxCTk(self.tv_prot_cal_est.tab("Protocolo"), valor=30, valor_max=config.VALOR_MAX_TIEMPO_DESENSIBILIZACION, valor_min=config.VALOR_MIN_TIEMPO_DESENSIBILIZACION)
        self.e_tiempo_desensibilizacion.grid(row=7, column=0, padx=5, pady=(4,2), sticky="n")
        self.asignar_tooltip_spinbox(self.e_tiempo_desensibilizacion, mensaje_entry="Introduzca el tiempo de desensibilización (en segundos) entre los odorantes introducidos en el protocolo para la limpieza de los canales y reposo del paciente.")


        #Orden de los canales
        self.l_orden_canales = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"), text="Orden de los canales", font=ctk.CTkFont(size=14,weight="bold"))
        self.l_orden_canales.grid(row=8, column=0, padx=10, pady=(30,5), sticky="n")
        self.cb_secuencial = ctk.CTkCheckBox(self.tv_prot_cal_est.tab("Protocolo"), text="Secuencial", font=ctk.CTkFont(size=14))
        self.cb_secuencial.grid(row=9, column=0, padx=40, pady=(4,2), sticky="w")
        self.cb_secuencial.select()  # Por defecto, el orden de los canales es secuencial
        self.cb_aleatorio = ctk.CTkCheckBox(self.tv_prot_cal_est.tab("Protocolo"), text="Aleatorio", font=ctk.CTkFont(size=14))
        self.cb_aleatorio.grid(row=9, column=0, padx=40, pady=(4,2), sticky="e")
        CTkToolTip(self.cb_aleatorio, message="Seleccione esta opción para que los odorantes se presenten en un orden aleatorio durante el protocolo.", delay=0.5, font=ctk.CTkFont(size=12))
        CTkToolTip(self.cb_secuencial, message="Seleccione esta opción para que los odorantes se presenten en un orden secuencial durante el protocolo.", delay=0.5, font=ctk.CTkFont(size=12))







        #PROTOCOLOS CONOCIDOS/ESTANDARIZADOS 
        #OJO: ME QUEDA MUY LARGO SI NO PUEDO UTILIZAR LA CLASE CTkComboBox DE CUSTOM TKINTER
        #Sniffin Sticks test(identificación, umbral y descriminación)
        #self.comb_protocolos_definidos = stk.def combobox_callback(choice):
            #print('combobox dropdown clicked:', choice)
        """
        self.l_protocolos_definidos= ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"), text="Protocolos definidos", text_color="#ffffff", font=ctk.CTkFont(size=14, weight="bold"))
        self.l_protocolos_definidos.grid(row=11, column=0, padx=10, pady=(20,5), sticky="w")
        sv_protolocos_definidos = ctk.StringVar(value='------')
        comb_protocolos_definidos = ctk.CTkComboBox(self.tv_prot_cal_est.tab("Protocolo"), values=['------','Sniffin Sticks', 'UPSIT', 'CCCRC', 'Snap & Sniff Threshold', 'Q-Sticks', 'Protocolo papers Ángela'],
                                             width=100, height=28, text_color="#ffffff",dropdown_fg_color="#0a5f70", command= self.protocolo_definido, variable=sv_protolocos_definidos)
        comb_protocolos_definidos.grid(row=11, column=0, padx=10, pady=(20,5), sticky="e")
        """
    
        #Inicar protocolo
        self.b_iniciar_protocolo = ctk.CTkButton(self.tv_prot_cal_est.tab("Protocolo"), text="▶", text_color = "#ffffff", fg_color="#85ad75", width=15, height=20, 
        hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=10,command=self.iniciar_protocolo,font=ctk.CTkFont(size=34, weight="bold"))
        self.b_iniciar_protocolo.grid(row=18, column=0, padx=50, pady=(60,5), sticky="w")
        CTkToolTip(self.b_iniciar_protocolo, message="Inicio del protocolo configurado", delay=0.5, font=ctk.CTkFont(size=12))

        
        #Reiniciar protocolo
        self.b_reiniciar_protocolo = ctk.CTkButton(self.tv_prot_cal_est.tab("Protocolo"), text="↻" , text_color = "#ffffff", fg_color="#C7BE19",width=15, height=20, 
                                                   hover_color="#9da31e", border_color="#F6F04F", border_width=1, corner_radius=10,command=self._consulta_reiniciar_protocolo,font=ctk.CTkFont(size=34, weight="bold"))
        self.b_reiniciar_protocolo.grid(row=18, column=0, padx=10, pady=(60,5), sticky="n")
        CTkToolTip(self.b_reiniciar_protocolo, message="Reinicio del protocolo configurado", delay=0.5, font=ctk.CTkFont(size=12))


        #Parar protocolo
        self.b_parar_protocolo = ctk.CTkButton(self.tv_prot_cal_est.tab("Protocolo"), text="◼", text_color = "#ffffff",width=15, height=20, 
        fg_color="#f56a6a", hover_color = "#ee4242", border_color="#ff0000",corner_radius=10,border_width=1, command=self._consulta_parar_protocolo,font=ctk.CTkFont(size=34, weight="bold"))
        self.b_parar_protocolo.grid(row=18, column=0, padx=50, pady=(60,5), sticky="e")
        CTkToolTip(self.b_parar_protocolo, message="Parada del protocolo configurado ya iniciado", delay=0.5, font=ctk.CTkFont(size=12))
        

        #FALTAN INLCUIR PROTOCOLOS ESTANDARIZADOS DE OLFATOMETRÍA (Sniffin' Sticks, etc) Y LA POSIBILIDAD DE CREAR 
        # PROTOCOLOS PERSONALIZADOS

        """
        #CALIBRACIÓN
        # Crea un frame deslizante dentro del tabview
        self.f_calibracion_scroll = ctk.CTkScrollableFrame(self.tv_prot_cal_est.tab("Calibración"), fg_color="transparent")
        self.f_calibracion_scroll.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.tv_prot_cal_est.tab("Calibración").grid_rowconfigure(0, weight=1)
        self.tv_prot_cal_est.tab("Calibración").grid_columnconfigure(0, weight=1)
        self.f_calibracion_scroll.grid_columnconfigure(0, weight=1)
        
        self.l_calibracion = ctk.CTkLabel(self.f_calibracion_scroll, text="Calibración", text_color="#458B8D", font=ctk.CTkFont(size=22, weight="bold"))
        self.l_calibracion.grid(row=0, column=0, padx=10, pady=(10,5), sticky="n")

        # Selección de canales a calibrar
        sv_canales_calibrado = ctk.StringVar(value="Ninguno")
        comb_canales_calibrados = ctk.CTkComboBox(self.f_calibracion_scroll, values=['Ninguno','Canal Amarillo', 'Canal Rojo', 'Canal Verde', 'Canal Azul', 'Canal Blanco', 'Canal Negro'],
                                             width=160, height=36, text_color="#ffffff",command=self.canal_calibrado,dropdown_fg_color="#0a5f70", variable=sv_canales_calibrado)
        comb_canales_calibrados.grid(row=1, column=0, padx=10, pady=(20,5), sticky="n")

        #Calibración Velocidad
        self.l_calibracion_velocidad = ctk.CTkLabel(self.f_calibracion_scroll, text="Velocidad", text_color="#458B8D", font=ctk.CTkFont(size=18, weight="bold"))
        self.l_calibracion_velocidad.grid(row=2, column=0, padx=10, pady=(50,5), sticky="n")

        #Gráfica en tiempo real - Velocidad
        fig_velocidad = Figure(figsize=(10,5),dpi=55)
        self.ax_velocidad = fig_velocidad.add_subplot(111)
        self.ax_velocidad.set_xlabel("Tiempo (s)")
        self.ax_velocidad.set_ylabel("Velocidad (m/s)")
        self.ax_velocidad.plot(self.tiempo_graficas,self.buffer_velocidad)
        fig_velocidad.tight_layout()
        self.canvas_velocidad = FigureCanvasTkAgg(fig_velocidad, master=self.f_calibracion_scroll)
        self.canvas_velocidad.get_tk_widget().grid(row=3, column=0, padx=10, pady=20, sticky="n")
        self.canvas_velocidad.draw()

        self.b_iniciar_calibracion_velocidad = ctk.CTkButton(self.f_calibracion_scroll, text="▶", text_color = "#ffffff", fg_color="#85ad75", width=15, height=20, 
        hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=10,command=self.iniciar_calibrado_velocidad,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibracion_velocidad.grid(row=4, column=0, padx=90, pady=(20,5), sticky="w")
       

        self.b_reiniciar_calibrado_velocidad = ctk.CTkButton(self.f_calibracion_scroll, text="↻" , text_color = "#ffffff", fg_color="#C7BE19",width=15, height=20,
                                                   hover_color="#9da31e", border_color="#F6F04F", border_width=1, corner_radius=10,command=self.reiniciar_calibrado_velocidad,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_velocidad.grid(row=4, column=0, padx=10, pady=(20,5), sticky="n")

        self.b_parar_calibrado_velocidad = ctk.CTkButton(self.f_calibracion_scroll, text="◼", text_color = "#ffffff",width=15, height=20, 
        fg_color="#f56a6a", hover_color = "#ee4242", border_color="#ff0000",corner_radius=10,border_width=1, command=self.parar_calibrado_velocidad,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_velocidad.grid(row=4, column=0, padx=90, pady=(20,5), sticky="e")


        #Calibración Flujo
        self.l_calibracion_flujo = ctk.CTkLabel(self.f_calibracion_scroll, text="Flujo", text_color="#458B8D", font=ctk.CTkFont(size=18, weight="bold"))
        self.l_calibracion_flujo.grid(row=5, column=0, padx=10, pady=(50,5), sticky="n")

        #Gráfica en tiempo real - Flujo
        fig_flujo = Figure(figsize=(10,5),dpi=60)
        self.ax_flujo = fig_flujo.add_subplot(111)
        self.ax_flujo.set_xlabel("Tiempo (s)")
        self.ax_flujo.set_ylabel("Flujo (ml/min)")
        self.ax_flujo.plot(self.tiempo_graficas,self.buffer_flujo)
        fig_flujo.tight_layout()
        self.canvas_flujo = FigureCanvasTkAgg(fig_flujo, master=self.f_calibracion_scroll)
        self.canvas_flujo.get_tk_widget().grid(row=6, column=0, padx=10, pady=(20,5), sticky="n")
        self.canvas_flujo.draw()

        self.b_iniciar_calibracion_flujo = ctk.CTkButton(self.f_calibracion_scroll, text="▶", text_color = "#ffffff", fg_color="#85ad75", width=15, height=20, 
        hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=10,command=self.iniciar_calibrado_flujo,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibracion_flujo.grid(row=7, column=0, padx=90, pady=(20,5), sticky="w")
       

        self.b_reiniciar_calibrado_flujo = ctk.CTkButton(self.f_calibracion_scroll, text="↻" , text_color = "#ffffff", fg_color="#C7BE19",width=15, height=20,
                                                   hover_color="#9da31e", border_color="#F6F04F", border_width=1, corner_radius=10,command=self.reiniciar_calibrado_flujo,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_flujo.grid(row=7, column=0, padx=10, pady=(20,5), sticky="n")

        self.b_parar_calibrado_flujo = ctk.CTkButton(self.f_calibracion_scroll, text="◼", text_color = "#ffffff",width=15, height=20, 
        fg_color="#f56a6a", hover_color = "#ee4242", border_color="#ff0000",corner_radius=10,border_width=1, command=self.parar_calibrado_flujo,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_flujo.grid(row=7, column=0, padx=90, pady=(20,5), sticky="e")



        #Calibración Concentración
        self.l_calibracion_concentracion = ctk.CTkLabel(self.f_calibracion_scroll, text="Concentración", text_color="#458B8D", font=ctk.CTkFont(size=18, weight="bold"))
        self.l_calibracion_concentracion.grid(row=8, column=0, padx=10, pady=(50,5), sticky="n")

        #Gráfica en tiempo real - Concentración
        fig_concentracion = Figure(figsize=(10,5),dpi=60)
        self.ax_concentracion = fig_concentracion.add_subplot(111)
        self.ax_concentracion.set_xlabel("Tiempo (s)")
        self.ax_concentracion.set_ylabel("Concentracion (µg/m\u00B3)")
        self.ax_concentracion.plot(self.tiempo_graficas,self.buffer_concentracion)
        fig_concentracion.tight_layout()
        self.canvas_concentracion = FigureCanvasTkAgg(fig_concentracion, master=self.f_calibracion_scroll)
        self.canvas_concentracion.get_tk_widget().grid(row=9, column=0, padx=10, pady=(20,5), sticky="n")
        self.canvas_concentracion.draw()

        self.b_iniciar_calibracion_concentracion = ctk.CTkButton(self.f_calibracion_scroll, text="▶", text_color = "#ffffff", fg_color="#85ad75", width=15, height=20, 
        hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=10,command=self.iniciar_calibrado_concentracion,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibracion_concentracion.grid(row=10, column=0, padx=90, pady=(20,5), sticky="w")
       

        self.b_reiniciar_calibrado_concentracion = ctk.CTkButton(self.f_calibracion_scroll, text="↻" , text_color = "#ffffff", fg_color="#C7BE19",width=15, height=20,
                                                   hover_color="#9da31e", border_color="#F6F04F", border_width=1, corner_radius=10,command=self.reiniciar_calibrado_concentracion, font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_concentracion.grid(row=10, column=0, padx=10, pady=(20,5), sticky="n")

        self.b_parar_calibrado_concentracion = ctk.CTkButton(self.f_calibracion_scroll, text="◼", text_color = "#ffffff",width=15, height=20, 
        fg_color="#f56a6a", hover_color = "#ee4242", border_color="#ff0000",corner_radius=10,border_width=1, command=self.parar_calibrado_concentracion,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_concentracion.grid(row=10, column=0, padx=90, pady=(20,5), sticky="e")




        #Calibración Latencia
        self.l_calibracion_latencia = ctk.CTkLabel(self.f_calibracion_scroll, text="Latencia", text_color="#458B8D", font=ctk.CTkFont(size=18, weight="bold"))
        self.l_calibracion_latencia.grid(row=11, column=0, padx=10, pady=(50,5), sticky="n")

        #Gráfica en tiempo real - Latencia
        fig_latencia = Figure(figsize=(10,5),dpi=60)
        self.ax_latencia = fig_latencia.add_subplot(111)
        self.ax_concentracion.set_xlabel("Tiempo (s)")
        self.ax_concentracion.set_ylabel("Latencia (ms)")
        fig_latencia.tight_layout()
        self.canvas_latencia = FigureCanvasTkAgg(fig_latencia, master=self.f_calibracion_scroll)
        self.canvas_latencia.get_tk_widget().grid(row=12, column=0, padx=10, pady=(20,5), sticky="n")
        self.canvas_latencia.draw()

        self.b_iniciar_calibracion_latencia = ctk.CTkButton(self.f_calibracion_scroll, text="▶", text_color = "#ffffff", fg_color="#85ad75", width=15, height=20, 
        hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=10,command=self.iniciar_calibrado_latencia,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibracion_latencia.grid(row=13, column=0, padx=90, pady=(20,5), sticky="w")
       

        self.b_reiniciar_calibrado_latencia = ctk.CTkButton(self.f_calibracion_scroll, text="↻" , text_color = "#ffffff", fg_color="#C7BE19",width=15, height=20,
                                                   hover_color="#9da31e", border_color="#F6F04F", border_width=1, corner_radius=10,command=self.reiniciar_calibrado_latencia, font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_latencia.grid(row=13, column=0, padx=10, pady=(20,5), sticky="n")

        self.b_parar_calibrado_latencia = ctk.CTkButton(self.f_calibracion_scroll, text="◼", text_color = "#ffffff",width=15, height=20, 
        fg_color="#f56a6a", hover_color = "#ee4242", border_color="#ff0000",corner_radius=10,border_width=1, command=self.parar_calibrado_latencia,font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_latencia.grid(row=13, column=0, padx=90, pady=(20,5), sticky="e")



        self.actualizar_graficas()



        self.b_iniciar_calibracion = ctk.CTkButton(self.f_calibracion_scroll, text="Iniciar Calibrado General", text_color="#ffffff", fg_color= "#85ad75", width= 15, height=20,
                                                   hover_color="#488f51", border_color="#006400", border_width=1, corner_radius=10,command=self.iniciar_calibrado,font=ctk.CTkFont(size=20, weight="bold"))
        self.b_iniciar_calibracion.grid(row=14, column=0, padx=10, pady=(70,5), sticky="n")

        
        self.b_reiniciar_calibrado = ctk.CTkButton(self.f_calibracion_scroll, text="Reiniciar Calibrado General", text_color="#ffffff", fg_color= "#C7BE19" , width=15, height=20,
                                                   hover_color="#9da31e", border_color="#F6F04F", border_width= 1, corner_radius=10,command=self.reiniciar_calibrado,font=ctk.CTkFont(size=20, weight="bold"))
        self.b_reiniciar_calibrado.grid(row=15, column=0, padx=10, pady=(20,5), sticky="n")


        self.b_parar_calibrado = ctk.CTkButton(self.f_calibracion_scroll, text="Parar Calibrado General", text_color="#ffffff", fg_color= "#f56a6a", width=15, height=20,
                                                   hover_color="#ee4242", border_color="#ff0000", border_width= 1, corner_radius=10,command=self.parar_calibrado,font=ctk.CTkFont(size=20, weight="bold"))
        self.b_parar_calibrado.grid(row=16, column=0, padx=10, pady=(20,5), sticky="n")

        """



        #ESTADO
        #self.f_estado = ctk.CTkFrame(self, fg_color="#1e1e1e",border_color="#4a4c4e", border_width=1, corner_radius=10)
        #self.f_estado.grid(row=3,column=1,padx=5,pady=(0,10),sticky="nsew")
        #self.columnconfigure(0, weight=1)


        #self.l_titulo_estado= ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), text="Estado", text_color="#458B8D", font=ctk.CTkFont(size=22, weight="bold"))
        #self.l_titulo_estado.grid(row=0, column=0, padx=10, pady=(10,5), sticky="n")

        self.l_fecha = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), text=f"Fecha y hora: {time.strftime(config.FORMATO_TIMESTAMP, time.localtime())}", font=ctk.CTkFont(size=14, weight="bold"))
        self.l_fecha.grid(row=0, column=0, padx=10, pady=(20,5), sticky="n")

        
        self.tiempo_inicio_sesion = time.time()  # Variable para almacenar el tiempo de inicio de la sesión
        self.duracion_sesion= ctk.StringVar(value="Duración de sesión: 00:00:00")  # Variable para almacenar la duración de la sesión
        self.l_duracion_sesion = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), textvariable=self.duracion_sesion, font=ctk.CTkFont(size=14, weight="bold"))
        self.l_duracion_sesion.grid(row=1, column=0, padx=10, pady=(20,5), sticky="n")

        self.l_id_sesion = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), text="ID de sesión: ", font=ctk.CTkFont(size=14, weight="bold"))
        self.l_id_sesion.grid(row=4, column=0, padx=71, pady=(20,5), sticky="w")
        self.e_id_sesion= ctk.CTkEntry(self.tv_prot_cal_est.tab("Estado"), placeholder_text="introduzca identificador", font=ctk.CTkFont(size=14))
        self.e_id_sesion.grid(row=4, column=0, padx=71, pady=(20,5), sticky="e")

        self.l_id_paciente = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), text="ID de paciente: ", font=ctk.CTkFont(size=14, weight="bold"))
        self.l_id_paciente.grid(row=5, column=0, padx=65, pady=(20,5), sticky="w")
        self.e_id_paciente= ctk.CTkEntry(self.tv_prot_cal_est.tab("Estado"), placeholder_text="introduzca identificador", font=ctk.CTkFont(size=14))
        self.e_id_paciente.grid(row=5, column=0, padx=65, pady=(20,5), sticky="e")


        #self.actualizar_canales()

        self.sv_latencia_canal= ctk.StringVar(value="0 ms")

        self.l_canal_anterior, self.l_canal_anterior_valor = self._crear_pareja_estado(
            self.tv_prot_cal_est.tab("Estado"), fila=7, texto="Canal anterior: ", textvariable=self.sv_canal_anterior)

        self.l_canal_activo, self.l_canal_activo_valor = self._crear_pareja_estado(
            self.tv_prot_cal_est.tab("Estado"), fila=8, texto="Canal activo: ", textvariable=self.sv_canal_activo)

        self.l_canal_siguiente, self.l_canal_siguiente_valor = self._crear_pareja_estado(
            self.tv_prot_cal_est.tab("Estado"), fila=9, texto="Canal siguiente: ", textvariable=self.sv_canal_siguiente)

        self.l_latencia_canal, self.l_valor_latencia_canal = self._crear_pareja_estado(
            self.tv_prot_cal_est.tab("Estado"), fila=11, texto="Latencia: ", textvariable=self.sv_latencia_canal)

        #self.l_flujo_aire_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), text="Flujo de aire estimado: ", font=ctk.CTkFont(size=14, weight="bold"))
        #self.l_flujo_aire_canal.grid(row=8, column=0, padx=80, pady=(20,5), sticky="w")
        #self.sv_flujo_aire_canal= ctk.StringVar(value="0 ml/min")
        #self.l_valor_flujo_aire_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), textvariable=self.sv_flujo_aire_canal, font=ctk.CTkFont(size=14))
        #self.l_valor_flujo_aire_canal.grid(row=8, column=0, padx=80, pady=(20,5), sticky="e")

        #self.l_concentracion_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), text="Concentración estimada: ", font=ctk.CTkFont(size=14, weight="bold"))
        #self.l_concentracion_canal.grid(row=9, column=0, padx=75, pady=(20,5), sticky="w")
        #self.sv_concentracion_canal= ctk.StringVar(value="0 µg/m\u00B3")
        #self.l_valor_concentracion_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), textvariable=self.sv_concentracion_canal, font=ctk.CTkFont(size=14))
        #self.l_valor_concentracion_canal.grid(row=9, column=0, padx=75, pady=(20,5), sticky="e")   

        """
        self.l_velocidad_motor_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), text="Velocidad motor: ", font=ctk.CTkFont(size=14, weight="bold"))
        self.l_velocidad_motor_canal.grid(row=11, column=0, padx=70, pady=(20,5), sticky="w")
        self.sv_velocidad_motor_canal= ctk.StringVar(value="0 rpm")
        self.l_valor_velocidad_motor_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), textvariable=self.sv_velocidad_motor_canal, font=ctk.CTkFont(size=14))
        self.l_valor_velocidad_motor_canal.grid(row=11, column=0, padx=70, pady=(20,5), sticky="e")
        """

        
        self.b_generar_informe = ctk.CTkButton(self.tv_prot_cal_est.tab("Estado"), text="Generar informe de sesión", fg_color="#5172a4",text_color="#ffffff",
                                       corner_radius=10,border_width=1, border_color="#6ba2f4",command=self.generar_informe,
                                       font=ctk.CTkFont(size=18, weight="bold"))
        self.b_generar_informe.grid(row=13, column=0, padx=31, pady=(30,5), sticky="n")

        #self.l_dispositivo_conectado?


        #Para un botón
        """
        self.button = ctk.CTkButton(self.Frame, text="Pulsar", command=self.button_click,
                                     font= ctk.CTkFont(size=16, weight="bold"),
                                     bg_color="blue", fg_color="white", hover_color="lightblue")
        self.button.grid(row=1, column=0, pady=20, sticky="nesw")
        """
    
    def _crear_pareja_estado(self, tabview, fila, texto, stringvar, pady=(20,5)):
        contenedor = ctk.CTkFrame(tabview, fg_color="transparent")
        contenedor.grid(row=fila, column=0, pady=pady, sticky="n")
        etiqueta = ctk.CTkLabel(contenedor, text=texto, font=ctk.CTkFont(size=14, weight="bold"))
        etiqueta.pack(side="left")
        valor = ctk.CTkLabel(contenedor, textvariable=stringvar, font=ctk.CTkFont(size=14))
        valor.pack(side="left", padx=(4, 0))

        return etiqueta, valor

# ─────────────────────────────────────────────────────────────
#  FUNCIONALIDADES
# ─────────────────────────────────────────────────────────────
    #def buscqueda_esp32(self):

    def button_click(self):
        self.label.configure(text="Botón pulsado")

    def _construir_datos_informe(self):
        return reports.DatosInforme(
                id_sesion = self.e_id_sesion.get(),
                id_paciente = self.e_id_paciente.get(),
                duracion_sesion = self.duracion_sesion.get(),
                tiempo_inicio_sesion = float(self.tiempo_inicio_sesion),
                num_ciclos = self.e_num_ciclos.get(),
                tiempo_exposicion = self.e_tiempo_exposicion.get(),
                tiempo_desensibilizacion = self.e_tiempo_desensibilizacion.get(),
                intervalo_ciclos = self.e_intervalo_ciclos.get(),
                tiempo_calibrado = self.e_tiempo_calibrado.get(),
                historial_sesion = self.historial_sesion,
                metricas_calibracion = self.metricas_calibracion,
                colores_canales = self.colores_canales,
        )
    
    def generar_informe(self):
        
        formatos = [('PDF','*.pdf'),('Excel', '*.xlsx'),('CSV','*.csv')]
        ruta = ctk.filedialog.asksaveasfilename(title='Guardar informe de sesión',
                                                filetypes=formatos, defaultextension=".pdf",
                                                  initialfile=f'Informe_OlfaMetric_{self.e_id_sesion.get()}_{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}')
        if not ruta:
            self.consola.registro("Generación de informe cancelada. No se ha seleccionado ninguna ruta de guardado.", nivel="AVISO")
            return
        
        datos= self._construir_datos_informe()

        self.consola.registro(f'Generando informe en {ruta}....')

        if ruta.endswith('.pdf'):
            try:
                reports.generar_pdf(ruta, datos)
                self.consola.registro(f"InformePDF generado correctamente en {ruta}")
                if self.ruta_archivo_temporal and os.path.exists(self.ruta_archivo_temporal):
                    self.consola.registro(f"Archivo temporal eliminado de: {self.ruta_archivo_temporal}")
                    os.remove(self.ruta_archivo_temporal)  #Se elimina el archivo temporal después de generar el informe
                    #self.ruta_archivo_temporal = None
            except Exception as e:
                import traceback
                self.consola.registro(f'Error al generar informe PDF: {e}', nivel = "ERROR")
                self.consola.registro(traceback.format_exc(), nivel="ERROR")

        elif ruta.endswith('.xlsx'):
            try:
                reports.generar_excel(ruta, datos)
                self.consola.registro(f"Informe Excel generado correctamente en {ruta}")
                if self.ruta_archivo_temporal and os.path.exists(self.ruta_archivo_temporal):
                    self.consola.registro(f"Archivo temporal eliminado de: {self.ruta_archivo_temporal}")
                    os.remove(self.ruta_archivo_temporal)  #Se elimina el archivo temporal después de generar el informe
                    #self.ruta_archivo_temporal = None
            except Exception as e:
                self.consola.registro(f'Error al generar informe Excel: {e}', nivel = "ERROR")

        elif ruta.endswith('.csv'):
            try:
                reports.generar_csv(ruta, datos)
                self.consola.registro(f"Informe CSV generado correctamente en {ruta}")
                if self.ruta_archivo_temporal and os.path.exists(self.ruta_archivo_temporal):
                    self.consola.registro(f"Archivo temporal eliminado de: {self.ruta_archivo_temporal}")
                    os.remove(self.ruta_archivo_temporal)  #Se elimina el archivo temporal después de generar el informe
                    #self.ruta_archivo_temporal = None
            except Exception as e:
                self.consola.registro(f'Error al generar informe CSV: {e}', nivel = "ERROR")

    """
    def generar_csv(self, ruta):
        #Extrae los datos de la UI, llama al módulo reports para generar el CSV y registra la acción en la consola
        try:
            datos = self._construir_datos_informe()
            reports.generar_csv(ruta, datos)
            self.consola.registro(f"CSV generado correctamente en {ruta}")

        except Exception as e:
            self.consola.registro(f"Error al generar CSV: {e}", nivel="ERROR")
    """
    """
    def b_buscar_dispositivos(self):
        if self.ws_client.conectado:
            self.consola.registro("Dispositivo ya conectado")
            return
        self.consola.registro("Reintentando conexión al simulador...")
        self.ws_client.detener()
        self.ws_client.uri = "ws://localhost:8765"
        self.ws_client.iniciar()
    """
    """
    ###OJO ESTA FUNCION PARA CUANDO TENGA EL ESP32 REAL!!!!
    def b_buscar_dispositivos(self):
        self.consola.registro("Buscando dispositivos...")
        self.l_estado_conexion.configure(text="◌ Buscando...", text_color="#f0c060")
        #daemon = True, significa que el hilo se detiene automáticamente cuando se cierra la App
        threading.Thread(target=self.buscar_mdns,daemon=True).start()

        #if self.ws_client.conectado:
            #self.consola.registro("DISPOSITIVO CONECTADO ✔")
        #elif

        #else:
    """

    def iniciar_busqueda_mdns(self):
        self.consola.registro("Buscando dispositivos en la red...")

        def _hilo_busqueda_mdns():
            uri = discovery.buscar_mdns()
            if uri:
                self.after(0,self.conectar_dispositivo_encontrado, uri)
            else:
                self.after(0, self._informar_no_encontrado)

        threading.Thread(target=_hilo_busqueda_mdns, daemon=True).start()

    def _informar_no_encontrado(self):
        self.consola.registro(f'No se encontró ningún dispositivo', nivel = "AVISO")
        self.l_estado_conexion.configure(text="✕ Error",text_color="#fa8989")

    def conectar_dispositivo_encontrado(self,uri):
            #imprime/registra en la consola que se ha encontrado un dispositivo
            self.consola.registro(f'Dispositivo encontrado: {uri}')
            #para la conexión WebSocket actual
            self.ws_client.detener()
            #cambia la URI del cliente WebSocket a la del ESP32 encontrado
            self.ws_client.uri = uri
            #reconecta nuevamente con la nueva URI
            self.ws_client.iniciar()

        
    def tiempo_sesion(self):    
        tiempo = time.strftime(config.FORMATO_HORA, time.gmtime(time.time()-self.tiempo_inicio_sesion))
        self.duracion_sesion.set(f"Duración de sesión: {tiempo}")
        tiempo_local = time.strftime(config.FORMATO_TIMESTAMP, time.localtime())
        self.l_fecha.configure(text=f"Fecha y hora: {tiempo_local}")
        self.after(1000, self.tiempo_sesion)

    def actualizar_comb_canales_calibrados(self):
        valores = [canal.e_olor_canal.get() for canal in self.cuadros_canales if canal.e_olor_canal.get()] 
        valores.append("Canal Blanco")
        self.comb_canales_calibrados.configure(values=valores)

    def bloquear_botones(self,bloquear):
        if bloquear:
            #cabecera
            self.b_buscar_dispositivos.configure(state="disabled")

            #protocolo
            self.e_num_ciclos.b_decrementar.configure(state="disabled")
            self.e_num_ciclos.e_spinbox.configure(state="disabled")
            self.e_num_ciclos.b_incrementar.configure(state="disabled")
            self.e_intervalo_ciclos.b_decrementar.configure(state="disabled")
            self.e_intervalo_ciclos.e_spinbox.configure(state="disabled")
            self.e_intervalo_ciclos.b_incrementar.configure(state="disabled")
            self.e_tiempo_exposicion.b_decrementar.configure(state="disabled")
            self.e_tiempo_exposicion.e_spinbox.configure(state="disabled")
            self.e_tiempo_exposicion.b_incrementar.configure(state="disabled")
            self.e_tiempo_desensibilizacion.b_decrementar.configure(state="disabled")
            self.e_tiempo_desensibilizacion.e_spinbox.configure(state="disabled")
            self.e_tiempo_desensibilizacion.b_incrementar.configure(state="disabled")
            self.cb_aleatorio.configure(state="disabled")
            self.cb_secuencial.configure(state="disabled")
            self.b_iniciar_protocolo.configure(state="disabled")
            self.b_reiniciar_protocolo.configure(state="disabled")
            
            #estado
            self.e_id_sesion.configure(state="disabled")
            self.e_id_paciente.configure(state="disabled")
            self.b_generar_informe.configure(state="disabled")

            #Canales
            for canal in self.cuadros_canales:
                if canal.e_olor_canal.winfo_exists():
                    canal.e_olor_canal.configure(state="disabled")
            self._actualizar_bloqueo_canales_manual()

            #calibrado
            self.comb_canales_calibrados.configure(state="disabled")
            self.b_iniciar_calibrado_general.configure(state="disabled")
            self.b_reiniciar_calibrado_general.configure(state="disabled")
            self.b_parar_calibrado_general.configure(state="disabled")

            self.b_iniciar_calibrado_velocidad.configure(state="disabled")
            self.b_reiniciar_calibrado_velocidad.configure(state="disabled")
            self.b_parar_calibrado_velocidad.configure(state="disabled")
            self.b_iniciar_calibrado_flujo.configure(state="disabled")
            self.b_reiniciar_calibrado_flujo.configure(state="disabled")
            self.b_parar_calibrado_flujo.configure(state="disabled")
            self.b_iniciar_calibrado_concentracion.configure(state="disabled")
            self.b_reiniciar_calibrado_concentracion.configure(state="disabled")  
            self.b_parar_calibrado_concentracion.configure(state="disabled")
            self.b_iniciar_calibrado_latencia.configure(state="disabled")
            self.b_reiniciar_calibrado_latencia.configure(state="disabled")
            self.b_parar_calibrado_latencia.configure(state="disabled")


        else:

            #cabecera
            self.b_buscar_dispositivos.configure(state="normal")

            #protocolo
            self.e_num_ciclos.b_decrementar.configure(state="normal")
            self.e_num_ciclos.e_spinbox.configure(state="normal")
            self.e_num_ciclos.b_incrementar.configure(state="normal")
            self.e_intervalo_ciclos.b_decrementar.configure(state="normal")
            self.e_intervalo_ciclos.e_spinbox.configure(state="normal")
            self.e_intervalo_ciclos.b_incrementar.configure(state="normal")
            self.e_tiempo_exposicion.b_decrementar.configure(state="normal")
            self.e_tiempo_exposicion.e_spinbox.configure(state="normal")
            self.e_tiempo_exposicion.b_incrementar.configure(state="normal")
            self.e_tiempo_desensibilizacion.b_decrementar.configure(state="normal")
            self.e_tiempo_desensibilizacion.e_spinbox.configure(state="normal")
            self.e_tiempo_desensibilizacion.b_incrementar.configure(state="normal")
            self.cb_aleatorio.configure(state="normal")
            self.cb_secuencial.configure(state="normal")
            self.b_iniciar_protocolo.configure(state="normal")
            self.b_reiniciar_protocolo.configure(state="normal")
            
            #estado
            self.e_id_sesion.configure(state="normal")
            self.e_id_paciente.configure(state="normal")
            self.b_generar_informe.configure(state="normal")

            #Canales
            for canal in self.cuadros_canales:
                if canal.e_olor_canal.winfo_exists():
                    canal.e_olor_canal.configure(state="normal")
            self._actualizar_bloqueo_canales_manual()

            #calibrado
            self.comb_canales_calibrados.configure(state="normal")
            self.b_iniciar_calibrado_general.configure(state="normal")
            self.b_reiniciar_calibrado_general.configure(state="normal")
            self.b_parar_calibrado_general.configure(state="normal")

            self.b_iniciar_calibrado_velocidad.configure(state="normal")
            self.b_reiniciar_calibrado_velocidad.configure(state="normal")
            self.b_parar_calibrado_velocidad.configure(state="normal")
            self.b_iniciar_calibrado_flujo.configure(state="normal")
            self.b_reiniciar_calibrado_flujo.configure(state="normal")
            self.b_parar_calibrado_flujo.configure(state="normal")
            self.b_iniciar_calibrado_concentracion.configure(state="normal")
            self.b_reiniciar_calibrado_concentracion.configure(state="normal")  
            self.b_parar_calibrado_concentracion.configure(state="normal")
            self.b_iniciar_calibrado_latencia.configure(state="normal")
            self.b_reiniciar_calibrado_latencia.configure(state="normal")
            self.b_parar_calibrado_latencia.configure(state="normal")

    def iniciar_protocolo(self):
        
        if self.protocolo_activo:
            if self.protocolo_parado:
                self.protocolo_parado = False
                self.consola.registro("Reanudando protocolo...")
                self.b_iniciar_protocolo.configure(state ="disabled")
                self.b_reiniciar_protocolo.configure(state = "disabled")

                if self.fase_actual == "Exposición":
                    canal = self.canales_protocolo[self.indice_canal_protocolo]
                    #self.canal_activo = canal
                    #self.sv_canal_activo.set(self.canal_activo.e_olor_canal.get())
                    # Al reanudar no hace falta esperar ACK de posición: la válvula no se ha
                    # movido durante la pausa (sigue en el mismo canal), así que "rotar" se
                    # envía con 0 pasos y puede no generar confirmación de ejecución.
                    canal.activar_canal(tiempo_inicial = self.tiempo_guardado)
                    self.tiempo_guardado = None
                    self.periodo_exposicion(canal, self.segundos_restantes_protocolo)
                if self.fase_actual == "Desensibilización":
                    #self.canal_activo = self.cuadros_canales[2]
                    #self.sv_canal_activo.set(self.canal_activo.e_olor_canal.get())
                    canal_desensibilizacion = self.cuadros_canales[2] #CANAL DE DESENSIBILIZACIÓN
                    canal_desensibilizacion.activar_canal(tiempo_inicial = self.tiempo_guardado)
                    self.tiempo_guardado = None
                    self.periodo_desensibilizacion(self.segundos_restantes_protocolo)
                if self.fase_actual == "Intervalo":
                    self.canal_activo = None
                    self.sv_canal_activo.set("Ninguno")
                    self.sv_canal_anterior.set("Ninguno")
                    self.sv_canal_siguiente.set("Ninguno")
                    self.periodo_intervalo(self.segundos_restantes_protocolo)
            else:
                self.consola.registro("Ya hay un protocolo activo", nivel="AVISO")
            return
        
        else:
            self.protocolo_activo= True
            canales_con_olor = []

        for canal in self.cuadros_canales:
            if canal.e_olor_canal.get() != "":
                canales_con_olor.append(canal)

        #Validación
        ##ESTOS CONDICIONALES SE LOS PUEDO METER A UNA FUNCIÓN PARA QUE ASEGURE LA VALIDACIÓN DEL PROTOCOLO
        if not canales_con_olor:
            self.consola.registro("No hay ningún canal con olor introducido. Introduzca al menos un olor en uno de los canales para iniciar el protocolo", nivel="AVISO")
            self.protocolo_activo= False
            return
        self.consola.registro(f"{self.e_num_ciclos.get()}")
        if self.e_num_ciclos.get() == 0 or self.e_num_ciclos.get() == "" or self.e_num_ciclos.get() < 0:
            self.consola.registro("El número de ciclos no está definido o es negativo. Defina al menos un ciclo para iniciar el protocolo", nivel="AVISO")
            self.protocolo_activo= False
            return

        if self.e_tiempo_exposicion.get() == 0 or self.e_tiempo_exposicion.get() == "" or self.e_tiempo_exposicion.get() < 0:
            self.consola.registro("El tiempo de exposición no está definido o es negativo. Introduzca la duración del periodo de exposición para iniciar el protocolo", nivel="AVISO")
            self.protocolo_activo= False
            return

        if self.e_tiempo_desensibilizacion.get() == 0 or self.e_tiempo_desensibilizacion.get() == "" or self.e_tiempo_desensibilizacion.get() < 0:
            self.consola.registro("El tiempo de desensibilización no está definido o es negativo. Introduzca la duración del periodo de desensibilización para iniciar el protocolo", nivel="AVISO")
            self.protocolo_activo= False
            return

        if self.cb_aleatorio.get() == 0 and self.cb_secuencial.get() == 0:
            self.consola.registro("No se ha seleccionado el orden de los canales. Seleccione un orden para iniciar el protocolo", nivel="AVISO")
            self.protocolo_activo= False
            return

        if self.cb_aleatorio.get() == 1 and self.cb_secuencial.get() == 1:
            self.consola.registro("No se pueden seleccionar ambos órdenes de canal a la vez. Seleccione un orden para iniciar el protocolo", nivel="AVISO")
            self.protocolo_activo= False
            return

        if self.e_intervalo_ciclos.get() < 0 or self.e_intervalo_ciclos.get() == "":
            self.consola.registro("El intervalo entre ciclos no está definido o es negativo. Introduzca la duración del intervalo entre ciclos para iniciar el protocolo", nivel="AVISO")
            self.protocolo_activo= False
            return

        else:
            self.ciclo_actual = 1
            self.indice_canal_protocolo = 0
            self.segundos_restantes_protocolo = 0
            self.tiempo_guardado = None
            self.fase_actual = None

            if self.cb_aleatorio.get() == 1:
                self.orden_protocolo = "aleatorio"
                self.canales_protocolo = random.sample(canales_con_olor, len(canales_con_olor))
                
            else:
                self.orden_protocolo = "secuencial"
                #hacemos una copia de la lista de olores en el protocolo y no una referencia al objeto que los guarda
                self.canales_protocolo = list(canales_con_olor)

        #ARRANQUE PROTOCOLO
        self.consola.registro(f"Iniciando protocolo {self.orden_protocolo} en {len(self.canales_protocolo)} canales: { [olor.e_olor_canal.get() for olor in self.canales_protocolo] }")
        #self.sv_estado_protocolo.set(f"Ciclo {self.ciclo_actual}/{self.e_num_ciclos.get()} - Canal {self.colores_canales[self.canal_proto_idx]} - Fase: {self.fase_actual or 'N/A'} - Tiempo restante: {self.segundos_restantes}s")
        #self.sv_cuenta_atras.set(f"{self.segundos_restantes}s")
        self.bloquear_botones(bloquear=True)
        self.iniciar_exposicion()

    def iniciar_exposicion(self):   
        if self.indice_canal_protocolo >= len(self.canales_protocolo):
            self.iniciar_intervalo()
            return
        
        canal = self.canales_protocolo[self.indice_canal_protocolo]
        #self.canal_activo = canal
        self.fase_actual = "Exposición"
        self.consola.registro(f"Ciclo {self.ciclo_actual}/{self.e_num_ciclos.get()} Iniciando exposición en canal {canal.e_olor_canal.get()} durante {self.e_tiempo_exposicion.get()} segundos")
        canal.activar_canal()
        if canal.num_canal == self.canal_esperando_posicion:
            self.callbacks_pendientes_posicion_valvula.append((canal.num_canal, self.periodo_exposicion, (canal, int(self.e_tiempo_exposicion.get()))))
        else:
            self.periodo_exposicion(canal, int(self.e_tiempo_exposicion.get()))

    def periodo_exposicion(self, canal, segundos_restantes):
        if self.protocolo_parado:
            self.segundos_restantes_protocolo = segundos_restantes
            return
        
        if segundos_restantes > 0:
            self.segundos_restantes_protocolo = segundos_restantes
            #self.sv_cuenta_atrasc.set(f"{self.segundos_restantes}s")
            self.after_activo = self.after(1000, lambda: self.periodo_exposicion(canal, segundos_restantes - 1))
        else:
            #self.sv_cuenta_atras.set("")
            canal.parar_canal()
            self.iniciar_desensibilizacion()
    
    def iniciar_desensibilizacion(self):
        self.fase_actual = "Desensibilización"
        self.consola.registro(f"Ciclo {self.ciclo_actual}/{self.e_num_ciclos.get()} Iniciando desensibilización durante {self.e_tiempo_desensibilizacion.get()} segundos")
        #self.canal_activo = self.cuadros_canales[2]
        canal_desensibilizacion = self.cuadros_canales[2] #CANAL DE DESENSIBILIZACIÓN
        canal_desensibilizacion.activar_canal()
        if canal_desensibilizacion.num_canal == self.canal_esperando_posicion:
            self.callbacks_pendientes_posicion_valvula.append((canal_desensibilizacion.num_canal, self.periodo_desensibilizacion, (int(self.e_tiempo_desensibilizacion.get()),)))
        else:
            self.periodo_desensibilizacion(int(self.e_tiempo_desensibilizacion.get()))

    def periodo_desensibilizacion(self, segundos_restantes):
        if self.protocolo_parado:
            self.segundos_restantes_protocolo = segundos_restantes
            return
        
        if segundos_restantes > 0:
            #canal.activar_canal()
            self.segundos_restantes_protocolo = segundos_restantes
            #self.sv_cuenta_atras.set(f"{self.segundos_restantes}s")
            self.after_activo = self.after(1000, lambda: self.periodo_desensibilizacion(segundos_restantes - 1))

        else:
            #self.sv_cuenta_atras.set("")
            self.cuadros_canales[2].parar_canal()
            self.indice_canal_protocolo += 1
            self.iniciar_exposicion()

    def iniciar_intervalo(self):
        self.ciclo_actual += 1
        if self.ciclo_actual > int(self.e_num_ciclos.get()):
            self.finalizar_protocolo()
            return
        self.fase_actual = "Intervalo"
        self.indice_canal_protocolo = 0
        self.sv_canal_activo.set("Ninguno")
        self.sv_canal_anterior.set("Ninguno")
        self.sv_canal_siguiente.set("Ninguno")
        self.canal_activo = None
        self.consola.registro(f"Pausa entre ciclos durante: {self.e_intervalo_ciclos.get()} segundos. Ciclo siguiente: {self.ciclo_actual}/{self.e_num_ciclos.get()}")
        self.periodo_intervalo(int(self.e_intervalo_ciclos.get()))


    def periodo_intervalo(self, segundos_restantes):
        if self.protocolo_parado:
            self.segundos_restantes_protocolo = segundos_restantes
            return
        if segundos_restantes > 0:
            self.segundos_restantes_protocolo = segundos_restantes
            #self.sv_cuenta_atras.set(f"{self.segundos_restantes}s")
            self.after_activo = self.after(1000, lambda: self.periodo_intervalo(segundos_restantes - 1))
        else:
            #self.sv_cuenta_atras.set("")
            self.iniciar_exposicion()

    def finalizar_protocolo(self):
        pasos_home = self.posiciones_canales[2]-self.posicion_valvula
        self.ws_client.enviar({"cmd": "rotar", "canal": config.CANAL_BLANCO, "pasos": pasos_home})
        self.posicion_valvula = 0
        self.protocolo_activo = False
        self.protocolo_parado = False
        self.fase_actual = None
        #self.sv_cuenta_atras.set("")
        self.bloquear_botones(bloquear=False)
        self.consola.registro("Protocolo finalizado")

    def _consulta_reiniciar_protocolo(self):
        respuesta = messagebox.askyesno("Reiniciar protocolo", "¿Está seguro de que desea reiniciar el protocolo? Se perderá el progreso de la actual sesion experimental.")
        if respuesta:
            self.reiniciar_protocolo()
            self.consola.registro("Reiniciando protocolo...")
        else:
            self.consola.registro("Reinicio de protocolo cancelado")
    
    def reiniciar_protocolo(self):
        self._cancelar_espera_posicion_valvula(self.periodo_exposicion)
        self._cancelar_espera_posicion_valvula(self.periodo_desensibilizacion)
        for canal in self.cuadros_canales:
            self._cancelar_activacion_pendiente(canal)

        for canal in self.canales_protocolo:
            canal.resetear_cronometro()

        if self.after_activo:
            self.after_cancel(self.after_activo)
            self.after_activo = None

        self.protocolo_activo = False
        self.protocolo_parado = False
        pasos_home = self.posiciones_canales[2]-self.posicion_valvula
        self.ws_client.enviar({"cmd": "rotar", "canal": config.CANAL_BLANCO, "pasos": pasos_home})
        self.posicion_valvula = 0
        self.canal_activo = None
        self.fase_actual = None
        self.segundos_restantes_protocolo = 0
        self.tiempo_guardado = None
        self.indice_canal_protocolo = None
        self.ciclo_actual = 1
        self.canales_protocolo = []
        self.bloquear_botones(bloquear=False)
        self.sv_canal_activo.set("Ninguno")
        self.sv_canal_anterior.set("Ninguno")
        self.sv_canal_siguiente.set("Ninguno")
        self.consola.registro("Protocolo reiniciado")

    def _consulta_parar_protocolo(self):
        respuesta = messagebox.askyesno("Parar protocolo", "¿Está seguro de que desea parar el protocolo? Se pausará el actual progreso de la sesión experimental y podrá reanudarlo posteriormente.")
        if respuesta:
            self.consola.registro("Parando protocolo...")
            self.parar_protocolo()
        else:
            self.consola.registro("Parada de protocolo cancelada")

    def parar_protocolo(self):
        self.protocolo_parado = True
        self._cancelar_espera_posicion_valvula(self.periodo_exposicion)
        self._cancelar_espera_posicion_valvula(self.periodo_desensibilizacion)
        self.b_iniciar_protocolo.configure(state="normal")
        self.b_reiniciar_protocolo.configure(state="normal")
        if self.fase_actual == "Exposición" or self.fase_actual == "Desensibilización":
            self.tiempo_guardado = datetime.datetime.strptime(self.canal_activo.sv_tiempo_activo.get().split()[2], config.FORMATO_HORA)
        #self.consola.registro(self.canal_activo)
        for canal in self.cuadros_canales:
            self._cancelar_activacion_pendiente(canal)
            canal.parar_canal()
        
        self.consola.registro("Protocolo parado")
        # Si estamos en desensibilización, guardar el restante con decimales
        #fase = getattr(self, 'fase_actual', None)
        """
        if fase == "Desensibilización" and getattr(self, 'desens_end_time', None) is not None:
            restante_f = max(0.0, self.desens_end_time - time.time())
            self.segundos_restantes_float = restante_f
            self.segundos_restantes = math.ceil(restante_f)
        if fase == "Exposición" and getattr(self, 'expos_end_time', None) is not None:
            restante_f = max(0.0, self.expos_end_time - time.time())
            self.segundos_restantes_float = restante_f
            self.segundos_restantes = math.ceil(restante_f)
        if fase == "Intervalo" and getattr(self, 'inter_end_time', None) is not None:
            restante_f = max(0.0, self.inter_end_time - time.time())
            self.segundos_restantes_float = restante_f
            self.segundos_restantes = math.ceil(restante_f)
        """

        if self.after_activo:
            #en caso de estar vigente el temporizador activo, cancelamos la llamada pendiente para evitar que se 
            # ejecute después de haber parado el protocolo
            self.after_cancel(self.after_activo)
            self.after_activo = None
        """
        if not self.protocolo_activo:
            self.consola.registro("No hay ningún protocolo activo", nivel="AVISO")
            return
        if self.protocolo_parado
            self.consola.registro()
        if protocolo_activo and 
        """

    #CALIBRADO VELOCIDAD
    def iniciar_calibrado_velocidad(self):
        if self.canal_calibrado is not None:
            self._actualizar_bloqueo_canales_manual()
            if not self.calibrado_velocidad_parado and not self.calibrando_velocidad:
                self.calibrando_velocidad = True
                self.consola.registro("Iniciando calibrado de velocidad...")
                tiempo_calibrado_segundos=int(self.e_tiempo_calibrado.get())*config.MUESTRAS_POR_SEGUNDO_CALIBRACION
                self.tiempo_grafica_velocidad = collections.deque((i * (1/config.MUESTRAS_POR_SEGUNDO_CALIBRACION) for i in range(tiempo_calibrado_segundos)), maxlen=tiempo_calibrado_segundos)
                self.buffer_velocidad = collections.deque([np.nan]*len(self.tiempo_grafica_velocidad), maxlen=len(self.tiempo_grafica_velocidad))
                self.contador_velocidad = 0
                self.buffer_historico_calibrado_velocidad.clear()
                self.b_iniciar_calibrado_velocidad.configure(state="disabled")
                self.b_reiniciar_calibrado_velocidad.configure(state="disabled")
                num_canal = self.canal_calibrado.num_canal
                if num_canal not in self.metricas_calibracion:
                    self.metricas_calibracion[num_canal] = {}
                self.metricas_calibracion[num_canal].setdefault("tiempo_inicio", time.time())
                self.metricas_calibracion[num_canal].setdefault("duracion", self.e_tiempo_calibrado.get())
                self.metricas_calibracion[num_canal].setdefault("olor", self.canal_calibrado.e_olor_canal.get() if self.canal_calibrado.e_olor_canal.winfo_exists() else "----")
                if not self.calibrando_flujo and not self.calibrando_concentracion and not self.calibrando_latencia:
                    self.canal_calibrado.activar_canal()
                if num_canal == self.canal_esperando_posicion:
                    self.callbacks_pendientes_posicion_valvula.append((num_canal, self.periodo_calibrado_velocidad, (self.canal_calibrado, self.e_tiempo_calibrado.get())))
                else:
                    self.periodo_calibrado_velocidad(self.canal_calibrado, self.e_tiempo_calibrado.get())
            else:
                self.calibrado_velocidad_parado = False
                #self.calibrando_velocidad = True
                self.consola.registro("Reanudando calibrado de velocidad...")
                self.consola.registro(f"Tiempo guardado: {self.segundos_restantes_velocidad}")
                #self.canal_calibrado.activar_canal(tiempo_inicial = self.tiempo_guardado)
                self.canal_calibrado.activar_canal()
                #self.tiempo_guardado = None
                self.periodo_calibrado_velocidad(self.canal_calibrado, self.segundos_restantes_velocidad)
                #self.sv_canal_activo.set(self.canal_activo.e_olor_canal.get())
        else:
            self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de velocidad", nivel="AVISO")
            

    def periodo_calibrado_velocidad(self, canal_calibrado, segundos_restantes):
        self.segundos_restantes_velocidad = segundos_restantes
        if segundos_restantes > 0:
            self.consola.registro(f"Calibrado de velocidad en curso... Tiempo restante: {self.segundos_restantes_velocidad}s")
            #self.sv_cuenta_atrasc.set(f"{self.segundos_restantes_velocidad}s")
            self.after_calibrado_velocidad = self.after(1000, lambda: self.periodo_calibrado_velocidad(canal_calibrado, segundos_restantes - 1))
        else:
            #self.sv_cuenta_atras.set("")
            if canal_calibrado is not None:
                canal_calibrado.parar_canal()
            else:
                self.consola.registro("No hay ningún canal seleccionado para calibrar.", nivel="AVISO")
            self.parar_calibrado_velocidad()

    def reiniciar_calibrado_velocidad(self):
        self._cancelar_espera_posicion_valvula(self.periodo_calibrado_velocidad)
        if self.canal_calibrado is not None:
            self._cancelar_activacion_pendiente(self.canal_calibrado)
        self.calibrando_velocidad = False
        self.calibrado_velocidad_parado = False
        self.segundos_restantes_velocidad = 0
        self.contador_velocidad = 0
        self.tiempo_guardado = None
        if self.after_calibrado_velocidad:
            self.after_cancel(self.after_calibrado_velocidad)
            self.after_calibrado_velocidad = None
        if self.canal_calibrado is not None:
            self.canal_calibrado.parar_canal()
        else:
            self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de velocidad.", nivel="AVISO")

        self.buffer_historico_calibrado_velocidad.clear()
        tiempo_calibrado_segundos=int(self.e_tiempo_calibrado.get())*config.MUESTRAS_POR_SEGUNDO_CALIBRACION
        self.tiempo_grafica_velocidad = collections.deque((i * (1/config.MUESTRAS_POR_SEGUNDO_CALIBRACION) for i in range(tiempo_calibrado_segundos)), maxlen=tiempo_calibrado_segundos)
        self.buffer_velocidad = collections.deque([np.nan]*len(self.tiempo_grafica_velocidad), maxlen=len(self.tiempo_grafica_velocidad))
        #self.buffer_velocidad = collections.deque([np.nan]*61, maxlen=61)
        #self.tiempo_grafica_velocidad = collections.deque(list(range(0,61)), maxlen=61)

        self.ax_velocidad.clear()
        self.ax_velocidad.set_xlabel("Tiempo (s)")
        self.ax_velocidad.set_ylabel("Velocidad (m/s)")
        self.ax_velocidad.set_xlim(0,int(self.e_tiempo_calibrado.get()))
        self.ax_velocidad.set_ylim(config.LIMITESY["velocidad"][0],config.LIMITESY["velocidad"][1])  # Ajusta el rango del eje y según tus datos esperados
        self.ax_velocidad.tick_params(colors = "#ffffff") 
        self.ax_velocidad.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
        self.ax_velocidad.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
        self.ax_velocidad.spines['bottom'].set_color('#ffffff')  # Color de la línea del eje x
        self.ax_velocidad.spines['left'].set_color('#ffffff')  # Color de
        self.ax_velocidad.spines['top'].set_color('#ffffff')  # Color de la línea superior
        self.ax_velocidad.spines['right'].set_color('#ffffff')  # Color de la línea derecha
        self.canvas_velocidad.draw()

        self.b_iniciar_calibrado_velocidad.configure(state="normal")
        self._actualizar_bloqueo_canales_manual()
        self.consola.registro("Calibrado de velocidad reiniciado")
    
    def parar_calibrado_velocidad(self):
        if self.calibrando_velocidad:
            self._cancelar_espera_posicion_valvula(self.periodo_calibrado_velocidad)
            self.calibrado_velocidad_parado = True
            #self.calibrando_velocidad = False
            if self.after_calibrado_velocidad:
                self.after_cancel(self.after_calibrado_velocidad)
                self.after_calibrado_velocidad = None
            if self.canal_calibrado is not None:
                #if not self.calibrando_flujo and not self.calibrando_concentracion and not self.calibrando_latencia:
                if not self.calibrado_flujo_parado and not self.calibrado_concentracion_parado and not self.calibrado_latencia_parado:
                    self._cancelar_activacion_pendiente(self.canal_calibrado)
                    self.canal_calibrado.parar_canal()
            else:
                self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de velocidad.", nivel="AVISO")
            self.b_iniciar_calibrado_velocidad.configure(state="normal")
            self.b_reiniciar_calibrado_velocidad.configure(state="normal")

            if self.segundos_restantes_velocidad > 0:
                self.consola.registro(f"Calibrado de velocidad parado con {self.segundos_restantes_velocidad} segundos restantes")

            else:
                if self.canal_calibrado is not None:
                    num_canal = self.canal_calibrado.num_canal
                    if num_canal not in self.metricas_calibracion:
                        self.metricas_calibracion[num_canal] = {}
                        self.metricas_calibracion[num_canal]["olor"] = self.canal_calibrado.e_olor_canal.get() or self.canal_calibrado.color_canal
                    self.metricas_calibracion[num_canal]["velocidad"] = list(self.buffer_historico_calibrado_velocidad)
                    self.calibrando_velocidad = False
                    self.calibrado_velocidad_parado = False
                    self.consola.registro("Calibrado de velocidad finalizado")
                else:
                    self.consola.registro("No se pudieron guardar las métricas de calibrado: No hay ningún canal seleccionado para calibrar.", nivel="AVISO")
            self._actualizar_bloqueo_canales_manual()
        else:
            self.consola.registro("No hay ningún calibrado de velocidad activo. Seleccione un canal y pulse iniciar para comenzar el calibrado de velocidad.", nivel="AVISO")


    #CALIBRADO FLUJO
    def iniciar_calibrado_flujo(self):
        if self.canal_calibrado is not None:
            self._actualizar_bloqueo_canales_manual()
            if not self.calibrado_flujo_parado and not self.calibrando_flujo:
                self.calibrando_flujo = True
                self.consola.registro("Iniciando calibrado de flujo...")
                tiempo_calibrado_segundos=int(self.e_tiempo_calibrado.get())*config.MUESTRAS_POR_SEGUNDO_CALIBRACION
                self.tiempo_grafica_flujo = collections.deque((i * (1/config.MUESTRAS_POR_SEGUNDO_CALIBRACION) for i in range(tiempo_calibrado_segundos)), maxlen=tiempo_calibrado_segundos)
                self.buffer_flujo = collections.deque([np.nan]*len(self.tiempo_grafica_flujo), maxlen=len(self.tiempo_grafica_flujo))
                self.contador_flujo = 0
                self.buffer_historico_calibrado_flujo.clear()
                self.b_iniciar_calibrado_flujo.configure(state="disabled")
                self.b_reiniciar_calibrado_flujo.configure(state="disabled")
                num_canal = self.canal_calibrado.num_canal
                if num_canal not in self.metricas_calibracion:
                    self.metricas_calibracion[num_canal] = {}
                self.metricas_calibracion[num_canal].setdefault("tiempo_inicio", time.time())
                self.metricas_calibracion[num_canal].setdefault("duracion", self.e_tiempo_calibrado.get())
                self.metricas_calibracion[num_canal].setdefault("olor", self.canal_calibrado.e_olor_canal.get() if self.canal_calibrado.e_olor_canal.winfo_exists() else self.canal_calibrado.color_canal)
                if not self.calibrando_velocidad and not self.calibrando_concentracion and not self.calibrando_latencia:
                    self.canal_calibrado.activar_canal()
                if num_canal == self.canal_esperando_posicion:
                    self.callbacks_pendientes_posicion_valvula.append((num_canal, self.periodo_calibrado_flujo, (self.canal_calibrado, self.e_tiempo_calibrado.get())))
                else:
                    self.periodo_calibrado_flujo(self.canal_calibrado, self.e_tiempo_calibrado.get())
            else:
                self.calibrado_flujo_parado = False
                #self.calibrando_flujo = True
                self.consola.registro("Reanudando calibrado de flujo...")
                self.consola.registro(f"Tiempo guardado: {self.segundos_restantes_flujo}")
                #self.canal_calibrado.activar_canal(tiempo_inicial = self.tiempo_guardado)
                self.canal_calibrado.activar_canal()
                #self.tiempo_guardado = None
                self.periodo_calibrado_flujo(self.canal_calibrado, self.segundos_restantes_flujo)
                #self.sv_canal_activo.set(self.canal_activo.e_olor_canal.get())
        else:
            self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de flujo", nivel="AVISO")
            
        
    def periodo_calibrado_flujo(self, canal_calibrado, segundos_restantes):
        self.segundos_restantes_flujo = segundos_restantes
        if segundos_restantes > 0:
            self.consola.registro(f"Calibrado de flujo en curso... Tiempo restante: {self.segundos_restantes_flujo}s")
            #self.sv_cuenta_atrasc.set(f"{self.segundos_restantes_flujo}s")
            self.after_calibrado_flujo = self.after(1000, lambda: self.periodo_calibrado_flujo(canal_calibrado, segundos_restantes - 1))
        else:
            #self.sv_cuenta_atras.set("")
            if canal_calibrado is not None:
                canal_calibrado.parar_canal()
            else:
                self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de flujo.", nivel="AVISO")
            self.parar_calibrado_flujo()

    def reiniciar_calibrado_flujo(self):
        self._cancelar_espera_posicion_valvula(self.periodo_calibrado_flujo)
        if self.canal_calibrado is not None:
            self._cancelar_activacion_pendiente(self.canal_calibrado)
        self.calibrando_flujo = False
        self.calibrado_flujo_parado = False
        self.segundos_restantes_flujo = 0
        self.contador_flujo = 0
        self.tiempo_guardado = None
        if self.after_calibrado_flujo:
            self.after_cancel(self.after_calibrado_flujo)
            self.after_calibrado_flujo = None
        if self.canal_calibrado is not None:
            self.canal_calibrado.parar_canal()
        else:
            self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de flujo.", nivel="AVISO")


        self.buffer_historico_calibrado_flujo.clear()
        tiempo_calibrado_segundos=int(self.e_tiempo_calibrado.get())*config.MUESTRAS_POR_SEGUNDO_CALIBRACION
        self.tiempo_grafica_flujo = collections.deque((i * (1/config.MUESTRAS_POR_SEGUNDO_CALIBRACION) for i in range(tiempo_calibrado_segundos)), maxlen=tiempo_calibrado_segundos)
        self.buffer_flujo = collections.deque([np.nan]*len(self.tiempo_grafica_flujo), maxlen=len(self.tiempo_grafica_flujo))

        self.ax_flujo.clear()
        self.ax_flujo.set_xlim(0,int(self.e_tiempo_calibrado.get()))
        self.ax_flujo.set_ylim(config.LIMITESY["flujo"][0],config.LIMITESY["flujo"][1])  # Ajusta el rango del eje y según tus datos esperados
        self.ax_flujo.set_xlabel("Tiempo (s)")
        self.ax_flujo.set_ylabel("Flujo (l/min)")
        self.ax_flujo.tick_params(colors = "#ffffff") 
        self.ax_flujo.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
        self.ax_flujo.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
        self.ax_flujo.spines['bottom'].set_color('#ffffff')  # Color de la línea del eje x
        self.ax_flujo.spines['left'].set_color('#ffffff')  # Color de
        self.ax_flujo.spines['top'].set_color('#ffffff')  # Color de la línea superior
        self.ax_flujo.spines['right'].set_color('#ffffff')  # Color de la línea derecha
        self.canvas_flujo.draw()

        self.b_iniciar_calibrado_flujo.configure(state="normal")
        self._actualizar_bloqueo_canales_manual()
        self.consola.registro("Calibrado de flujo reiniciado")
    
    def parar_calibrado_flujo(self):
        if self.calibrando_flujo:
            self._cancelar_espera_posicion_valvula(self.periodo_calibrado_flujo)
            self.calibrado_flujo_parado = True
            #self.calibrando_flujo = False
            if self.after_calibrado_flujo:
                self.after_cancel(self.after_calibrado_flujo)
                self.after_calibrado_flujo = None
            if self.canal_calibrado is not None:
                if not self.calibrado_velocidad_parado and not self.calibrado_concentracion_parado and not self.calibrado_latencia_parado:
                    self._cancelar_activacion_pendiente(self.canal_calibrado)
                    self.canal_calibrado.parar_canal()
            else:
                self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de flujo.", nivel="AVISO")
            self.b_iniciar_calibrado_flujo.configure(state="normal")
            self.b_reiniciar_calibrado_flujo.configure(state="normal")

            if self.segundos_restantes_flujo > 0:
                #self.tiempo_guardado = datetime.datetime.strptime(int(self.e_tiempo_calibrado.get()) - self.segundos_restantes, "%H:%M:%S")
                #self.consola.registro(f"{self.tiempo_guardado}")
                self.consola.registro(f"Calibrado de flujo parado con {self.segundos_restantes_flujo} segundos restantes")
        
            else:
                if self.canal_calibrado is not None:
                    num_canal = self.canal_calibrado.num_canal
                    if num_canal not in self.metricas_calibracion:
                        self.metricas_calibracion[num_canal] = {}
                        self.metricas_calibracion[num_canal]["olor"] = self.canal_calibrado.e_olor_canal.get() or self.canal_calibrado.color_canal
                    self.metricas_calibracion[num_canal]["flujo"] = list(self.buffer_historico_calibrado_flujo)
                    self.calibrando_flujo = False
                    self.calibrado_flujo_parado = False
                    self.consola.registro("Calibrado de flujo finalizado")
                else:
                    self.consola.registro("No se pudieron guardar las métricas de calibrado: No hay ningún canal seleccionado para calibrar.", nivel="AVISO")
            self._actualizar_bloqueo_canales_manual()
        else:
            self.consola.registro("No hay ningún calibrado activo. Seleccione un canal y pulse iniciar para comenzar el calibrado de flujo.", nivel="AVISO")

    #CALIBRADO CONCENTRACIÓN
    def iniciar_calibrado_concentracion(self):
        if self.canal_calibrado is not None:
            self._actualizar_bloqueo_canales_manual()
            if not self.calibrado_concentracion_parado and not self.calibrando_concentracion:
                self.calibrando_concentracion = True
                self.consola.registro("Iniciando calibrado de concentración...")
                tiempo_calibrado_segundos=int(self.e_tiempo_calibrado.get())*config.MUESTRAS_POR_SEGUNDO_CALIBRACION
                self.tiempo_grafica_concentracion = collections.deque((i * (1/config.MUESTRAS_POR_SEGUNDO_CALIBRACION) for i in range(tiempo_calibrado_segundos)), maxlen=tiempo_calibrado_segundos)
                self.buffer_concentracion = collections.deque([np.nan]*len(self.tiempo_grafica_concentracion), maxlen=len(self.tiempo_grafica_concentracion))
                self.contador_concentracion = 0
                self.buffer_historico_calibrado_concentracion.clear()
                self.b_iniciar_calibrado_concentracion.configure(state="disabled")
                self.b_reiniciar_calibrado_concentracion.configure(state="disabled")
                num_canal = self.canal_calibrado.num_canal
                if num_canal not in self.metricas_calibracion:
                    self.metricas_calibracion[num_canal] = {}
                self.metricas_calibracion[num_canal].setdefault("tiempo_inicio", time.time())
                self.metricas_calibracion[num_canal].setdefault("duracion", self.e_tiempo_calibrado.get())
                self.metricas_calibracion[num_canal].setdefault("olor", self.canal_calibrado.e_olor_canal.get() if self.canal_calibrado.e_olor_canal.winfo_exists() else self.canal_calibrado.color_canal)
                if not self.calibrando_flujo and not self.calibrando_velocidad and not self.calibrando_latencia:
                    self.canal_calibrado.activar_canal()
                if num_canal == self.canal_esperando_posicion:
                    self.callbacks_pendientes_posicion_valvula.append((num_canal, self.periodo_calibrado_concentracion, (self.canal_calibrado, self.e_tiempo_calibrado.get())))
                else:
                    self.periodo_calibrado_concentracion(self.canal_calibrado, self.e_tiempo_calibrado.get())
            else:
                self.calibrado_concentracion_parado = False
                #self.calibrando_concentracion = True
                self.consola.registro("Reanudando calibrado de concentración...")
                self.consola.registro(f"Tiempo guardado: {self.segundos_restantes_concentracion}")
                #self.canal_calibrado.activar_canal(tiempo_inicial = self.tiempo_guardado)
                self.canal_calibrado.activar_canal()
                #self.tiempo_guardado = None
                self.periodo_calibrado_concentracion(self.canal_calibrado, self.segundos_restantes_concentracion)
                #self.sv_canal_activo.set(self.canal_activo.e_olor_canal.get())
        else:
            self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de concentración", nivel="AVISO")
            
        
    def periodo_calibrado_concentracion(self, canal_calibrado, segundos_restantes):
        self.segundos_restantes_concentracion = segundos_restantes
        if segundos_restantes > 0:
            self.consola.registro(f"Calibrado de concentración en curso... Tiempo restante: {self.segundos_restantes_concentracion}s")
            #self.sv_cuenta_atrasc.set(f"{self.segundos_restantes}s")
            self.after_calibrado_concentracion = self.after(1000, lambda: self.periodo_calibrado_concentracion(canal_calibrado, segundos_restantes - 1))
        else:
            #self.sv_cuenta_atras.set("")
            if canal_calibrado is not None:
                canal_calibrado.parar_canal()
            else:
                self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de concentración.", nivel="AVISO")
            self.parar_calibrado_concentracion()

    def reiniciar_calibrado_concentracion(self):
        self._cancelar_espera_posicion_valvula(self.periodo_calibrado_concentracion)
        if self.canal_calibrado is not None:
            self._cancelar_activacion_pendiente(self.canal_calibrado)
        self.calibrando_concentracion = False
        self.calibrado_concentracion_parado = False
        self.segundos_restantes_concentracion = 0
        self.contador_concentracion = 0
        self.tiempo_guardado = None
        if self.after_calibrado_concentracion:
            self.after_cancel(self.after_calibrado_concentracion)
            self.after_calibrado_concentracion = None
        if self.canal_calibrado is not None:
            self.canal_calibrado.parar_canal()
        else:
            self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de concentración.", nivel="AVISO")



        self.buffer_historico_calibrado_concentracion.clear()
        tiempo_calibrado_segundos=int(self.e_tiempo_calibrado.get())*config.MUESTRAS_POR_SEGUNDO_CALIBRACION
        self.tiempo_grafica_concentracion = collections.deque((i * (1/config.MUESTRAS_POR_SEGUNDO_CALIBRACION) for i in range(tiempo_calibrado_segundos)), maxlen=tiempo_calibrado_segundos)
        self.buffer_concentracion = collections.deque([np.nan]*len(self.tiempo_grafica_concentracion), maxlen=len(self.tiempo_grafica_concentracion))

        self.ax_concentracion.clear()
        self.ax_concentracion.set_xlim(0,int(self.e_tiempo_calibrado.get()))
        self.ax_concentracion.set_ylim(config.LIMITESY["concentracion"][0],config.LIMITESY["concentracion"][1])  # Ajusta el rango del eje y según tus datos esperados
        self.ax_concentracion.set_xlabel("Tiempo (s)")
        self.ax_concentracion.set_ylabel("Concentración (ppm)")
        self.ax_concentracion.tick_params(colors = "#ffffff") 
        self.ax_concentracion.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
        self.ax_concentracion.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
        self.ax_concentracion.spines['bottom'].set_color('#ffffff')  # Color de la línea del eje x
        self.ax_concentracion.spines['left'].set_color('#ffffff')  # Color de
        self.ax_concentracion.spines['top'].set_color('#ffffff')  # Color de la línea superior
        self.ax_concentracion.spines['right'].set_color('#ffffff')  # Color de la línea derecha
        self.canvas_concentracion.draw()

        self.b_iniciar_calibrado_concentracion.configure(state="normal")
        self._actualizar_bloqueo_canales_manual()
        self.consola.registro("Calibrado de concentración reiniciado")

    def parar_calibrado_concentracion(self):
        if self.calibrando_concentracion:
            self._cancelar_espera_posicion_valvula(self.periodo_calibrado_concentracion)
            self.calibrado_concentracion_parado = True
            #self.calibrando_concentracion = False
            if self.after_calibrado_concentracion:
                self.after_cancel(self.after_calibrado_concentracion)
                self.after_calibrado_concentracion = None
            if self.canal_calibrado is not None:
                if not self.calibrado_flujo_parado and not self.calibrado_velocidad_parado and not self.calibrado_latencia_parado:
                    self._cancelar_activacion_pendiente(self.canal_calibrado)
                    self.canal_calibrado.parar_canal()
            else:
                self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de concentración.", nivel="AVISO")
            self.b_iniciar_calibrado_concentracion.configure(state="normal")
            self.b_reiniciar_calibrado_concentracion.configure(state="normal")

            if self.segundos_restantes_concentracion > 0:
                #self.tiempo_guardado = datetime.datetime.strptime(int(self.e_tiempo_calibrado.get()) - self.segundos_restantes, "%H:%M:%S")
                #self.consola.registro(f"{self.tiempo_guardado}")
                self.consola.registro(f"Calibrado de concentración parado con {self.segundos_restantes_concentracion} segundos restantes")

        
            else:
                if self.canal_calibrado is not None:
                    num_canal = self.canal_calibrado.num_canal
                    if num_canal not in self.metricas_calibracion:
                        self.metricas_calibracion[num_canal] = {}
                        self.metricas_calibracion[num_canal]["olor"] = self.canal_calibrado.e_olor_canal.get() or self.canal_calibrado.color_canal
                    self.metricas_calibracion[num_canal]["concentracion"] = list(self.buffer_historico_calibrado_concentracion)
                    self.calibrando_concentracion = False
                    self.calibrado_concentracion_parado = False
                    self.consola.registro("Calibrado de concentración finalizado")
                else:
                    self.consola.registro("No se pudieron guardar las métricas de calibrado: No hay ningún canal seleccionado para calibrar.", nivel="AVISO")
            self._actualizar_bloqueo_canales_manual()
        else:
            self.consola.registro("No hay ningún calibrado activo. Seleccione un canal y pulse iniciar para comenzar el calibrado de concentración.", nivel="AVISO")

    #CALIBRADO LATENCIA
    def iniciar_calibrado_latencia(self):
        if self.canal_calibrado is not None:
            self._actualizar_bloqueo_canales_manual()
            if not self.calibrado_latencia_parado and not self.calibrando_latencia:
                self.calibrando_latencia = True
                self.consola.registro("Iniciando calibrado de latencia...")
                tiempo_calibrado_segundos=int(self.e_tiempo_calibrado.get())*config.MUESTRAS_POR_SEGUNDO_CALIBRACION
                self.tiempo_grafica_latencia = collections.deque((i * (1/config.MUESTRAS_POR_SEGUNDO_CALIBRACION) for i in range(tiempo_calibrado_segundos)), maxlen=tiempo_calibrado_segundos)
                self.buffer_latencia = collections.deque([np.nan]*len(self.tiempo_grafica_latencia), maxlen=len(self.tiempo_grafica_latencia))
                self.contador_latencia = 0
                self.buffer_historico_calibrado_latencia.clear()
                self.b_iniciar_calibrado_latencia.configure(state="disabled")
                self.b_reiniciar_calibrado_latencia.configure(state="disabled")
                num_canal = self.canal_calibrado.num_canal
                if num_canal not in self.metricas_calibracion:
                    self.metricas_calibracion[num_canal] = {}
                self.metricas_calibracion[num_canal].setdefault("tiempo_inicio", time.time())
                self.metricas_calibracion[num_canal].setdefault("duracion", self.e_tiempo_calibrado.get())
                self.metricas_calibracion[num_canal].setdefault("olor", self.canal_calibrado.e_olor_canal.get() if self.canal_calibrado.e_olor_canal.winfo_exists() else self.canal_calibrado.color_canal)
                if not self.calibrando_flujo and not self.calibrando_concentracion and not self.calibrando_velocidad:
                    self.canal_calibrado.activar_canal()
                if num_canal == self.canal_esperando_posicion:
                    self.callbacks_pendientes_posicion_valvula.append((num_canal, self.periodo_calibrado_latencia, (self.canal_calibrado, self.e_tiempo_calibrado.get())))
                else:
                    self.periodo_calibrado_latencia(self.canal_calibrado, self.e_tiempo_calibrado.get())
            else:
                self.calibrado_latencia_parado = False
                #self.calibrando_latencia = True
                self.consola.registro("Reanudando calibrado de latencia...")
                self.consola.registro(f"Tiempo guardado: {self.segundos_restantes_latencia}")
                #self.canal_calibrado.activar_canal(tiempo_inicial = self.tiempo_guardado)
                self.canal_calibrado.activar_canal()
                #self.tiempo_guardado = None
                self.periodo_calibrado_latencia(self.canal_calibrado, self.segundos_restantes_latencia)
                #self.sv_canal_activo.set(self.canal_activo.e_olor_canal.get())
        else:
            self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de latencia", nivel="AVISO")
            

    def periodo_calibrado_latencia(self, canal_calibrado, segundos_restantes):
        self.segundos_restantes_latencia = segundos_restantes
        if segundos_restantes > 0:
            self.consola.registro(f"Calibrado de latencia en curso... Tiempo restante: {self.segundos_restantes_latencia}s")
            #self.sv_cuenta_atrasc.set(f"{self.segundos_restantes_latencia}s")
            self.after_calibrado_latencia = self.after(1000, lambda: self.periodo_calibrado_latencia(canal_calibrado, segundos_restantes - 1))
        else:
            #self.sv_cuenta_atras.set("")
            if canal_calibrado is not None:
                canal_calibrado.parar_canal()
            else:
                self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de latencia.", nivel="AVISO")
            self.parar_calibrado_latencia()

    def reiniciar_calibrado_latencia(self):
        self._cancelar_espera_posicion_valvula(self.periodo_calibrado_latencia)
        if self.canal_calibrado is not None:
            self._cancelar_activacion_pendiente(self.canal_calibrado)
        self.calibrando_latencia = False
        self.calibrado_latencia_parado = False
        self.segundos_restantes_latencia = 0
        self.contador_latencia = 0
        self.tiempo_guardado = None
        if self.after_calibrado_latencia:
            self.after_cancel(self.after_calibrado_latencia)
            self.after_calibrado_latencia = None
        if self.canal_calibrado is not None:
            self.canal_calibrado.parar_canal()
        else:
            self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de latencia.", nivel="AVISO")


        self.buffer_historico_calibrado_latencia.clear()
        tiempo_calibrado_segundos=int(self.e_tiempo_calibrado.get())*config.MUESTRAS_POR_SEGUNDO_CALIBRACION
        self.tiempo_grafica_latencia = collections.deque((i * (1/config.MUESTRAS_POR_SEGUNDO_CALIBRACION) for i in range(tiempo_calibrado_segundos)), maxlen=tiempo_calibrado_segundos)
        self.buffer_latencia = collections.deque([np.nan]*len(self.tiempo_grafica_latencia), maxlen=len(self.tiempo_grafica_latencia))

        self.ax_latencia.clear()
        self.ax_latencia.set_xlim(0,int(self.e_tiempo_calibrado.get()))
        self.ax_latencia.set_ylim(config.LIMITESY["latencia"][0],config.LIMITESY["latencia"][1])  # Ajusta el rango del eje y según tus datos esperados
        self.ax_latencia.set_xlabel("Tiempo (s)")
        self.ax_latencia.set_ylabel("Latencia (ms)")
        self.ax_latencia.tick_params(colors = "#ffffff") 
        self.ax_latencia.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
        self.ax_latencia.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
        self.ax_latencia.spines['bottom'].set_color('#ffffff')  # Color de la línea del eje x
        self.ax_latencia.spines['left'].set_color('#ffffff')  # Color de
        self.ax_latencia.spines['top'].set_color('#ffffff')  # Color de la línea superior
        self.ax_latencia.spines['right'].set_color('#ffffff')  # Color de la línea derecha
        self.canvas_latencia.draw()

        self.b_iniciar_calibrado_latencia.configure(state="normal")
        self._actualizar_bloqueo_canales_manual()
        self.consola.registro("Calibrado de latencia reiniciado")

    def parar_calibrado_latencia(self):
        if self.calibrando_latencia:
            self._cancelar_espera_posicion_valvula(self.periodo_calibrado_latencia)
            self.calibrado_latencia_parado = True
            #self.calibrando_latencia = False
            if self.after_calibrado_latencia:
                self.after_cancel(self.after_calibrado_latencia)
                self.after_calibrado_latencia = None
            if self.canal_calibrado is not None:
                if not self.calibrado_flujo_parado and not self.calibrado_concentracion_parado and not self.calibrado_velocidad_parado:
                    self._cancelar_activacion_pendiente(self.canal_calibrado)
                    self.canal_calibrado.parar_canal()
            else:
                self.consola.registro("No hay ningún canal seleccionado para calibrar. Seleccione un canal para iniciar el calibrado de latencia.", nivel="AVISO")
            self.b_iniciar_calibrado_latencia.configure(state="normal")
            self.b_reiniciar_calibrado_latencia.configure(state="normal")

            if self.segundos_restantes_latencia > 0:
                #self.tiempo_guardado = datetime.datetime.strptime(int(self.e_tiempo_calibrado.get()) - self.segundos_restantes, "%H:%M:%S")
                #self.consola.registro(f"{self.tiempo_guardado}")
                self.consola.registro(f"Calibrado de latencia parado con {self.segundos_restantes_latencia} segundos restantes")
        
            else:
                if self.canal_calibrado is not None:
                    num_canal = self.canal_calibrado.num_canal
                    if num_canal not in self.metricas_calibracion:
                        self.metricas_calibracion[num_canal] = {}
                        self.metricas_calibracion[num_canal]["olor"] = self.canal_calibrado.e_olor_canal.get() or self.canal_calibrado.color_canal
                    self.metricas_calibracion[num_canal]["latencia"] = list(self.buffer_historico_calibrado_latencia)
                    self.calibrando_latencia = False
                    self.calibrado_latencia_parado = False
                    self.consola.registro("Calibrado de latencia finalizado")
                else:
                    self.consola.registro("No se pudieron guardar las métricas de calibrado: No hay ningún canal seleccionado para calibrar.", nivel="AVISO")
            self._actualizar_bloqueo_canales_manual()
        else:
            self.consola.registro("No hay ningún calibrado activo. Seleccione un canal y pulse iniciar para comenzar el calibrado de latencia.", nivel="AVISO")


    def iniciar_calibrado_general(self):
        self.iniciar_calibrado_velocidad()
        self.iniciar_calibrado_flujo()
        self.iniciar_calibrado_concentracion()
        self.iniciar_calibrado_latencia()

    def _consultar_reiniciar_calibrado_general(self):
        if self.calibrando_velocidad or self.calibrando_flujo or self.calibrando_concentracion or self.calibrando_latencia:
            respuesta = messagebox.askyesno("Reiniciar calibrado general", "¿Está seguro de que desea reiniciar el calibrado general? Se reiniciará el calibrado de todos los canales y se perderán los datos de la actual sesión experimental.")
            if respuesta:
                self.consola.registro("Reiniciando calibrado general...")
                self.reiniciar_calibrado_general()
                self.consola.registro("Calibrado general reiniciado.")
            else:
                self.consola.registro("Reinicio de calibrado general cancelado.")
        else:
            self.consola.registro("No hay ningún calibrado activo. Seleccione un canal y pulse iniciar para comenzar el calibrado.", nivel="AVISO")
    def reiniciar_calibrado_general(self):
        self.reiniciar_calibrado_velocidad()
        self.reiniciar_calibrado_flujo()
        self.reiniciar_calibrado_concentracion()
        self.reiniciar_calibrado_latencia()

    def _consultar_parar_calibrado_general(self):
        if self.calibrando_velocidad or self.calibrando_flujo or self.calibrando_concentracion or self.calibrando_latencia:
            respuesta = messagebox.askyesno("Parar calibrado general", "¿Está seguro de que desea parar el calibrado general? Se pausará el calibrado de todos los canales y se podrá reanudar más tarde.")
            if respuesta:
                self.consola.registro("Parando calibrado general...")
                self.parar_calibrado_general()
                self.consola.registro("Calibrado general parado.")
            else:
                self.consola.registro("Parada de calibrado general cancelada.")
        else:
            self.consola.registro("No hay ningún calibrado activo. Seleccione un canal y pulse iniciar para comenzar el calibrado.", nivel="AVISO")

    def parar_calibrado_general(self):
        self.parar_calibrado_velocidad()
        self.parar_calibrado_flujo()
        self.parar_calibrado_concentracion()
        self.parar_calibrado_latencia()

    def protocolo_definido(self,protocolo):
        if protocolo != '------':
            self.consola.registro(f'Protolo definido seleccionado: {protocolo}')
        else:
            self.consola.registro(f'Prorocolo definido no seleccionado')
    
    def seleccionar_calibrado(self,nombre_canal):
        if not self.calibrado_activo():
            if nombre_canal != 'Ninguno':

                #se reinician los contadores y búfers temporales
                self.contador_concentracion = 0
                self.contador_flujo = 0
                self.contador_velocidad = 0
                self.contador_latencia = 0
                self.buffer_concentracion =  collections.deque([np.nan]*config.TAMANO_BUFFER_GRAFICAS,maxlen=config.TAMANO_BUFFER_GRAFICAS)
                self.buffer_flujo =  collections.deque([np.nan]*config.TAMANO_BUFFER_GRAFICAS,maxlen=config.TAMANO_BUFFER_GRAFICAS)
                self.buffer_latencia =  collections.deque([np.nan]*config.TAMANO_BUFFER_GRAFICAS,maxlen=config.TAMANO_BUFFER_GRAFICAS)
                self.buffer_velocidad =  collections.deque([np.nan]*config.TAMANO_BUFFER_GRAFICAS,maxlen=config.TAMANO_BUFFER_GRAFICAS)


                self.consola.registro(f'Canal calibrado seleccionado: {nombre_canal}')
                for canal in self.cuadros_canales:
                    if canal.e_olor_canal.get() == nombre_canal or canal.l_color_canal.cget("text") == nombre_canal:
                        self.canal_calibrado = canal
            else:
                self.consola.registro(f'Canal calibrado no seleccionado')

        else:   
            self.comb_canales_calibrados.configure(state = "disabled")
        
                
    def calibrado_activo(self):
        return (self.calibrando_velocidad or self.calibrando_flujo or
                self.calibrando_concentracion or self.calibrando_latencia)

    def _cancelar_espera_posicion_valvula(self, funcion_periodo_en_espera):
        # Retira de la cola de espera la llamada periodo pendiente, si seguía pendiente.
        self.callbacks_pendientes_posicion_valvula = [
            (num_canal, funcion, argumentos) for num_canal, funcion, argumentos in self.callbacks_pendientes_posicion_valvula
            if funcion != funcion_periodo_en_espera
        ]

    def _actualizar_bloqueo_canales_manual(self):
        # Bloquea los botones "Activar"/"Parar" de los canales mientras haya un protocolo
        # o un calibrado en curso, para evitar activaciones manuales que interfieran con
        # el proceso en marcha. Se recalcula cada vez a partir del estado actual, así que
        # es seguro llamarlo desde cualquier punto de inicio/parada/reinicio del calibrado.
        if self.protocolo_activo or self.calibrado_activo():
            for canal in self.cuadros_canales:
                canal.b_activar_canal.configure(state="disabled")
                canal.b_parar_canal.configure(state="disabled")
        else:
            for canal in self.cuadros_canales:
                canal.b_activar_canal.configure(state="normal")
                canal.b_parar_canal.configure(state="normal")

    def _cancelar_activacion_pendiente(self, canal):
        # Retira la activación (motor + cronómetro) pendiente para este canal concreto,
        # para que un ACK de rotación que llegue tarde no reactive un canal que ya se paró.
        self.callbacks_pendientes_posicion_valvula = [
            (num_canal, funcion, argumentos) for num_canal, funcion, argumentos in self.callbacks_pendientes_posicion_valvula
            if not (funcion == self._completar_activacion_canal and num_canal == canal.num_canal)
        ]

    def _completar_activacion_canal(self, canal):
        # Se llama una vez el ESP32 confirma que la válvula ha llegado a la posición de
        # este canal: recién entonces se enciende el motor y arranca el cronómetro de
        # "tiempo activo" del canal (ver actualizar_canales() y widgets.Canal).
        self.ws_client.enviar({"cmd": "activar", "canal": canal.num_canal, "velocidad_%": 14})
        canal.confirmar_activacion()

    def actualizar_graficas(self):
        #self.buffer_velocidad.append(nuevo_valor_velocidad)
        #self.buffer_flujo.append(nuevo_valor_flujo)
        #self.buffer_concentración.append(nuevo_valor_concentración)
        #self.buffer_latencia.append(nuevo_valor_latencia)
        if self.calibrando_velocidad and not self.calibrado_velocidad_parado:
            if not self.ax_velocidad.lines:
                self.ax_velocidad.clear()
                self.ax_velocidad.plot(self.tiempo_grafica_velocidad, self.buffer_velocidad)
            else: 
                self.ax_velocidad.lines[0].set_data(self.tiempo_grafica_velocidad, self.buffer_velocidad)
            self.ax_velocidad.set_xlim(0,int(self.e_tiempo_calibrado.get()))
            self.ax_velocidad.set_ylim(config.LIMITESY["velocidad"][0],config.LIMITESY["velocidad"][1])  # Ajusta el rango del eje y según tus datos esperados
            #self.ax_velocidad.plot(self.tiempo_grafica_velocidad, self.buffer_velocidad)
            self.ax_velocidad.set_xlabel("Tiempo (s)")
            self.ax_velocidad.set_ylabel("Velocidad (m/s)")
            self.ax_velocidad.tick_params(colors = "#ffffff") 
            self.ax_velocidad.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
            self.ax_velocidad.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
            self.canvas_velocidad.draw()
        if self.calibrando_flujo and not self.calibrado_flujo_parado:
            if not self.ax_flujo.lines:
                self.ax_flujo.clear()
                self.ax_flujo.plot(self.tiempo_grafica_flujo, self.buffer_flujo)
            else: 
                self.ax_flujo.lines[0].set_data(self.tiempo_grafica_flujo, self.buffer_flujo)
            self.ax_flujo.set_xlim(0,int(self.e_tiempo_calibrado.get()))
            self.ax_flujo.set_ylim(config.LIMITESY["flujo"][0],config.LIMITESY["flujo"][1])  # Ajusta el rango del eje y según tus datos esperados
            self.ax_flujo.set_xlabel("Tiempo (s)")
            self.ax_flujo.set_ylabel("Flujo (ml/min)")
            self.ax_flujo.tick_params(colors = "#ffffff") 
            self.ax_flujo.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
            self.ax_flujo.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
            self.canvas_flujo.draw()
        if self.calibrando_concentracion and not self.calibrado_concentracion_parado:
            if not self.ax_concentracion.lines:
                self.ax_concentracion.clear()
                self.ax_concentracion.plot(self.tiempo_grafica_concentracion, self.buffer_concentracion)
            else: 
                self.ax_concentracion.lines[0].set_data(self.tiempo_grafica_concentracion, self.buffer_concentracion)
            self.ax_concentracion.set_xlim(0,int(self.e_tiempo_calibrado.get()))
            self.ax_concentracion.set_ylim(config.LIMITESY["concentracion"][0],config.LIMITESY["concentracion"][1])  # Ajusta el rango del eje y según tus datos esperados
            self.ax_concentracion.set_xlabel("Tiempo (s)")
            self.ax_concentracion.set_ylabel("Concentración (µg/m\u00B3)")
            self.ax_concentracion.tick_params(colors = "#ffffff") 
            self.ax_concentracion.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
            self.ax_concentracion.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
            self.canvas_concentracion.draw()
        if self.calibrando_latencia and not self.calibrado_latencia_parado:
            if not self.ax_latencia.lines:
                self.ax_latencia.clear()
                self.ax_latencia.plot(self.tiempo_grafica_latencia, self.buffer_latencia)
            else: 
                self.ax_latencia.lines[0].set_data(self.tiempo_grafica_latencia, self.buffer_latencia)
            self.ax_latencia.set_xlim(0,int(self.e_tiempo_calibrado.get()))
            self.ax_latencia.set_ylim(config.LIMITESY["latencia"][0],config.LIMITESY["latencia"][1])  # Ajusta el rango del eje y según tus datos esperados
            self.ax_latencia.set_xlabel("Tiempo (s)")
            self.ax_latencia.set_ylabel("Latencia (ms)")
            self.ax_latencia.tick_params(colors = "#ffffff") 
            self.ax_latencia.xaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje x
            self.ax_latencia.yaxis.label.set_color("#ffffff")  # Color de las etiquetas del eje y
            self.canvas_latencia.draw()
            
        self.after_actualizar_graficas = self.after(config.INTERVALO_DE_ACTUALIZACION_UI_MS, self.actualizar_graficas)
    


    def consultar_colores(self):
        for canal in self.cuadros_canales:
            self.olores.append(canal.e_olor_canal.get())

    def calcular_posicion_valvula(self, num_canal_actual, num_canal_final):
        movimiento = self.posiciones_canales[num_canal_final] - self.posiciones_canales[num_canal_actual]
        self.posicion_valvula = self.posicion_valvula + movimiento
        return movimiento
        
   
    def actualizar_canales(self,num_canal,accion):     
            if accion== "activar":
                #se establece la posición de la válvula giratoria según el canal activo y el canal que se quiere activar.
                pasos = self.calcular_posicion_valvula(self.canal_activo.num_canal if self.canal_activo else config.CANAL_BLANCO, num_canal)
                
                if self.canal_activo != None and self.canal_activo.num_canal != num_canal:
                    self.consola.registro(f"Se ha activado el canal {num_canal} ({self.cuadros_canales[num_canal].e_olor_canal.get() if self.cuadros_canales[num_canal].e_olor_canal.get() else ''}) mientras el canal {self.canal_activo.num_canal} ({self.cuadros_canales[self.canal_activo.num_canal].e_olor_canal.get() if self.cuadros_canales[self.canal_activo.num_canal].e_olor_canal.get() else ''}) estaba activo. Se detiene el canal {self.canal_activo.num_canal} ({self.cuadros_canales[num_canal].e_olor_canal.get() if self.cuadros_canales[num_canal].e_olor_canal.get() else ''}).", nivel="AVISO")
                    self.canal_activo.parar_canal()
                self.canal_activo = self.cuadros_canales[num_canal]
                self.sv_canal_activo.set(f"Canal {self.canal_activo.e_olor_canal.get()}" if self.canal_activo.e_olor_canal.get() else "Canal Blanco")

                if self.protocolo_activo:

                    if self.sv_canal_activo.get() == "Canal Blanco":
                        self.sv_canal_anterior.set(f"Canal {self.canales_protocolo[self.indice_canal_protocolo].e_olor_canal.get()}" if self.indice_canal_protocolo >=0 else "Ninguno")
                        self.sv_canal_siguiente.set(f"Canal {self.canales_protocolo[self.indice_canal_protocolo + 1].e_olor_canal.get()}" if self.indice_canal_protocolo+1 < len(self.canales_protocolo)  else "Ninguno")
                    else:
                        self.sv_canal_anterior.set(f"Canal Blanco" if self.indice_canal_protocolo - 1 >= 0 else "Ninguno")
                        self.sv_canal_siguiente.set(f"Canal Blanco" if self.indice_canal_protocolo + 1 <= len(self.canales_protocolo)  else "Ninguno")      
                
                #mensaje para mover la válvula giratoria  a la posición del canal activo.
                self.ws_client.enviar({"cmd": "rotar", "canal": num_canal, "pasos": pasos})
                #el motor DC y el cronómetro del canal se arrancan en _completar_activacion_canal,
                #cuando el ESP32 confirme por ACK que la válvula ya ha llegado a esta posición
                #(ver _datos_ack). Así evitamos que el "tiempo activo" empiece a contar mientras
                #la válvula todavía está girando.
                self.canal_esperando_posicion = num_canal
                self.callbacks_pendientes_posicion_valvula.append((num_canal, self._completar_activacion_canal, (self.cuadros_canales[num_canal],)))


            if accion== "parar":
                self._cancelar_activacion_pendiente(self.cuadros_canales[num_canal])
                if self.canal_esperando_posicion == num_canal:
                    self.canal_esperando_posicion = None
                if self.canal_activo is not None and self.canal_activo.num_canal == num_canal:
                    ultima_telemetria = self.ultimos_datos_telemetria.get(num_canal, {})
                    self.historial_sesion.append({
                                "timestamp" : time.time(),
                                "canal" : self.canal_activo.num_canal,
                                "olor" : self.canal_activo.e_olor_canal.get()
                                if self.canal_activo.e_olor_canal.winfo_exists() else "",
                                "estado" : "inactivo" ,
                                #PENDIENTE DE MODIFICAR, DEBE MOSTRAR LOS ULTIMOS DATOS DE TELEMETRÍA DEL CANAL ANTES DE PARARLO, NO 0.0
                                "flujo" :ultima_telemetria.get("flujo", 0.0),
                                "velocidad_motor" : ultima_telemetria.get("velocidad_motor", 0.0),
                                "concentracion" : ultima_telemetria.get("concentracion", 0.0),
                                "latencia" : ultima_telemetria.get("latencia", 0),
                                "modo": ultima_telemetria.get("modo","----")
                    })
                    if not self.protocolo_activo:
                        pasos = self.calcular_posicion_valvula(self.canal_activo.num_canal if self.canal_activo else config.CANAL_BLANCO, config.CANAL_BLANCO)
                        self.ws_client.enviar({"cmd": "rotar", "canal": num_canal, "pasos": pasos})
                        self.canal_activo = None
                        self.sv_canal_activo.set("Ninguno")

                    #podrían establecerse como valor "Ninguno" a los canales anterior y siguiente.
                #self.consola.registro(f"Canal {num_canal} SE PARA")
                self.ws_client.enviar({"cmd": "parar", "canal": num_canal})
        

            #self.after(1000, self.actualizar_canales)
            

#FUNCIONES NECESARIAS PARA LA CONCEXIÓN CON ESP32
    def _datos_telemetria(self, datos: dict):
        # Llamado desde el hilo WS → usar after() para tocar la UI
        num_canal = datos.get("canal", -1)
        #actualizo la varible con los últimos datos de telemetría recibidos del canal activo
        if num_canal >= 0:
            self.ultimos_datos_telemetria[num_canal] = dict(datos)

        # Actualizar buffers de la gráfica correspondiente
        if self.canal_activo is not None and num_canal == self.canal_activo.num_canal:

            self.buffer_historico_flujo.append(datos.get("flujo", 0.0))
            self.buffer_historico_velocidad.append(datos.get("velocidad_motor", 0.0))
            self.buffer_historico_concentracion.append(datos.get("concentracion", 0.0))
            self.buffer_historico_latencia.append(datos.get("latencia", 0))
            self.buffer_historico_timestamps.append(datos.get("timestamp", time.time()))

            try:
                olor = self.canal_activo.e_olor_canal.get()
            except Exception:
                olor = ""
            self.buffer_historico_olores.append(olor)
            datos_con_hist = dict(datos)
            datos_con_hist["timestamp"] = time.time()
            datos_con_hist["olor"] = olor
            datos_con_hist["modo"] = "Protocolo" if self.protocolo_activo else "Calibrado" if self.calibrado_activo() else "Manual"
            self.historial_sesion.append(datos_con_hist)
   
            with open(self.ruta_archivo_temporal, "a", encoding="utf-8") as archivo_temporal:
                json.dump(datos_con_hist, archivo_temporal, ensure_ascii=False)
                archivo_temporal.write("\n")
                
        
        
        if self.canal_calibrado is not None and num_canal == self.canal_calibrado.num_canal:
            if self.calibrando_flujo and not self.calibrado_flujo_parado:
                #self.buffer_flujo.append(datos["flujo"])
                self.buffer_flujo[self.contador_flujo]=(datos.get("flujo", 0.0))
                self.contador_flujo += 1
                self.buffer_historico_calibrado_flujo.append(datos["flujo"])
            if self.calibrando_concentracion and not self.calibrado_concentracion_parado:
                #self.buffer_concentracion.append(datos["concentracion"])
                self.buffer_concentracion[self.contador_concentracion]=(datos.get("concentracion", 0.0))
                self.contador_concentracion += 1
                self.buffer_historico_calibrado_concentracion.append(datos["concentracion"])
            if self.calibrando_latencia and not self.calibrado_latencia_parado:
                #self.buffer_latencia.append(datos["latencia"])
                self.buffer_latencia[self.contador_latencia]=(datos.get("latencia", 0.0))
                self.contador_latencia += 1
                self.buffer_historico_calibrado_latencia.append(datos["latencia"])
            if self.calibrando_velocidad and not self.calibrado_velocidad_parado:
                #self.buffer_velocidad[self.contador]
                    #self.buffer_velocidad.append(datos["velocidad_motor"])
                self.buffer_velocidad[self.contador_velocidad] = (datos.get("velocidad_motor", 0.0))
                self.contador_velocidad += 1
                self.buffer_historico_calibrado_velocidad.append(datos["velocidad_motor"])

        # Actualizar labels de Estado
        #self.after(100, self._actualizar_labels_estado, datos)
        self._actualizar_labels_estado(datos)


    def _actualizar_labels_estado(self, datos):
        self.sv_latencia_canal.set(f"{datos.get('latencia',0)} ms")
        #if self.canal_activo is not None:
            #if datos.get("canal") == self.canal_activo.num_canal:
                #self.sv_latencia_canal.set(f"{datos.get('latencia',0)} ms")
                #if self.calibrado_activo():
                    #self.sv_velocidad_motor.set(f"{datos['velocidad_motor']:.1f} m/s")
                    #self.sv_flujo_aire_canal.set(f"{datos.get('flujo',0.0):.1f} ml/min")
                    #self.sv_concentracion_canal.set(f"{datos.get('concentracion',0.0):.1f} µg/m\u00B3")
                #Quiero calcular una estimación
                #else:
                    #añadir por cada parámetro una fórmula de estimación
                    #self.sv_flujo_aire_canal.set(f"{datos.get('flujo',0.0):.1f} ml/min")
                    #self.sv_concentracion_canal.set(f"{datos.get('concentracion',0.0):.1f} µg/m\u00B3")
                    #self.sv_latencia_canal.set(f"{datos.get('latencia',0):.1f} ms") #la latencia no hace falta aproximarla, se sabe su valor en cada momento
                    
    def _datos_ack(self, datos: dict):
        # Procesar ACK de datos si es necesario
        accion = datos.get("ack", "desconocida")
        canal_accion = datos.get("canal", "desconocido")
        estado_accion = datos.get("ok", "desconocido")
        estado_en_cola = datos.get("en_cola", "desconocido")

        # ACK final de "rotar" (ya no en cola, es decir, la válvula ha llegado a la posición de destino
        # de ese canal): dispara el inicio del conteo (calibrado o protocolo) que estaba esperando a
        # que la válvula se posicionase en ese canal concreto.
        if accion == "rotar" and estado_accion is True and not estado_en_cola:
            if self.canal_esperando_posicion == canal_accion:
                self.canal_esperando_posicion = None
            funciones_callbacks = [
                (funcion, argumentos) for num_canal, funcion, argumentos in self.callbacks_pendientes_posicion_valvula
                if num_canal == canal_accion
            ]
            if funciones_callbacks:
                self.callbacks_pendientes_posicion_valvula = [
                    (num_canal, funcion, argumentos) for num_canal, funcion, argumentos in self.callbacks_pendientes_posicion_valvula
                    if num_canal != canal_accion
                ]
                #se llama a la función/funciones periodo pendientes para ese canal
                for funcion, argumentos in funciones_callbacks:
                    funcion(*argumentos)

        if estado_accion == True:
            estado_accion = "correctamente"
        else: 
            estado_accion = "incorrectamente"
        if canal_accion == config.CANAL_BLANCO:
            self.consola.registro(f"[ESP32] Acción '{accion}' en canal {canal_accion} (Canal Blanco) recibida y {'en colada' if estado_en_cola else 'ejecutada'} {estado_accion}.")
        else:
            self.consola.registro(f"[ESP32] Acción '{accion}' en canal {canal_accion} ({self.cuadros_canales[int(canal_accion)].e_olor_canal.get() if self.cuadros_canales[int(canal_accion)].e_olor_canal.get() else "Sin olor definido"}) recibida y {"en colada" if estado_en_cola else "ejecutada"} {estado_accion}.")

    def _datos_log(self, datos: dict):
        # Procesar log de datos si es necesario
        nivel_mensaje = datos.get("nivel", "INFO").upper()
        mensaje = datos.get("log", "(sin contenido)")
        self.consola.registro(f"[ESP32] {mensaje}", nivel=nivel_mensaje)
    
                

    def _on_estado_ws(self, estado: str):
        # Actualizar el indicador de conexión en la cabecera
        textos = {
            "conectando":    ("◌ Conectando…",  config.COLOR_ESTADO_CONECTANDO),
            "conectado":     ("● Conectado",    config.COLOR_ESTADO_OK),
            "desconectado":  ("○ Desconectado", config.COLOR_ESTADO_DESCONECTADO),
            "error":         ("✕ Error",       config.COLOR_ESTADO_ERROR),
        }

        if estado == "conectado":
            self.consola.registro("Conexión establecida con el ESP32", nivel="INFO")
        elif estado == "desconectado":
            self.consola.registro(f"Sin conexión con el ESP32. Reintentando en {config.RECONEXION_AUTOMATICA_S} s…", nivel="ERROR")
            if (self.protocolo_activo and not self.protocolo_parado) or self.calibrado_activo() or self.canal_activo is not None:
                #Intento de parada de todos los canales como medida de seguridad en caso de que el sistema estuviera activo y se pierda la conexión con el ESP32. 
                self.ws_client.enviar({"cmd": "parar_todos"})
                self.consola.registro("COMPRUEBE QUE EL SISTEMA ESTÁ APAGADO. SI NO ES ASÍ, PULSE LA SETA DE EMERGENCIA.", nivel="AVISO")
        texto, color = textos.get(estado, ("○ Desconectado", "#fa8989"))
        self.after(0, lambda: self.l_estado_conexion.configure(text=texto, text_color=color))

if __name__ == "__main__":  
    app = App()
    app.mainloop()




