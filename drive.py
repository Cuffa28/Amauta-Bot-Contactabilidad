
import os
import json
import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from utils import normalizar

# --- Autenticación con Google ---
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
    data = hoja_clientes.get_all_records()
    return pd.DataFrame(data)

def obtener_hoja_asesor(nombre):
    hoja = spreadsheet.worksheet(nombre)
    data = hoja.get_all_values()
    headers = [h.strip().upper() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    return df

def procesar_contacto(cliente_real, fila_cliente, frase, estado, proximo_contacto, nota, extraer_datos, detectar_tipo):
    _, fecha_contacto, detalle = extraer_datos(frase)

    df_clientes = obtener_hoja_clientes()
    codigo_asesor = df_clientes.iloc[fila_cliente - 1]["ASESOR/A"]
    hoja_nombre = mapa_asesores.get(codigo_asesor)
    if not hoja_nombre:
        raise ValueError(f"El cliente '{cliente_real}' no tiene un asesor válido asignado.")

    hoja_destino = spreadsheet.worksheet(hoja_nombre)
    data = hoja_destino.get_all_records()

    fila_index = None
    for i, fila in enumerate(data, start=2):
        if normalizar(fila["CLIENTE"]) == normalizar(cliente_real):
            fila_index = i
            break

    tipo = detectar_tipo(frase)

    if fila_index:
        hoja_destino.update_cell(fila_index, 2, tipo)
        hoja_destino.update_cell(fila_index, 3, detalle)
        hoja_destino.update_cell(fila_index, 4, fecha_contacto)
        hoja_destino.update_cell(fila_index, 5, estado)
        hoja_destino.update_cell(fila_index, 6, nota if nota else "-")
        hoja_destino.update_cell(fila_index, 7, proximo_contacto if proximo_contacto else "")
    else:
        hoja_destino.append_row([
            cliente_real, tipo, detalle, fecha_contacto, estado,
            nota if nota else "-", proximo_contacto if proximo_contacto else ""
        ])
    return hoja_nombre

def marcar_contacto_como_hecho(cliente, asesor):
    hoja = spreadsheet.worksheet(asesor)
    data = hoja.get_all_records()
    for i, fila in enumerate(data, start=2):
        if normalizar(fila.get("CLIENTE", "")) == normalizar(cliente):
            hoja.update_cell(i, 5, "Hecho")
            hoja.update_cell(i, 7, "")
            break

def obtener_recordatorios_pendientes(mail):
    hoy = datetime.datetime.now().date()
    proximos_dias = hoy + datetime.timedelta(days=3)
    pendientes = []

    # Código asesor desde mail
    mail = mail.lower()
    codigo = None
    if "facundo" in mail:
        codigo = "FACUNDO"
    elif "florencia" in mail:
        codigo = "FLORENCIA"
    elif "jeronimo" in mail:
        codigo = "JERONIMO"
    elif "agustin" in mail:
        codigo = "AGUSTIN"
    elif "regina" in mail:
        codigo = "REGINA"

    asesores = [codigo] if codigo else mapa_asesores.values()

    for asesor in asesores:
        hoja = spreadsheet.worksheet(asesor)
        data = hoja.get_all_records()
        for fila in data:
            fecha_str = fila.get("PRÓXIMO CONTACTO")
            cliente = fila.get("CLIENTE", "Sin nombre")
            if fecha_str:
                try:
                    fecha = datetime.datetime.strptime(fecha_str.strip(), "%d/%m/%Y").date()
                    detalle = fila.get("DETALLE", "-sin info-")
                    if fecha < hoy:
                        tipo = "vencido"
                    elif fecha <= proximos_dias:
                        tipo = "proximo"
                    else:
                        continue
                    pendientes.append((cliente, asesor, fecha_str, detalle, tipo))
                except ValueError:
                    continue

    return pendientes