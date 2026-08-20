# OlfaMetric

Software de control del olfatómetro MRI-compatible para el estudio 
de la epilepsia mediante fMRI.

Desarrollado como parte del TFM del Máster Universitario en Ingeniería 
Biomédica de la Universidad Internacional de Valencia (VIU), en 
colaboración con el grupo de Neuroingeniería de la UMH.

## Descripción

Breve párrafo (5-8 líneas) sobre qué hace la app: control de válvula 
rotatoria por WiFi, protocolos de exposición configurables, telemetría 
en tiempo real, exportación BIDS-compatible, activación manual de canales, etc.

## Requisitos

- Python 3.10 o superior
- Sistema operativo: Windows 10/11 (probado)
- Red WiFi local con el ESP32 accesible
- Hardware: olfatómetro con controlador ESP32-WROOM-32U

## Instalación

Instrucciones paso a paso para clonar el repositorio, crear el 
entorno virtual, instalar dependencias.

## Ejecución

Cómo lanzar la app (`python main.py`). Cómo lanzar el simulador si 
no hay hardware disponible (`python olfato_sim.py`).

## Estructura del proyecto

Un pequeño árbol de carpetas con una línea por archivo. 
Aquí se  referencia el documento de arquitectura (Google Docs).

## Uso básico / Manual de Usuario

Guía rápida del flujo típico: 
1. Conectar dispositivo (mDNS)
2. Configurar protocolo
3. Calibrar canales
4. Iniciar sesión
5. Exportar informe

## Dependencias principales

Lista con enlaces: customtkinter, websockets, matplotlib, reportlab, etc.

## Autores y contacto

Gabriel Collado Santamaría (email VIU) - Estudiante  
Directora TFT - Lilibeth Zambrano Martinez  
Asesor Externo - Eduardo Fernández Jover

## Licencia
Todos los derechos reservados (PENDIENTE DE DECIDIR CON UMH)