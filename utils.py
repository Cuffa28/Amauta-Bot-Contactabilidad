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
    patron = (
        r"(?:se hablo con|llame a|me comunique con|chatee con|le escribi a|"
        r"me reuni con|visite a|estuve con|tuve un zoom con|tuve un meet con) "
        r"([A-Z\s]+) EL (\d{1,2}/\d{1,2}/\d{4}) POR (.+)"
    )
    coincidencias = re.findall(patron, frase_normalizada, re.IGNORECASE)
    if coincidencias:
        cliente, fecha_str, motivo = coincidencias[0]
        fecha_contacto = datetime.datetime.strptime(fecha_str.strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
        return normalizar(cliente), fecha_contacto, motivo.strip()
    else:
        raise ValueError("No se pudo interpretar la frase. Usá el formato sugerido.")

