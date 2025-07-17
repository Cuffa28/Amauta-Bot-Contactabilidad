import datetime
import re
from drive_utils import obtener_hoja_clientes, normalizar

def detectar_tipo(frase):
    frase = frase.lower()
    if any(p in frase for p in [
        "llamé a", "llame a", "me comuniqué con", "se llamó a", 
        "hable con", "hable a", "se hablo con"
    ]):
        return "LLAMADA"
    elif any(p in frase for p in [
        "le escribi a", "chatee con", "cheteé con", "envie un whatsapp a"
    ]):
        return "MENSAJES"
    elif any(p in frase for p in [
        "me reuni con", "me junte con", "estuve con", 
        "tuve un zoom con", "visite a", "tuve un meet con"
    ]):
        return "REUNION"
    else:
        return "CONTACTO"

def extraer_datos(frase):
    frase_normalizada = normalizar(frase)

    patrones = [
        r"SE CONTACTO CON (.*?) EL (\d{1,2}/\d{1,2}/\d{4}) POR (.*)",
        r"(?:HABLE CON|LLAME A|ME COMUNIQUE CON|CHATEE CON|LE ESCRIBI A|ME REUNI CON|VISITE A|ESTUVE CON|TUVE UN ZOOM CON|TUVE UN MEET CON) (.*?) EL (\d{1,2}/\d{1,2}/\d{4}) POR (.*)",
    ]

    for patron in patrones:
        coincidencias = re.findall(patron, frase_normalizada, re.IGNORECASE)
        if coincidencias:
            cliente, fecha_str, motivo = coincidencias[0]
            fecha_contacto = datetime.datetime.strptime(fecha_str.strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
            return normalizar(cliente), fecha_contacto, motivo.strip()

    raise ValueError("No se pudo interpretar la frase. Usá el formato sugerido.")

def buscar_clientes_similares_por_asesor(cliente_input, asesor_input):
    df_clientes = obtener_hoja_clientes()
    nombres = df_clientes["CLIENTE"].tolist()
    asesores = df_clientes["ASESOR/A"].tolist()

    cliente_input_normalizado = normalizar(cliente_input)
    coincidencias = []
    coincidencia_exacta = None

    for i, (nombre, asesor) in enumerate(zip(nombres, asesores), start=2):
        if asesor != asesor_input:
            continue

        nombre_normalizado = normalizar(nombre)

        if cliente_input_normalizado == nombre_normalizado:
            coincidencia_exacta = (i, nombre)
            break
        elif cliente_input_normalizado in nombre_normalizado or nombre_normalizado in cliente_input_normalizado:
            coincidencias.append((i, nombre))

    if coincidencia_exacta:
        return [coincidencia_exacta]
    return coincidencias
