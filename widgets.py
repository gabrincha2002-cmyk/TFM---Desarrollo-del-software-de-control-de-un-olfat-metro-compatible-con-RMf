###################################################################
#Creación de widgets personalizados para la aplicación OlfaMetric #
###################################################################

import os
import customtkinter as ctk 
from CTkToolTip import CTkToolTip
import datetime
import logging
import config

class Canal(ctk.CTkFrame):
    def __init__(self, master, color_canal, num_canal, registro=None, actualizar_canal=None):
        super().__init__(master, fg_color="#343638", border_color="#4a4c4e", border_width=1, corner_radius=10)
        self.color_canal = color_canal
        self.num_canal = num_canal
        self.actualizar_canal = actualizar_canal
        self.registro = registro
        self.after_cronometro = None
        self.estado_canal= False
        self.crear_canal()

    def crear_canal(self):
        self.grid_columnconfigure((0,1), weight=1)
        self.grid_rowconfigure((0,1), weight=1)
        
        # Color canal
        self.l_color_canal = ctk.CTkLabel(self, text=f"Canal {self.color_canal}", font=ctk.CTkFont(size=20, weight="bold"))
        self.l_color_canal.grid(row=0, column=0, padx=(10,5), pady=10, sticky="w")

        # Olor del canal
        self.e_olor_canal = ctk.CTkEntry(self, placeholder_text="Olor del canal", font=ctk.CTkFont(size=20))
        self.e_olor_canal.grid(row=0, column=0, padx=10, pady=10, sticky="e")
        CTkToolTip(self.e_olor_canal, message="Introduce el nombre del olor que se va a utilizar en este canal.\nEste nombre se mostrará en los informes de sesión.", delay=0.5, justify="left", wraplength=300)

        #Tiempo activo del canal
        self.sv_tiempo_activo=ctk.StringVar(value="Tiempo activo: 00:00:00")  # Variable para almacenar el tiempo activo del canal
        self.l_tiempo_act_canal = ctk.CTkLabel(self, textvariable= self.sv_tiempo_activo, font=ctk.CTkFont(size=14))
        self.l_tiempo_act_canal.grid(row=2, column=0, padx=10, pady=(10,5), sticky="w")

        # Barra de progreso de la actividad
        self.pb_actividad_canal = ctk.CTkProgressBar(self, width=400, height=20)
        self.pb_actividad_canal.grid(row=3, column=0, padx=10, pady=(10,5), sticky="w")
        self.pb_actividad_canal.set(0.0)

        # Porcentaje de actividad
        self.l_porcentaje_act_canal = ctk.CTkLabel(self, text="0%", font=ctk.CTkFont(size=14))
        self.l_porcentaje_act_canal.grid(row=3, column=1, padx=10, pady=(5,10), sticky="w")
        self.l_porcentaje_act_canal.configure(text="0%")
        #Botón Activar

        self.b_activar_canal = ctk.CTkButton(self, text="Activar", fg_color="#85ad75",text_color="#ffffff", 
                                             hover_color="#488f51",corner_radius=10,border_color="#006400",border_width=1,
                                             font=ctk.CTkFont(size=16, weight="bold"), command=self.activar_canal)
        self.b_activar_canal.grid(row=5, column=0, padx=10, pady=(5,10), sticky="w")


        self.b_parar_canal = ctk.CTkButton(self, text="Parar", fg_color="#f56a6a",text_color="#ffffff",
                                             hover_color="#ee4242",corner_radius=10,border_color="#ff0000",border_width=1,
                                             font=ctk.CTkFont(size=16, weight="bold"), command=self.parar_canal)
        self.b_parar_canal.grid(row=5, column=1, padx=10, pady=(5,10), sticky="w")

    def cronometro(self,tiempo):
        if self.estado_canal:
            self.sv_tiempo_activo.set(f"Tiempo activo: {tiempo.strftime('%H:%M:%S')}")
            self.after_cronometro = self.after(1000, lambda: self.cronometro(tiempo + datetime.timedelta(seconds=1)))

    def resetear_cronometro(self):
        self.sv_tiempo_activo.set("Tiempo activo: 00:00:00")

    def pausar_cronometro(self):
        if self.after_cronometro:
            self.after_cancel(self.after_cronometro)
            self.after_cronometro = None
    
    def actualizar_barra_progreso(self, valor):
        self.pb_actividad_canal.set(valor)
        

    def activar_canal(self,tiempo_inicial=datetime.datetime.strptime("00:00:00", "%H:%M:%S")):
        if not self.estado_canal:
            self.estado_canal=True
            self.cronometro(tiempo_inicial)
            self.configure(fg_color="#256F2F", border_color="#7DEB7D", border_width=4)  # Cambia el fondo del canal para indicar que está activo
            self.b_activar_canal.configure(text="En marcha", fg_color="#70c64e",text_color="#ffffff",border_color="#006400",border_width=1,font=ctk.CTkFont(size=14, weight="bold"))
            #FALTA INCLUIR FUNCIONALIDAD PARA ACTIVAR EL CANAL EN EL ESP32
            if self.registro:
                self.registro(f"Canal {self.color_canal} ({self.e_olor_canal.get()}) ACTIVADO")
            
            if self.actualizar_canal:
                self.actualizar_canal(self.num_canal,"activar")
            

    def parar_canal(self):
        if self.estado_canal:
            self.estado_canal=False
            self.pausar_cronometro()
            # se congela la barra de progreso al parar
            self.pb_actividad_canal.stop()
            self.l_porcentaje_act_canal.configure(text=self.pb_actividad_canal.get())
        
            self.configure(fg_color="#343638", border_color="#4a4c4e", border_width=1)  # Restaura el fondo del canal para indicar que está inactivo
            self.b_activar_canal.configure(text="Activar", fg_color="#85ad75",text_color="#ffffff",border_color="#006400",border_width=1,
                font=ctk.CTkFont(size=14, weight="bold"))
            #FALTA INCLUIR FUNCIONALIDAD PARA PARAR EL CANAL EN EL ESP32
            #self.canal_anterior.set(f"Canal {self.color_canal} ({self.e_olor_canal.get()})")
            #print(f"Canal {self.color_canal} ({self.e_olor_canal.get()}")
            if self.registro:
                olor = self.e_olor_canal.get() if self.e_olor_canal.winfo_exists() else ""
                self.registro(f"Canal {self.color_canal} ({olor}) DETENIDO")
            
            if self.actualizar_canal:
                self.actualizar_canal(self.num_canal,"parar")
            


class SpinboxCTk(ctk.CTkFrame):
    def __init__(self, master, valor=120,valor_min=0, valor_max=9999999, escalon=1
                 , border_width=0, corner_radius=10, width=120, height=30):
        super().__init__(master, fg_color = "#242424",width=width, height=height, border_width=border_width, corner_radius=corner_radius)
        self.valor_min = valor_min
        self.valor_max = valor_max
        self.escalon = escalon
        self.valor = ctk.StringVar(value=valor)
        self.crear_spinboxCTk()

    def crear_spinboxCTk(self):
        f_spinbox = ctk.CTkFrame(self,fg_color="#242424", bg_color="#242424")
        f_spinbox.grid_columnconfigure((0,2),weight=0)
        f_spinbox.grid_columnconfigure(1,weight=0)
        f_spinbox.grid(row=0, column=0, sticky="w", padx=10, pady=10,)

        self.b_decrementar = ctk.CTkButton(f_spinbox,bg_color="#242424",fg_color="#0a5f70", text="-", width=30, command=self.decrementar,font=ctk.CTkFont(size=14, weight="bold"),border_color="#0a5f70", border_width=1)
        self.b_decrementar.grid(row=0,column=0, padx=5, pady=5, sticky="w")

        self.e_spinbox = ctk.CTkEntry(f_spinbox,bg_color="#242424", fg_color="#242424", textvariable=self.valor, font=ctk.CTkFont(size=14))
        self.e_spinbox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.b_incrementar = ctk.CTkButton(f_spinbox, bg_color="#242424", fg_color="#0a5f70",text="+", width=30, command=self.incrementar,font=ctk.CTkFont(size=14, weight="bold"),border_color="#0a5f70", border_width=1)
        self.b_incrementar.grid(row=0,column=2, padx=5, pady=5, sticky="e")

    def incrementar(self):
        try:
            valor_actual = int(self.valor.get())
            valor_final = valor_actual + self.escalon
            if valor_final <= self.valor_max:
                self.valor.set(valor_final)
        except ValueError:
            pass

    def decrementar(self):
        try:
            valor_actual = int(self.valor.get())
            valor_final = valor_actual - self.escalon
            if valor_final >= self.valor_min:
                self.valor.set(valor_final)
        except ValueError:
            pass
    
    def get(self):
        try:
            return int(self.valor.get())
        except ValueError:
            return self.valor_min
        
    def set(self, valor):
        self.valor.set(int(valor)) 

class FrameDeslizante(ctk.CTkScrollableFrame):
    def __init__(self, master,fg_color,border_color="#4a4c4e", border_width=1, corner_radius=10):
        super().__init__(master,fg_color=fg_color,border_color=border_color, border_width=border_width, corner_radius=corner_radius)
        self.fg_color = fg_color
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)  # Cabecera se expande
        
class Consola(ctk.CTkTextbox):
    def __init__(self, master):
        super().__init__(master)

        self.logger = logging.getLogger("olfametric.consola")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  #Se evita que los mensajes se propaguen a la raíz del logger

        if not self.logger.handlers:
            archivo_handler = logging.FileHandler(os.path.join(config.DIRECTORIO_HISTORIAL, "consola.log"), mode="a", encoding="utf-8")
            self.logger.addHandler(archivo_handler)




        self.crear()
        

    def crear(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Consola", text_color="#458B8D", font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, padx=5, pady=(5,5), sticky="nw")

        self.t_registro=ctk.CTkTextbox(self, width=1000, height=150, font=ctk.CTkFont(size=14),)
        self.t_registro.grid(row=1, column=0, padx=10, pady=(10,5), sticky="nsew")

    def registro(self, mensaje, nivel="INFO"):
        hora = datetime.datetime.now().strftime("%H:%M:%S")
        mensaje_final = f"{hora}- {nivel}- {mensaje}\n"
        self.t_registro.insert(index="end", text=mensaje_final)
        self.t_registro.see("end")

        #Se asigna el nivel de logging correspondiente según el nivel proporcionado
        if nivel.upper() == 'AVISO':
            nivel_logging = logging.WARNING
        else:
            nivel_logging = getattr(logging, nivel.upper(), logging.INFO)
        #Se registra el mensaje en el logger de la consola, que a su vez lo escribirá en el archivo de log
        self.logger.log(nivel_logging, mensaje_final)

    def limpiar_registro(self):
        self.t_registro.delete("1.0","end")  