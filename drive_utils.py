import os
import json
import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import unicodedata

def normalizar(texto):
    texto = texto.upper().replace(".", "").replace(",", "").strip()
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS_JSON")
if not creds_json:
    raise ValueError("La variable de entorno GOOGLE_CREDS_JSON no está definida.")

info = json.loads(creds_json)
creds = Credentials.from_service_account_info(info, scopes=SCOPE)
client = gspread.authorize(creds)

spreadsheet = client.open("Esquema Comercial")
hoja_clientes = spreadsheet.worksheet("CLIENTES")

mapa_asesores = {
    "FA": "FACUNDO",
    "FL": "FLORENCIA",
    "AC": "AGUSTIN",
    "R": "REGINA",
    "JC": "JERONIMO"
}

def obtener_hoja_clientes():
    return pd.DataFrame(hoja_clientes.get_all_records())

def obtener_hoja_nombre(codigo_asesor):
    return mapa_asesores.get(codigo_asesor, "DESCONOCIDO")

def procesar_contacto(cliente_real, fila_dummy, frase, estado, proximo_contacto, nota, extraer_datos_fn, detectar_tipo_fn):
    hoja_nombre = mapa_asesores.get(extraer_datos_fn(frase), "DESCONOCIDO")
    hoja = spreadsheet.worksheet(hoja_nombre)
    df = pd.DataFrame(hoja.get_all_records())

    # Buscar primera fila vacía (donde no hay cliente)
    fila_disponible = None
    for i, row in df.iterrows():
        if not str(row.get("CLIENTE", "")).strip():
            fila_disponible = i + 2  # sumar 2 por el header y base 0
            break

    # Si no hay fila vacía, agregar una nueva
    if fila_disponible is None:
        fila_disponible = len(df) + 2
        hoja.add_rows(1)

    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y")
    tipo_contacto = detectar_tipo_fn(frase)

    hoja.update_cell(fila_disponible, 1, cliente_real)        # CLIENTE (col A)
    hoja.update_cell(fila_disponible, 2, tipo_contacto)        # Tipo (col B)
    hoja.update_cell(fila_disponible, 3, frase)                # Detalles (col C)
    hoja.update_cell(fila_disponible, 4, fecha_actual)         # Fecha último contacto (col D)
    hoja.update_cell(fila_disponible, 5, estado)               # Estado (col E)
    hoja.update_cell(fila_disponible, 6, nota)                 # Notas (col F)
    hoja.update_cell(fila_disponible, 7, proximo_contacto)     # Próximo contacto (col G)

    return hoja_nombre

def marcar_contacto_como_hecho(cliente, asesor):
    hoja_nombre = mapa_asesores.get(asesor)
    if not hoja_nombre:
        raise ValueError("Asesor desconocido")

    hoja = spreadsheet.worksheet(hoja_nombre)
    df = pd.DataFrame(hoja.get_all_records())

    for i, row in df.iterrows():
        if normalizar(row["CLIENTE"]) == normalizar(cliente):
            fila = i + 2  # porque los headers están en la fila 1
            hoja.update_cell(fila, 5, "Hecho")  # Columna E (Estado)
            hoja.update_cell(fila, 7, "")       # Columna G (Próximo contacto)
            return

    # Si no se encontró al cliente, buscar la primera fila vacía y crearla
    for i, row in df.iterrows():
        if not row["CLIENTE"]:  # celda vacía
            fila = i + 2
            hoja.update_cell(fila, 1, cliente)  # A: CLIENTE
            hoja.update_cell(fila, 5, "Hecho")  # E: Estado
            hoja.update_cell(fila, 7, "")       # G: Próximo contacto
            return

    # Si no hay filas vacías, error explícito
    raise ValueError(f"No se encontró fila vacía para cliente '{cliente}' en hoja '{hoja_nombre}'")

def obtener_recordatorios_pendientes(mail_usuario):
    codigo = mail_usuario.split("@")[0][:2].upper()
    hoja_nombre = mapa_asesores.get(codigo)
    if not hoja_nombre:
        return []

    hoja = spreadsheet.worksheet(hoja_nombre)
    df = pd.DataFrame(hoja.get_all_records())

    pendientes = []
    hoy = datetime.datetime.now().date()

    for i, row in df.iterrows():
        cliente = row["CLIENTE"]
        fecha_str = row.get("PRÓXIMO CONTACTO", "")
        detalle = row.get("NOTA", "")
        estado = row.get("ESTADO", "")

        if fecha_str:
            try:
                fecha = datetime.datetime.strptime(fecha_str, "%d/%m/%Y").date()
                tipo = "vencido" if fecha < hoy and estado != "Hecho" else "pendiente"
                if tipo == "vencido" or fecha == hoy:
                    pendientes.append((cliente, codigo, fecha.strftime("%d/%m/%Y"), detalle, tipo))
            except ValueError:
                continue
    return pendientes
