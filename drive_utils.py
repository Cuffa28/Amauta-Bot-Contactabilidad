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

def procesar_contacto(cliente_real, fila_cliente, frase, estado, proximo_contacto, nota, extraer_datos_fn, detectar_tipo_fn):
    df_clientes = obtener_hoja_clientes()
    codigo_asesor = df_clientes.iloc[fila_cliente - 2]["ASESOR/A"]
    hoja_nombre = obtener_hoja_nombre(codigo_asesor)
    hoja_contacto = spreadsheet.worksheet(hoja_nombre)

    cliente_col = df_clientes.columns.get_loc("CLIENTE") + 1
    fila_real = fila_cliente

    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y")
    tipo_contacto = detectar_tipo_fn(frase)

    hoja_contacto.update_cell(fila_real, cliente_col + 1, fecha_actual)
    hoja_contacto.update_cell(fila_real, cliente_col + 2, tipo_contacto)
    hoja_contacto.update_cell(fila_real, cliente_col + 3, frase)
    hoja_contacto.update_cell(fila_real, cliente_col + 4, estado)
    hoja_contacto.update_cell(fila_real, cliente_col + 5, nota)
    hoja_contacto.update_cell(fila_real, cliente_col + 6, proximo_contacto)

    return hoja_nombre

def marcar_contacto_como_hecho(cliente, asesor):
    hoja_nombre = mapa_asesores.get(asesor)
    if not hoja_nombre:
        raise ValueError("Asesor desconocido")

    hoja = spreadsheet.worksheet(hoja_nombre)
    df = pd.DataFrame(hoja.get_all_records())
    for i, row in df.iterrows():
        if normalizar(row["CLIENTE"]) == normalizar(cliente):
            fila = i + 2
            hoja.update_cell(fila, 6, "Hecho")
            hoja.update_cell(fila, 11, "")
            return

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
