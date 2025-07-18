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
    cliente_detectado, _, motivo = extraer_datos_fn(frase)
    df_clientes = obtener_hoja_clientes()

    fila_cliente_df = df_clientes[df_clientes["CLIENTE"].apply(normalizar) == normalizar(cliente_detectado)]
    if fila_cliente_df.empty:
        raise ValueError(f"Cliente no encontrado: {cliente_detectado}")

    asesor_codigo = fila_cliente_df["ASESOR/A"].values[0]
    hoja_nombre = mapa_asesores.get(asesor_codigo)
    if not hoja_nombre:
        raise ValueError(f"Asesor desconocido para código '{asesor_codigo}'")

    hoja = spreadsheet.worksheet(hoja_nombre)
    df = pd.DataFrame(hoja.get_all_records())

    fila_cliente = None
    for i, row in df.iterrows():
        if normalizar(row.get("CLIENTE", "")) == normalizar(cliente_real):
            fila_cliente = i + 2
            break

    if fila_cliente is None:
        for i, row in df.iterrows():
            if not str(row.get("CLIENTE", "")).strip():
                fila_cliente = i + 2
                break

    if fila_cliente is None:
        fila_cliente = len(df) + 2
        hoja.add_rows(1)

    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y")
    tipo_contacto = detectar_tipo_fn(frase)

    hoja.update_cell(fila_cliente, 1, cliente_real)       # A: Cliente
    hoja.update_cell(fila_cliente, 2, tipo_contacto)       # B: Tipo
    hoja.update_cell(fila_cliente, 3, motivo)              # C: Detalles (solo el motivo)
    hoja.update_cell(fila_cliente, 4, fecha_actual)        # D: Fecha último contacto
    hoja.update_cell(fila_cliente, 5, estado)              # E: Estado
    hoja.update_cell(fila_cliente, 6, nota)                # F: Notas
    hoja.update_cell(fila_cliente, 7, proximo_contacto)    # G: Próximo contacto

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
            hoja.update_cell(fila, 5, "Hecho")
            hoja.update_cell(fila, 7, "")
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
        cliente = row.get("CLIENTE", "")
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

