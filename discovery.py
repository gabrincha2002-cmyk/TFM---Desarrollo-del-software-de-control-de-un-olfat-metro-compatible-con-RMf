###################################################################
# Funcion para buscar un dispositivo en la red local mediante mDNS#
###################################################################

import time
import zeroconf as zc

SERVICIO_MDNS = "_olfatometro._tcp.local."
TIMEOUT_SEGUNDOS = 5

def buscar_mdns():
    #se trata de un diccinario que podrá ser modificado por la clase oyente, y guarda la
    #información relacionada
    direccion_controlador = {"ip": None, "puerto" : None}

    class Oyente:
        #la funcion add_service se dispara automáticamente cuendo encuentra un dispositivo en la
        #red que coincide con el tipo de servicio que se busca
        def add_service(self, zconf, tipo, nombre):
            info =zconf.get_service_info(tipo,nombre)
            if info:
                direccion_controlador["ip"] = info.parsed_addresses()[0]
                direccion_controlador["puerto"] = info.port
            pass

        def remove_service(self, zconf, tipo, nombre):
            pass

        def update_service(self, zconf, tipo, nombre):
            pass

    zconf = zc.Zeroconf()
    #OJO: "_esp32._tcp.local." tiene una estructura fija
    #_esp32   → nombre del servicio (debe coincidir con el ESP32)
    #._tcp         → protocolo de transporte
    #.local.       → dominio mDNS (siempre este, con el punto final)
    #El único propósito de la variable buscador es mantener vivo el objeto 
    # en memoria durante el bucle de espera.
    _buscador = zc.ServiceBrowser(zconf, SERVICIO_MDNS, Oyente())
        

    """
    Como ServiceBrowser es asíncrono (trabaja en su propio hilo interno), necesitas 
    esperar a que encuentre algo. El bucle comprueba cada 100ms si ya se encontró la IP.
    Si pasan 5 segundos sin resultado, sale del bucle. zconf.close() libera el socket,
    siempre hay que cerrarlo.
    """
    tiempo_inicio = time.time()
    while direccion_controlador["ip"] is None and time.time() - tiempo_inicio < TIMEOUT_SEGUNDOS:
        time.sleep(0.1)

    zconf.close()

    if direccion_controlador["ip"]:
        #se devuelve la URI del dispositivo encontrado, que es la IP y el puerto en formato ws://IP:PUERTO
        return f'ws://{direccion_controlador["ip"]}:{direccion_controlador["puerto"]}' 
    return None
        
