import customtkinter as ckt
""""
class App(ckt.CTk):
    def __init__(self):
        super().__init__()

        self.title("my app")
        self.geometry("400x150")
        self.grid_columnconfigure((0, 1), weight=1)

        self.button = ckt.CTkButton(self, text="my button", command=self.button_callback)
        self.button.grid(row=0, column=0, padx=20, pady=20, sticky="ew", columnspan=2)
        self.checkbox_1 = ckt.CTkCheckBox(self, text="checkbox 1")
        self.checkbox_1.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")
        self.checkbox_2 = ckt.CTkCheckBox(self, text="checkbox 2")
        self.checkbox_2.grid(row=1, column=1, padx=20, pady=(0, 20), sticky="w")
        
    def button_callback(self):
        print("button pressed")
"""
class MyCheckButtonFrame(ckt.CTkFrame):
    def __init__(self,master,title,values):
        super().__init__(master)
        self.title=title
        self.values=values  
        self.check_buttons=[]
        self.grid_columnconfigure(0,weight=1)

        self.title_label= ckt.CTkLabel(self, text=title, bg_color="transparent", fg_color="gray30", corner_radius=10)
        self.title_label.grid(row=0,column=0,padx=10,pady=10,sticky="we")

        for i,value in enumerate(values):
            check_button=ckt.CTkCheckBox(self, text=value)
            check_button.grid(row=i+1,column=0,padx=10,pady=(10,0),sticky="w")
            self.check_buttons.append(check_button)

class MyScrollableCheckButtonFrame(ckt.CTkScrollableFrame):
    def __init__(self,master,title,values):
        super().__init__(master)
        self.title=title
        self.values=values  
        self.check_buttons=[]
        #self.grid_columnconfigure(0,weight=1)

        self.title_label= ckt.CTkLabel(self, text=title, bg_color="transparent", fg_color="gray30", corner_radius=10)
        self.title_label.grid(row=0,column=0,padx=10,pady=10,sticky="we")

        for i,value in enumerate(values):
            check_button=ckt.CTkCheckBox(self, text=value)
            check_button.grid(row=i+1,column=0,padx=10,pady=(10,0),sticky="w")
            self.check_buttons.append(check_button)
    
    def get(self):
        checked_values=[]
        for check_button in self.check_buttons:
            if check_button.get():
                checked_values.append(check_button.cget("text"))
        return checked_values
    
class MyRadiobuttonFrame(ckt.CTkFrame):
    def __init__(self, master, title, values):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.values = values
        self.title = title
        self.radiobuttons = []
        self.variable = ckt.StringVar(value="")
        self.title = ckt.CTkLabel(self, text=self.title, fg_color="gray30", corner_radius=6)
        self.title.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")

        for i, value in enumerate(self.values):
            radiobutton = ckt.CTkRadioButton(self, text=value, value=value, variable=self.variable)
            radiobutton.grid(row=i + 1, column=0, padx=10, pady=(10, 0), sticky="w")
            self.radiobuttons.append(radiobutton)

    def get(self):
        return self.variable.get()

    def set(self, value):
        self.variable.set(value)

class App(ckt.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("OlfaMetric")
        self.geometry("500x300")
        self.grid_columnconfigure((0,1),weight=1)
        self.grid_rowconfigure(0,weight=1)
        """
        self.check_button_frame= ckt.CTkFrame(self)
        self.check_button_frame.grid(row=0,column=0,padx=10,pady=(10,0),sticky="nsw")
        self.check_button_1= ckt.CTkCheckBox(self.check_button_frame, text="checkbox 1")
        self.check_button_1.grid(row=0,column=0,padx=10,pady=(10,0),sticky="w")
        self.check_button_2= ckt.CTkCheckBox(self.check_button_frame, text="checkbox 2")
        self.check_button_2.grid(row=1,column=0,padx=10,pady=(10,0),sticky="w")
        """
        self.check_button_frame = MyScrollableCheckButtonFrame(self,"¿Puedes hacer un backflip?",
                                                               values=["Si","No","Puede","los findes","Solo cuando he comido bien","En pantalón corto"])
        self.check_button_frame.grid(row=0,column=0,padx=10,pady=(10,0),sticky="nsew")

        self.check_button_frame_2=MyRadiobuttonFrame(self,"¿Hacia delante o hacia atrás?",values=["Delante","Atrás"])
        self.check_button_frame_2.grid(row=0,column=1,padx=10,pady=(10,0),sticky="nsew")

        self.button= ckt.CTkButton(self, text="my button", command= self.button_callback)
        self.button.grid(row=3,column=0,padx=10,pady=10,sticky="we",columnspan=2)

    def button_callback(self):
        print("checked values:",self.check_button_frame.get())
        print("checked values 2:",self.check_button_frame_2.get())

app = App()
app.mainloop()

#help(ckt.CTkCheckBox.cget)