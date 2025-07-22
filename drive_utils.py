import os
import json
import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import unicodedata

# -------------------- Normalización --------------------

def normalizar(texto):
    texto = texto.upper().replace(".", "").replace(",", "").strip()
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto

# -------------------- Configuración --------------------

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
mapa_asesores = {
    "FA": "FACUNDO",
    "FL": "FLORENCIA",
    "AC": "AGUSTIN",
    "R": "REGINA",
    "JC": "JERONIMO"
}

client = None
spreadsheet = None

def inicializar_client():
    global client, spreadsheet
    if client and spreadsheet:
        return

    creds_json = os.environ.get("GOOGLE_CREDS_JSON")
    if not creds_json:
        raise ValueError("La variable de entorno GOOGLE_CREDS_JSON no está definida.")

    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPE)
    client = gspread.authorize(creds)
    spreadsheet = client.open("Esquema Comercial")

# -------------------- Funciones principales --------------------

def obtener_hoja_clientes():
    inicializar_client()
    return pd.DataFrame(spreadsheet.worksheet("CLIENTES").get_all_records())

def obtener_hoja_nombre(codigo_asesor):
    return mapa_asesores.get(codigo_asesor, "DESCONOCIDO")

def procesar_contacto(cliente_real, fila_dummy, frase, estado, proximo_contacto, nota, extraer_datos_fn, detectar_tipo_fn):
    inicializar_client()
    cliente_detectado, _, motivo = extraer_datos_fn(frase)
    df_clientes = obtener_hoja_clientes()

    try:
        _, cliente_nombre_real, asesor_codigo = buscar_cliente_normalizado(cliente_detectado, df_clientes)
    except ValueError as e:
        raise ValueError(f"[Procesar contacto] {e}")

    hoja_nombre = mapa_asesores.get(asesor_codigo)
    if not hoja_nombre:
        raise ValueError(f"Asesor desconocido para código '{asesor_codigo}'")

    hoja = spreadsheet.worksheet(hoja_nombre)
    fila_cliente = obtener_fila_para_cliente(cliente_real, hoja_nombre)
    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y")
    tipo_contacto = detectar_tipo_fn(frase)

    hoja.update(f"A{fila_cliente}:G{fila_cliente}", [[
        cliente_real,
        tipo_contacto,
        motivo,
        fecha_actual,
        estado,
        nota,
        proximo_contacto
    ]])

    return hoja_nombre

def marcar_contacto_como_hecho(cliente, asesor):
    inicializar_client()
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
    inicializar_client()
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

def buscar_cliente_normalizado(nombre_cliente, df_clientes):
    normal_input = normalizar(nombre_cliente)

    exactas = [
        (i + 2, row["CLIENTE"], row["ASESOR/A"])
        for i, row in df_clientes.iterrows()
        if normalizar(row["CLIENTE"]) == normal_input
    ]
    if len(exactas) == 1:
        return exactas[0]

    parciales = list({
        (i + 2, row["CLIENTE"], row["ASESOR/A"])
        for i, row in df_clientes.iterrows()
        if normal_input in normalizar(row["CLIENTE"]) or normalizar(row["CLIENTE"]) in normal_input
    })
    parciales = sorted(parciales, key=lambda x: x[1])
    if len(parciales) == 1:
        return parciales[0]

    if not exactas and not parciales:
        raise ValueError(f"No se encontró al cliente: {nombre_cliente}")
    else:
        raise ValueError(f"Se encontraron múltiples coincidencias para: {nombre_cliente}")

def obtener_fila_para_cliente(cliente_real, hoja_nombre):
    inicializar_client()
    hoja = spreadsheet.worksheet(hoja_nombre)
    df = pd.DataFrame(hoja.get_all_records())

    for i, row in df.iterrows():
        if normalizar(row.get("CLIENTE", "")) == normalizar(cliente_real):
            return i + 2

    for i, row in df.iterrows():
        if not str(row.get("CLIENTE", "")).strip():
            return i + 2

    fecha = datetime.datetime.now().strftime("%d/%m/%Y")
    hoja.append_row([
        cliente_real, "", "", fecha, "", "", ""
    ])
    return len(df) + 2

def agregar_cliente_si_no_existe(nombre_cliente, asesor):
    inicializar_client()
    hoja = spreadsheet.worksheet("CLIENTES")
    df = pd.DataFrame(hoja.get_all_records())

    if any(normalizar(nombre_cliente) == normalizar(row["CLIENTE"]) for _, row in df.iterrows()):
        return  # Ya existe

    hoja.append_row([nombre_cliente, asesor])

