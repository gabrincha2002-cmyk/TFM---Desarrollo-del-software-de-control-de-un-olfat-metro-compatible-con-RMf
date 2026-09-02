"""
=============================================================
 App de escritorio — Interfaz gráfica OlfaMetric
=============================================================
"""

#imports necesarios
import customtkinter as ctk
import time
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

#Configuración de apariencia y color
ctk.set_appearance_mode("dark")          
ctk.set_default_color_theme("blue")      

##################################################
# WIDGETS DE INTERFAZ
##################################################
class Canal(ctk.CTkFrame):
    """Marco que representa un canal individual del olfatómetro"""

    def __init__(self, master, color_canal, num_canal, registro=None, num_canal_activo=None):
        super().__init__(master, fg_color="#343638", border_color="#4a4c4e",
                         border_width=1, corner_radius=10)
        self.color_canal = color_canal
        self.num_canal = num_canal
        self.registro = registro
        self.num_canal_activo = num_canal_activo
        self.estado_canal = False
        self.crear_canal()

    def crear_canal(self):
        #Disribución interna del del canal
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure((0, 1), weight=1)

        #Etiqueta con el color/identificador del canal
        self.l_color_canal = ctk.CTkLabel(self, text=f"Canal {self.color_canal}",
                                          font=ctk.CTkFont(size=20, weight="bold"))
        self.l_color_canal.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")

        #Entrada para asociar un olor al canal
        self.e_olor_canal = ctk.CTkEntry(self, placeholder_text="Olor del canal",
                                         font=ctk.CTkFont(size=20))
        self.e_olor_canal.grid(row=0, column=0, padx=10, pady=10, sticky="e")

        #Indicador de tiempo activo del canal
        self.tiempo_activo = ctk.StringVar(value="Tiempo activo: 00:00:00")
        self.l_tiempo_act_canal = ctk.CTkLabel(self, textvariable=self.tiempo_activo,
                                               font=ctk.CTkFont(size=14))
        self.l_tiempo_act_canal.grid(row=2, column=0, padx=10, pady=(10, 5), sticky="w")

        #Barra de progreso y porcentaje de actividad
        self.pb_actividad_canal = ctk.CTkProgressBar(self, width=400, height=20)
        self.pb_actividad_canal.grid(row=3, column=0, padx=10, pady=(10, 5), sticky="w")

        self.l_porcentaje_act_canal = ctk.CTkLabel(self, text="0%",
                                                   font=ctk.CTkFont(size=14))
        self.l_porcentaje_act_canal.grid(row=3, column=1, padx=10, pady=(5, 10), sticky="w")

        #Botones de control manual del canal (Activar/Parar)
        self.b_activar_canal = ctk.CTkButton(self, text="Activar", fg_color="#85ad75",
                                             text_color="#ffffff", hover_color="#488f51",
                                             corner_radius=10, border_color="#006400",
                                             border_width=1,
                                             font=ctk.CTkFont(size=16, weight="bold"),
                                             command=self.activar_canal)
        self.b_activar_canal.grid(row=5, column=0, padx=10, pady=(5, 10), sticky="w")

        self.b_parar_canal = ctk.CTkButton(self, text="Parar", fg_color="#f56a6a",
                                           text_color="#ffffff", hover_color="#ee4242",
                                           corner_radius=10, border_color="#ff0000",
                                           border_width=1,
                                           font=ctk.CTkFont(size=16, weight="bold"),
                                           command=self.parar_canal)
        self.b_parar_canal.grid(row=5, column=1, padx=10, pady=(5, 10), sticky="w")

    def activar_canal(self):
        #Cambia el estilo del marco y del botón para indicar que el canal está en marcha
        if not self.estado_canal:
            self.estado_canal = True
            self.num_canal_activo = self.num_canal
            self.configure(fg_color="#256F2F", border_color="#7DEB7D", border_width=4)
            self.b_activar_canal.configure(text="En marcha", fg_color="#70c64e",
                                           text_color="#ffffff", border_color="#006400",
                                           border_width=1,
                                           font=ctk.CTkFont(size=14, weight="bold"))

    def parar_canal(self):
        #Restaura el estilo original del canal al detenerlo
        if self.estado_canal:
            self.estado_canal = False
            self.num_canal_activo = None
            self.configure(fg_color="#343638", border_color="#4a4c4e", border_width=1)
            self.b_activar_canal.configure(text="Activar", fg_color="#85ad75",
                                           text_color="#ffffff", border_color="#006400",
                                           border_width=1,
                                           font=ctk.CTkFont(size=14, weight="bold"))


class SpinboxCTk(ctk.CTkFrame):
    """Caja de entrada numérica con botones de incremento y decremento."""

    def __init__(self, master, valor=120, valor_min=0, valor_max=9999999, escalon=1,
                 fg_color="transparent", border_color="transparent",
                 border_width=0, corner_radius=10):
        super().__init__(master)
        self.valor_min = valor_min
        self.valor_max = valor_max
        self.escalon = escalon
        self.valor = ctk.StringVar(value=valor)
        self.crear_spinboxCTk()

    def crear_spinboxCTk(self):
        #Función de creación del spinbox 
        f_spinbox = ctk.CTkFrame(self, fg_color="transparent", bg_color="transparent")
        f_spinbox.grid_columnconfigure((0, 2), weight=0)
        f_spinbox.grid_columnconfigure(1, weight=1)
        f_spinbox.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        #Botón de decremento
        b_decrementar = ctk.CTkButton(f_spinbox, bg_color="transparent", fg_color="#0a5f70",
                                      text="-", width=30, command=self.decrementar,
                                      font=ctk.CTkFont(size=14, weight="bold"),
                                      border_color="#0a5f70", border_width=1)
        b_decrementar.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        #Caja de entrada del valor numérico
        e_spinbox = ctk.CTkEntry(f_spinbox, bg_color="transparent", fg_color="transparent",
                                 textvariable=self.valor, font=ctk.CTkFont(size=14))
        e_spinbox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        #Botón de incremento
        b_incrementar = ctk.CTkButton(f_spinbox, bg_color="transparent", fg_color="#0a5f70",
                                      text="+", width=30, command=self.incrementar,
                                      font=ctk.CTkFont(size=14, weight="bold"),
                                      border_color="#0a5f70", border_width=1)
        b_incrementar.grid(row=0, column=2, padx=5, pady=5, sticky="e")

    def incrementar(self):
        #Incrementa el valor del spinbox en una unidad
        try:
            valor_actual = int(self.valor.get())
            if valor_actual + self.escalon <= self.valor_max:
                self.valor.set(valor_actual + self.escalon)
        except ValueError:
            pass

    def decrementar(self):
        #Decrementa el valor del spinbox en una unidad
        try:
            valor_actual = int(self.valor.get())
            if valor_actual - self.escalon >= self.valor_min:
                self.valor.set(valor_actual - self.escalon)
        except ValueError:
            pass

    def get(self):
        #Función básica para obtener el valor del spinbox, devolviendo el valor mínimo en caso de error
        try:
            return int(self.valor.get())
        except ValueError:
            return self.valor_min

    def set(self, valor):
        #Función básica para establecer el valor del spinbox, asegurando que esté dentro de los límites
        self.valor.set(int(valor))


class FrameDeslizante(ctk.CTkScrollableFrame):
    """Marco desplazable reutilizable"""

    def __init__(self, master, fg_color, border_color="#4a4c4e",
                 border_width=1, corner_radius=10):
        super().__init__(master, fg_color=fg_color, border_color=border_color,
                         border_width=border_width, corner_radius=corner_radius)
        self.fg_color = fg_color
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)


class Consola(ctk.CTkTextbox):
    """Panel de consola para el registro de eventos y mensajes de estado de la aplicación"""

    def __init__(self, master):
        super().__init__(master)
        self.crear()

    def crear(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        #Título de la consola
        ctk.CTkLabel(self, text="Consola", text_color="#458B8D",
                     font=ctk.CTkFont(size=22, weight="bold")
                     ).grid(row=0, column=0, padx=5, pady=(5, 5), sticky="nw")

        #Área de texto donde se muestran los mensajes de registro
        self.t_registro = ctk.CTkTextbox(self, width=1000, height=150,
                                         font=ctk.CTkFont(size=14))
        self.t_registro.grid(row=1, column=0, padx=10, pady=(10, 5), sticky="nsew")


#####################################
# VENTANA PRINCIPAL
#####################################
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("OlfaMetric")
        self.geometry("1920x1080")

        #Colores/etiquetas de cada contendor de odorante
        self.colores_canales = ["Verde Claro", "Negro", "Blanco",
                                "Azul", "Amarillo", "Rojo"]

        #Datos iniciales para las gráficas de calibración
        self.tiempo_graficas = list(range(61))
        self.buffer_velocidad = list(range(61))
        self.buffer_flujo = list(range(61))
        self.buffer_concentracion = list(range(61))
        self.buffer_latencia = list(range(61))

        #Variables de estado para los indicadores de la sección Estado
        self.canal_activo = None
        self.sv_canal_activo = ctk.StringVar(value="Ninguno")
        self.sv_canal_anterior = ctk.StringVar(value="Ninguno")
        self.sv_canal_siguiente = ctk.StringVar(value="Ninguno")

        #Malla principal de la ventana
        self.grid_rowconfigure(0, weight=0)   # Cabecera
        self.grid_rowconfigure(1, weight=1)   # Canales / panel lateral
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)   # Consola
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)

        self.crear_ui()

    ################################################
    # CONSTRUCCIÓN DE LA INTERFAZ DE USUARIO
    ###############################################
    def crear_ui(self):
        #---- CABECERA ----
        self.f_cabecera = ctk.CTkFrame(self, fg_color="#1e1e1e", border_color="#4a4c4e",
                                       border_width=1, corner_radius=10)
        self.f_cabecera.grid(row=0, column=0, sticky="nsew", columnspan=2)
        self.f_cabecera.grid_columnconfigure((0, 1), weight=1)
        self.f_cabecera.grid_rowconfigure(0, weight=1)

        #Título y eslogan de la aplicación
        self.l_titulo = ctk.CTkLabel(self.f_cabecera, text="OlfaMetric", corner_radius=10,
                                     text_color="#01bdce",
                                     font=ctk.CTkFont(size=60, weight="bold"))
        self.l_titulo.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        self.l_subtitulo = ctk.CTkLabel(self.f_cabecera,
                                        text="- An olfactory metric for everyone -",
                                        corner_radius=10, text_color="#80E8E9",
                                        font=ctk.CTkFont(size=30, weight="normal",
                                                         slant="italic"))
        self.l_subtitulo.grid(row=0, column=0, padx=350, pady=5, sticky="w")

        #Indicador de estado de conexión
        self.l_estado = ctk.CTkLabel(self.f_cabecera, text="○ Desconectado",
                                     fg_color="#1e1e1e", text_color="#fa8989",
                                     font=ctk.CTkFont(size=18, weight="bold"))
        self.l_estado.grid(row=0, column=1, padx=30, pady=10, sticky="en")

        #Botón para lanzar la búsqueda de dispositivos
        self.b_buscar_dispositivos = ctk.CTkButton(self.f_cabecera, text="Buscar dispositivos",
                                                   fg_color="#1e1e1e", text_color="#828282",
                                                   corner_radius=10, border_width=1,
                                                   command=self.b_buscar_dispositivos,
                                                   font=ctk.CTkFont(size=14, weight="bold"))
        self.b_buscar_dispositivos.grid(row=0, column=1, padx=10, pady=(0, 5), sticky="es")

        #---- CONSOLA ----
        self.f_consola = ctk.CTkFrame(self, fg_color="#1e1e1e", border_color="#4a4c4e",
                                      border_width=1, corner_radius=10, height=100)
        self.f_consola.grid(row=3, column=0, columnspan=1, padx=5, pady=(5, 10), sticky="ew")
        self.consola = Consola(self.f_consola)
        self.consola.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")

        #---- SECCIÓN DE CANALES ----
        self.f_canales = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.f_canales.grid(row=1, column=0, padx=5, pady=10, sticky="nsew", rowspan=2)
        self.f_canales.grid_columnconfigure((0, 1), weight=1)
        self.f_canales.grid_rowconfigure((0, 1), weight=1)

        self.l_canales = ctk.CTkLabel(self.f_canales, text="Canales", text_color="#458B8D",
                                      font=ctk.CTkFont(size=22, weight="bold"))
        self.l_canales.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        #Malla de 3x2 con los marcos de cada uno de los seis canales
        self.cuadros_canales = []
        for i in range(0, 6):
            columna = i // 3
            fila = i % 3
            cuadro_canal = Canal(self.f_canales, color_canal=self.colores_canales[i],
                                 num_canal=i, num_canal_activo=self.canal_activo)
            cuadro_canal.grid(row=fila + 1, column=columna, padx=10, pady=10, sticky="nsew")
            self.cuadros_canales.append(cuadro_canal)

        #---- PANEL LATERAL CON PESTAÑAS (Protocolo/Calibración/Estado) ----
        self.tv_prot_cal_est = ctk.CTkTabview(master=self, fg_color="transparent",
                                              border_color="#4a4c4e", border_width=1,
                                              corner_radius=10, width=450)
        self.tv_prot_cal_est.grid(row=1, column=1, padx=5, pady=10, sticky="nsew", rowspan=3)
        self.tv_prot_cal_est.add("Protocolo")
        self.tv_prot_cal_est.add("Calibración")
        self.tv_prot_cal_est.add("Estado")

        self.tv_prot_cal_est.tab("Protocolo").grid_columnconfigure(0, weight=1)
        self.tv_prot_cal_est.tab("Calibración").grid_columnconfigure(0, weight=1)
        self.tv_prot_cal_est.tab("Estado").grid_columnconfigure(0, weight=1)
        self.tv_prot_cal_est.set("Protocolo")

        #---- PESTAÑA: PROTOCOLO ----
        self.l_protocolo = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"),
                                        bg_color="transparent",
                                        text="Protocolo de Olfatometría",
                                        text_color="#458B8D",
                                        font=ctk.CTkFont(size=22, weight="bold"))
        self.l_protocolo.grid(row=0, column=0, padx=5, pady=(20, 5), sticky="we")

        #Número de ciclos
        self.l_num_ciclos = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"),
                                         text="Número de ciclos",
                                         font=ctk.CTkFont(size=14, weight="bold"))
        self.l_num_ciclos.grid(row=1, column=0, padx=10, pady=(10, 2), sticky="we")
        self.e_num_ciclos = SpinboxCTk(self.tv_prot_cal_est.tab("Protocolo"), valor=3)
        self.e_num_ciclos.grid(row=2, column=0, padx=5, pady=(4, 2), sticky="n")

        #Intervalo entre ciclos
        self.l_intervalo_ciclos = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"),
                                               text="Intervalo entre ciclos (en sec)",
                                               font=ctk.CTkFont(size=14, weight="bold"))
        self.l_intervalo_ciclos.grid(row=3, column=0, padx=10, pady=(4, 2), sticky="we")
        self.e_intervalo_ciclos = SpinboxCTk(self.tv_prot_cal_est.tab("Protocolo"), valor=60)
        self.e_intervalo_ciclos.grid(row=4, column=0, padx=5, pady=(4, 2), sticky="n")

        #Tiempo de exposición
        self.l_tiempo_exposicion = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"),
                                                text="Exposición (en sec)",
                                                font=ctk.CTkFont(size=14, weight="bold"))
        self.l_tiempo_exposicion.grid(row=5, column=0, padx=10, pady=(4, 2), sticky="we")
        self.e_tiempo_exposicion = SpinboxCTk(self.tv_prot_cal_est.tab("Protocolo"), valor=3)
        self.e_tiempo_exposicion.grid(row=6, column=0, padx=5, pady=(4, 2), sticky="n")

        #Tiempo de desensibilización
        self.l_tiempo_limpieza = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"),
                                              text="Desensibilización (en sec)",
                                              font=ctk.CTkFont(size=14, weight="bold"))
        self.l_tiempo_limpieza.grid(row=7, column=0, padx=10, pady=(4, 2), sticky="we")
        self.e_tiempo_limpieza = SpinboxCTk(self.tv_prot_cal_est.tab("Protocolo"), valor=30)
        self.e_tiempo_limpieza.grid(row=8, column=0, padx=5, pady=(4, 2), sticky="n")

        #Selector del orden de activación de canales
        self.l_orden_canales = ctk.CTkLabel(self.tv_prot_cal_est.tab("Protocolo"),
                                            text="Orden de los canales",
                                            font=ctk.CTkFont(size=14, weight="bold"))
        self.l_orden_canales.grid(row=9, column=0, padx=10, pady=(30, 5), sticky="n")
        self.cb_secuencial = ctk.CTkCheckBox(self.tv_prot_cal_est.tab("Protocolo"),
                                             text="Secuencial",
                                             font=ctk.CTkFont(size=14))
        self.cb_secuencial.grid(row=10, column=0, padx=40, pady=(4, 2), sticky="w")
        self.cb_aleatorio = ctk.CTkCheckBox(self.tv_prot_cal_est.tab("Protocolo"),
                                            text="Aleatorio",
                                            font=ctk.CTkFont(size=14))
        self.cb_aleatorio.grid(row=10, column=0, padx=40, pady=(4, 2), sticky="e")

        #Botones de control del protocolo (iniciar/reiniciar/parar)
        self.b_iniciar_protocolo = ctk.CTkButton(self.tv_prot_cal_est.tab("Protocolo"),
                                                 text="▶", text_color="#ffffff",
                                                 fg_color="#85ad75", width=15, height=20,
                                                 hover_color="#488f51",
                                                 border_color="#006400", border_width=1,
                                                 corner_radius=10,
                                                 command=self.iniciar_protocolo,
                                                 font=ctk.CTkFont(size=26, weight="bold"))
        self.b_iniciar_protocolo.grid(row=18, column=0, padx=50, pady=(60, 5), sticky="w")

        self.b_reiniciar_protocolo = ctk.CTkButton(self.tv_prot_cal_est.tab("Protocolo"),
                                                   text="↻", text_color="#ffffff",
                                                   fg_color="#C7BE19", width=15, height=20,
                                                   hover_color="#9da31e",
                                                   border_color="#F6F04F", border_width=1,
                                                   corner_radius=10,
                                                   command=self.reiniciar_protocolo,
                                                   font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_protocolo.grid(row=18, column=0, padx=10, pady=(60, 5), sticky="n")

        self.b_parar_protocolo = ctk.CTkButton(self.tv_prot_cal_est.tab("Protocolo"),
                                               text="◼", text_color="#ffffff",
                                               width=15, height=20,
                                               fg_color="#f56a6a", hover_color="#ee4242",
                                               border_color="#ff0000", corner_radius=10,
                                               border_width=1,
                                               command=self.parar_protocolo,
                                               font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_protocolo.grid(row=18, column=0, padx=50, pady=(60, 5), sticky="e")

        #---- PESTAÑA: CALIBRACIÓN ----
        #Marco desplazable interno para almacenar las secciones de los parámetros de interés del calibrado
        self.f_calibracion_scroll = ctk.CTkScrollableFrame(
            self.tv_prot_cal_est.tab("Calibración"), fg_color="transparent")
        self.f_calibracion_scroll.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.tv_prot_cal_est.tab("Calibración").grid_rowconfigure(0, weight=1)
        self.tv_prot_cal_est.tab("Calibración").grid_columnconfigure(0, weight=1)
        self.f_calibracion_scroll.grid_columnconfigure(0, weight=1)

        self.l_calibracion = ctk.CTkLabel(self.f_calibracion_scroll, text="Calibración",
                                          text_color="#458B8D",
                                          font=ctk.CTkFont(size=22, weight="bold"))
        self.l_calibracion.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="n")

        #Desplegable de selección del canal a calibrar
        sv_canales_calibrado = ctk.StringVar(value="Ninguno")
        comb_canales_calibrados = ctk.CTkComboBox(
            self.f_calibracion_scroll,
            values=['Ninguno', 'Canal Amarillo', 'Canal Rojo', 'Canal Verde',
                    'Canal Azul', 'Canal Blanco', 'Canal Negro'],
            width=160, height=36, text_color="#ffffff",
            command=self.canal_calibrado, dropdown_fg_color="#0a5f70",
            variable=sv_canales_calibrado)
        comb_canales_calibrados.grid(row=1, column=0, padx=10, pady=(20, 5), sticky="n")

        #-- Bloque de calibración: Velocidad --
        self.l_calibracion_velocidad = ctk.CTkLabel(self.f_calibracion_scroll,
                                                    text="Velocidad",
                                                    text_color="#458B8D",
                                                    font=ctk.CTkFont(size=18, weight="bold"))
        self.l_calibracion_velocidad.grid(row=2, column=0, padx=10, pady=(50, 5), sticky="n")

        #Gráfica en tiempo real integrada con matplotlib
        fig_velocidad = Figure(figsize=(10, 5), dpi=55)
        self.ax_velocidad = fig_velocidad.add_subplot(111)
        self.ax_velocidad.set_xlabel("Tiempo (s)")
        self.ax_velocidad.set_ylabel("Velocidad (m/s)")
        self.ax_velocidad.plot(self.tiempo_graficas, self.buffer_velocidad)
        fig_velocidad.tight_layout()
        self.canvas_velocidad = FigureCanvasTkAgg(fig_velocidad,
                                                  master=self.f_calibracion_scroll)
        self.canvas_velocidad.get_tk_widget().grid(row=3, column=0, padx=10, pady=20, sticky="n")
        self.canvas_velocidad.draw()

        self.b_iniciar_calibracion_velocidad = ctk.CTkButton(
            self.f_calibracion_scroll, text="▶", text_color="#ffffff",
            fg_color="#85ad75", width=15, height=20, hover_color="#488f51",
            border_color="#006400", border_width=1, corner_radius=10,
            command=self.iniciar_calibrado_velocidad,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibracion_velocidad.grid(row=4, column=0, padx=90, pady=(20, 5), sticky="w")

        self.b_reiniciar_calibrado_velocidad = ctk.CTkButton(
            self.f_calibracion_scroll, text="↻", text_color="#ffffff",
            fg_color="#C7BE19", width=15, height=20, hover_color="#9da31e",
            border_color="#F6F04F", border_width=1, corner_radius=10,
            command=self.reiniciar_calibrado_velocidad,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_velocidad.grid(row=4, column=0, padx=10, pady=(20, 5), sticky="n")

        self.b_parar_calibrado_velocidad = ctk.CTkButton(
            self.f_calibracion_scroll, text="◼", text_color="#ffffff",
            width=15, height=20, fg_color="#f56a6a", hover_color="#ee4242",
            border_color="#ff0000", corner_radius=10, border_width=1,
            command=self.parar_calibrado_velocidad,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_velocidad.grid(row=4, column=0, padx=90, pady=(20, 5), sticky="e")

        #-- Bloque de calibración: Flujo --
        self.l_calibracion_flujo = ctk.CTkLabel(self.f_calibracion_scroll, text="Flujo",
                                                text_color="#458B8D",
                                                font=ctk.CTkFont(size=18, weight="bold"))
        self.l_calibracion_flujo.grid(row=5, column=0, padx=10, pady=(50, 5), sticky="n")

        fig_flujo = Figure(figsize=(10, 5), dpi=60)
        self.ax_flujo = fig_flujo.add_subplot(111)
        self.ax_flujo.set_xlabel("Tiempo (s)")
        self.ax_flujo.set_ylabel("Flujo (ml/min)")
        self.ax_flujo.plot(self.tiempo_graficas, self.buffer_flujo)
        fig_flujo.tight_layout()
        self.canvas_flujo = FigureCanvasTkAgg(fig_flujo, master=self.f_calibracion_scroll)
        self.canvas_flujo.get_tk_widget().grid(row=6, column=0, padx=10, pady=(20, 5), sticky="n")
        self.canvas_flujo.draw()

        self.b_iniciar_calibracion_flujo = ctk.CTkButton(
            self.f_calibracion_scroll, text="▶", text_color="#ffffff",
            fg_color="#85ad75", width=15, height=20, hover_color="#488f51",
            border_color="#006400", border_width=1, corner_radius=10,
            command=self.iniciar_calibrado_flujo,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibracion_flujo.grid(row=7, column=0, padx=90, pady=(20, 5), sticky="w")

        self.b_reiniciar_calibrado_flujo = ctk.CTkButton(
            self.f_calibracion_scroll, text="↻", text_color="#ffffff",
            fg_color="#C7BE19", width=15, height=20, hover_color="#9da31e",
            border_color="#F6F04F", border_width=1, corner_radius=10,
            command=self.reiniciar_calibrado_flujo,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_flujo.grid(row=7, column=0, padx=10, pady=(20, 5), sticky="n")

        self.b_parar_calibrado_flujo = ctk.CTkButton(
            self.f_calibracion_scroll, text="◼", text_color="#ffffff",
            width=15, height=20, fg_color="#f56a6a", hover_color="#ee4242",
            border_color="#ff0000", corner_radius=10, border_width=1,
            command=self.parar_calibrado_flujo,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_flujo.grid(row=7, column=0, padx=90, pady=(20, 5), sticky="e")

        #-- Bloque de calibración: Concentración --
        self.l_calibracion_concentracion = ctk.CTkLabel(self.f_calibracion_scroll,
                                                        text="Concentración",
                                                        text_color="#458B8D",
                                                        font=ctk.CTkFont(size=18, weight="bold"))
        self.l_calibracion_concentracion.grid(row=8, column=0, padx=10, pady=(50, 5), sticky="n")

        fig_concentracion = Figure(figsize=(10, 5), dpi=60)
        self.ax_concentracion = fig_concentracion.add_subplot(111)
        self.ax_concentracion.set_xlabel("Tiempo (s)")
        self.ax_concentracion.set_ylabel("Concentracion (µg/m³)")
        self.ax_concentracion.plot(self.tiempo_graficas, self.buffer_concentracion)
        fig_concentracion.tight_layout()
        self.canvas_concentracion = FigureCanvasTkAgg(fig_concentracion,
                                                      master=self.f_calibracion_scroll)
        self.canvas_concentracion.get_tk_widget().grid(row=9, column=0, padx=10, pady=(20, 5), sticky="n")
        self.canvas_concentracion.draw()

        self.b_iniciar_calibracion_concentracion = ctk.CTkButton(
            self.f_calibracion_scroll, text="▶", text_color="#ffffff",
            fg_color="#85ad75", width=15, height=20, hover_color="#488f51",
            border_color="#006400", border_width=1, corner_radius=10,
            command=self.iniciar_calibrado_concentracion,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibracion_concentracion.grid(row=10, column=0, padx=90, pady=(20, 5), sticky="w")

        self.b_reiniciar_calibrado_concentracion = ctk.CTkButton(
            self.f_calibracion_scroll, text="↻", text_color="#ffffff",
            fg_color="#C7BE19", width=15, height=20, hover_color="#9da31e",
            border_color="#F6F04F", border_width=1, corner_radius=10,
            command=self.reiniciar_calibrado_concentracion,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_concentracion.grid(row=10, column=0, padx=10, pady=(20, 5), sticky="n")

        self.b_parar_calibrado_concentracion = ctk.CTkButton(
            self.f_calibracion_scroll, text="◼", text_color="#ffffff",
            width=15, height=20, fg_color="#f56a6a", hover_color="#ee4242",
            border_color="#ff0000", corner_radius=10, border_width=1,
            command=self.parar_calibrado_concentracion,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_concentracion.grid(row=10, column=0, padx=90, pady=(20, 5), sticky="e")

        #-- Bloque de calibración: Latencia --
        self.l_calibracion_latencia = ctk.CTkLabel(self.f_calibracion_scroll, text="Latencia",
                                                   text_color="#458B8D",
                                                   font=ctk.CTkFont(size=18, weight="bold"))
        self.l_calibracion_latencia.grid(row=11, column=0, padx=10, pady=(50, 5), sticky="n")

        fig_latencia = Figure(figsize=(10, 5), dpi=60)
        self.ax_latencia = fig_latencia.add_subplot(111)
        self.ax_latencia.set_xlabel("Tiempo (s)")
        self.ax_latencia.set_ylabel("Latencia (ms)")
        fig_latencia.tight_layout()
        self.canvas_latencia = FigureCanvasTkAgg(fig_latencia,
                                                 master=self.f_calibracion_scroll)
        self.canvas_latencia.get_tk_widget().grid(row=12, column=0, padx=10, pady=(20, 5), sticky="n")
        self.canvas_latencia.draw()

        self.b_iniciar_calibracion_latencia = ctk.CTkButton(
            self.f_calibracion_scroll, text="▶", text_color="#ffffff",
            fg_color="#85ad75", width=15, height=20, hover_color="#488f51",
            border_color="#006400", border_width=1, corner_radius=10,
            command=self.iniciar_calibrado_latencia,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_iniciar_calibracion_latencia.grid(row=13, column=0, padx=90, pady=(20, 5), sticky="w")

        self.b_reiniciar_calibrado_latencia = ctk.CTkButton(
            self.f_calibracion_scroll, text="↻", text_color="#ffffff",
            fg_color="#C7BE19", width=15, height=20, hover_color="#9da31e",
            border_color="#F6F04F", border_width=1, corner_radius=10,
            command=self.reiniciar_calibrado_latencia,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_reiniciar_calibrado_latencia.grid(row=13, column=0, padx=10, pady=(20, 5), sticky="n")

        self.b_parar_calibrado_latencia = ctk.CTkButton(
            self.f_calibracion_scroll, text="◼", text_color="#ffffff",
            width=15, height=20, fg_color="#f56a6a", hover_color="#ee4242",
            border_color="#ff0000", corner_radius=10, border_width=1,
            command=self.parar_calibrado_latencia,
            font=ctk.CTkFont(size=24, weight="bold"))
        self.b_parar_calibrado_latencia.grid(row=13, column=0, padx=90, pady=(20, 5), sticky="e")

        #Botones de calibrado general
        self.b_iniciar_calibracion = ctk.CTkButton(
            self.f_calibracion_scroll, text="Iniciar Calibrado General",
            text_color="#ffffff", fg_color="#85ad75", width=15, height=20,
            hover_color="#488f51", border_color="#006400", border_width=1,
            corner_radius=10, command=self.iniciar_calibrado,
            font=ctk.CTkFont(size=20, weight="bold"))
        self.b_iniciar_calibracion.grid(row=14, column=0, padx=10, pady=(70, 5), sticky="n")

        self.b_reiniciar_calibrado = ctk.CTkButton(
            self.f_calibracion_scroll, text="Reiniciar Calibrado General",
            text_color="#ffffff", fg_color="#C7BE19", width=15, height=20,
            hover_color="#9da31e", border_color="#F6F04F", border_width=1,
            corner_radius=10, command=self.reiniciar_calibrado,
            font=ctk.CTkFont(size=20, weight="bold"))
        self.b_reiniciar_calibrado.grid(row=15, column=0, padx=10, pady=(20, 5), sticky="n")

        self.b_parar_calibrado = ctk.CTkButton(
            self.f_calibracion_scroll, text="Parar Calibrado General",
            text_color="#ffffff", fg_color="#f56a6a", width=15, height=20,
            hover_color="#ee4242", border_color="#ff0000", border_width=1,
            corner_radius=10, command=self.parar_calibrado,
            font=ctk.CTkFont(size=20, weight="bold"))
        self.b_parar_calibrado.grid(row=16, column=0, padx=10, pady=(20, 5), sticky="n")

        #---- PESTAÑA: ESTADO ----
        self.l_estado = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"), text="Estado",
                                     text_color="#458B8D",
                                     font=ctk.CTkFont(size=22, weight="bold"))
        self.l_estado.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="n")

        #Fecha y hora actuales
        self.l_fecha = ctk.CTkLabel(
            self.tv_prot_cal_est.tab("Estado"),
            text=f"Fecha y hora: {time.strftime('%d-%m-%Y %H:%M:%S', time.localtime())}",
            font=ctk.CTkFont(size=14, weight="bold"))
        self.l_fecha.grid(row=1, column=0, padx=10, pady=(20, 5), sticky="n")

        #Duración de la sesión
        self.duracion_sesion = ctk.StringVar(value="Duración de sesión: 00:00:00")
        self.l_duracion_sesion = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                              textvariable=self.duracion_sesion,
                                              font=ctk.CTkFont(size=14, weight="bold"))
        self.l_duracion_sesion.grid(row=2, column=0, padx=10, pady=(20, 5), sticky="n")

        #Identificadores de sesión y de paciente
        self.l_id_sesion = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                        text="ID de sesión: ",
                                        font=ctk.CTkFont(size=14, weight="bold"))
        self.l_id_sesion.grid(row=3, column=0, padx=71, pady=(20, 5), sticky="w")
        self.e_id_sesion = ctk.CTkEntry(self.tv_prot_cal_est.tab("Estado"),
                                        placeholder_text="introduzca identificador",
                                        font=ctk.CTkFont(size=14))
        self.e_id_sesion.grid(row=3, column=0, padx=71, pady=(20, 5), sticky="e")

        self.l_id_paciente = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                          text="ID de paciente: ",
                                          font=ctk.CTkFont(size=14, weight="bold"))
        self.l_id_paciente.grid(row=4, column=0, padx=65, pady=(20, 5), sticky="w")
        self.e_id_paciente = ctk.CTkEntry(self.tv_prot_cal_est.tab("Estado"),
                                          placeholder_text="introduzca identificador",
                                          font=ctk.CTkFont(size=14))
        self.e_id_paciente.grid(row=4, column=0, padx=65, pady=(20, 5), sticky="e")

        #Indicadores de canales anterior/activo/siguiente
        self.l_canal_anterior = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                             text="Canal anterior: ",
                                             font=ctk.CTkFont(size=14, weight="bold"))
        self.l_canal_anterior.grid(row=5, column=0, padx=110, pady=(20, 5), sticky="w")
        self.l_canal_anterior_valor = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                                   textvariable=self.sv_canal_anterior,
                                                   font=ctk.CTkFont(size=14))
        self.l_canal_anterior_valor.grid(row=5, column=0, padx=110, pady=(20, 5), sticky="e")

        self.l_canal_activo = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                           text="Canal activo: ",
                                           font=ctk.CTkFont(size=14, weight="bold"))
        self.l_canal_activo.grid(row=6, column=0, padx=115, pady=(20, 5), sticky="w")
        self.l_canal_activo_valor = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                                 textvariable=self.sv_canal_activo,
                                                 font=ctk.CTkFont(size=14))
        self.l_canal_activo_valor.grid(row=6, column=0, padx=115, pady=(20, 5), sticky="e")

        self.l_canal_siguiente = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                              text="Canal siguiente: ",
                                              font=ctk.CTkFont(size=14, weight="bold"))
        self.l_canal_siguiente.grid(row=7, column=0, padx=105, pady=(20, 5), sticky="w")
        self.l_canal_siguiente_valor = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                                    textvariable=self.sv_canal_siguiente,
                                                    font=ctk.CTkFont(size=14))
        self.l_canal_siguiente_valor.grid(row=7, column=0, padx=105, pady=(20, 5), sticky="e")

        #Indicadores de latencia, flujo de aire y concentración estimados
        self.l_latencia_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                             text="Latencia: ",
                                             font=ctk.CTkFont(size=14, weight="bold"))
        self.l_latencia_canal.grid(row=8, column=0, padx=140, pady=(20, 5), sticky="w")
        self.sv_latencia_canal = ctk.StringVar(value="0 ms")
        self.l_valor_latencia_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                                   textvariable=self.sv_latencia_canal,
                                                   font=ctk.CTkFont(size=14))
        self.l_valor_latencia_canal.grid(row=8, column=0, padx=140, pady=(20, 5), sticky="e")

        self.l_flujo_aire_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                               text="Flujo de aire estimado: ",
                                               font=ctk.CTkFont(size=14, weight="bold"))
        self.l_flujo_aire_canal.grid(row=9, column=0, padx=80, pady=(20, 5), sticky="w")
        self.sv_flujo_aire_canal = ctk.StringVar(value="0 ml/min")
        self.l_valor_flujo_aire_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                                     textvariable=self.sv_flujo_aire_canal,
                                                     font=ctk.CTkFont(size=14))
        self.l_valor_flujo_aire_canal.grid(row=9, column=0, padx=80, pady=(20, 5), sticky="e")

        self.l_concentracion_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                                  text="Concentración estimada: ",
                                                  font=ctk.CTkFont(size=14, weight="bold"))
        self.l_concentracion_canal.grid(row=10, column=0, padx=75, pady=(20, 5), sticky="w")
        self.sv_concentracion_canal = ctk.StringVar(value="0 µg/m³")
        self.l_valor_concentracion_canal = ctk.CTkLabel(self.tv_prot_cal_est.tab("Estado"),
                                                        textvariable=self.sv_concentracion_canal,
                                                        font=ctk.CTkFont(size=14))
        self.l_valor_concentracion_canal.grid(row=10, column=0, padx=75, pady=(20, 5), sticky="e")

        #Botón de generación del informe de la sesión
        self.b_informe = ctk.CTkButton(self.tv_prot_cal_est.tab("Estado"),
                                       text="Generar informe de sesión",
                                       fg_color="#5172a4", text_color="#ffffff",
                                       corner_radius=10, border_width=1,
                                       border_color="#6ba2f4",
                                       command=self.generar_informe,
                                       font=ctk.CTkFont(size=18, weight="bold"))
        self.b_informe.grid(row=11, column=0, padx=31, pady=(30, 5), sticky="n")

    ##################################################
    # MÉTODOS ASOCIADOS A LOS BOTONES DE LA INTERFAZ
    ##################################################
    def b_buscar_dispositivos(self): return None
    def generar_informe(self): return None
    def canal_calibrado(self, canal): return None
    def iniciar_protocolo(self): return None
    def reiniciar_protocolo(self): return None
    def parar_protocolo(self): return None
    def iniciar_calibrado_velocidad(self): return None
    def reiniciar_calibrado_velocidad(self): return None
    def parar_calibrado_velocidad(self): return None
    def iniciar_calibrado_flujo(self): return None
    def reiniciar_calibrado_flujo(self): return None
    def parar_calibrado_flujo(self): return None
    def iniciar_calibrado_concentracion(self): return None
    def reiniciar_calibrado_concentracion(self): return None
    def parar_calibrado_concentracion(self): return None
    def iniciar_calibrado_latencia(self): return None
    def reiniciar_calibrado_latencia(self): return None
    def parar_calibrado_latencia(self): return None
    def iniciar_calibrado(self): return None
    def reiniciar_calibrado(self): return None
    def parar_calibrado(self): return None


if __name__ == "__main__":
    app = App()
    #ejecución del bucle principal de la interfaz gráfica
    app.mainloop()