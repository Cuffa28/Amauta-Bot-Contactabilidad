import datetime
import re
from drive_utils import normalizar

def detectar_tipo(frase):
    frase = frase.lower()

    # 🛠️ Nuevos patrones explícitos (para modo guiado)
    if "se realizo una llamada" in frase or "se realizó una llamada" in frase:
        return "LLAMADA"
    if "se realizo un mensaje" in frase or "se realizó un mensaje" in frase:
        return "MENSAJES"
    if "se realizo una reunion" in frase or "se realizó una reunión" in frase:
        return "REUNION"

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
        r"SE REALIZO UNA .*? CON (.*?) EL (\d{1,2}/\d{1,2}/\d{4}) POR (.*)",  # 🆕 para carga guiada
    ]

    for patron in patrones:
        coincidencias = re.findall(patron, frase_normalizada, re.IGNORECASE)
        if coincidencias:
            cliente, fecha_str, motivo = coincidencias[0]
            fecha_contacto = datetime.datetime.strptime(fecha_str.strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
            return normalizar(cliente), fecha_contacto, motivo.strip()

    raise ValueError("No se pudo interpretar la frase. Usá el formato sugerido.")


