import datetime
import re
import unicodedata

def normalizar(texto):
    texto = texto.upper().replace(".", "").replace(",", "").strip()
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto

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
        # patrón para frases tipo: Se contactó con CLIENTE el DD/MM/YYYY por MOTIVO
        r"SE CONTACTO CON (.*?) EL (\d{1,2}/\d{1,2}/\d{4}) POR (.*)",

        # patrón para frases tipo: Hablé con CLIENTE el DD/MM/YYYY por MOTIVO
        r"(?:HABLE CON|LLAME A|ME COMUNIQUE CON|CHATEE CON|LE ESCRIBI A|ME REUNI CON|VISITE A|ESTUVE CON|TUVE UN ZOOM CON|TUVE UN MEET CON) (.*?) EL (\d{1,2}/\d{1,2}/\d{4}) POR (.*)",
    ]

    for patron in patrones:
        coincidencias = re.findall(patron, frase_normalizada, re.IGNORECASE)
        if coincidencias:
            cliente, fecha_str, motivo = coincidencias[0]
            fecha_contacto = datetime.datetime.strptime(fecha_str.strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
            return normalizar(cliente), fecha_contacto, motivo.strip()

    raise ValueError("No se pudo interpretar la frase. Usá el formato sugerido.")


