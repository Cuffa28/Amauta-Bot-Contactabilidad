from google.oauth2.service_account import Credentials
import gspread
import streamlit as st
import datetime
import re
import unicodedata
import pandas as pd

# Autenticación básica por mail
usuarios_autorizados = [
    "facundo@amautainversiones.com",
    "florencia@amautainversiones.com",
    "jeronimo@amautainversiones.com",
    "agustin@amautainversiones.com",
    "regina@amautainversiones.com"
]

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acceso restringido")
    mail_ingresado = st.text_input("📧 Ingresá tu mail institucional", placeholder="tuusuario@amautainversiones.com")

    if st.button("Ingresar"):
        if mail_ingresado.strip().lower() in usuarios_autorizados:
            st.session_state.autenticado = True
            st.session_state.mail_ingresado = mail_ingresado.strip().lower()
            st.rerun()
        else:
            st.error("❌ No estás autorizado para ingresar a esta aplicación.")

    st.stop()

# CONFIG
import os
import json

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Leer el JSON desde variable de entorno
creds_json = os.environ.get("GOOGLE_CREDS_JSON")
if not creds_json:
    raise ValueError("La variable de entorno GOOGLE_CREDS_JSON no está definida.")

info = json.loads(creds_json)
creds = Credentials.from_service_account_info(info, scopes=SCOPE)

# Autenticación con gspread
client = gspread.authorize(creds)
spreadsheet = client.open("Esquema Comercial")
hoja_clientes = spreadsheet.worksheet("CLIENTES")

# Mapeo de códigos -> nombre de hoja
mapa_asesores = {
    "FA": "FACUNDO",
    "FL": "FLORENCIA",
    "AC": "AGUSTIN",
    "R": "REGINA",
    "JC": "JERONIMO"
}

def obtener_hoja_asesor(asesor):
    hoja = spreadsheet.worksheet(asesor)
    data = hoja.get_all_values()
    headers = [h.strip().upper() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    return df

# Función para normalizar nombres (mayúsculas, tildes, etc.)
def normalizar(texto):
    texto = texto.upper().replace(".", "").replace(",", "").strip()
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto

# Detección automática de tipo de contacto
def detectar_tipo(frase):
    frase = frase.lower()
    if any(p in frase for p in ["llamé a", "llame a", "me comuniqué con", "se llamó a", "hable con", "hable a", "se hablo con"]):
        return "LLAMADA"
    elif any(p in frase for p in ["le escribi a", "chatee con", "cheteé con", "envie un whatsapp a"]):
        return "MENSAJES"
    elif any(p in frase for p in ["me reuni con", "me junte con", "estuve con", "tuve un zoom con", "visite a", "tuve un meet con"]):
        return "REUNION"
    else:
        return "CONTACTO"

# Parsear la frase principal
def extraer_datos(frase):
    frase_normalizada = normalizar(frase)
    patron = r"(?:se hablo con|llame a|me comunique con|chatee con|le escribi a|me reuni con|visite a|estuve con|tuve un zoom con|tuve un meet con) ([A-Z\s]+) EL (\d{1,2}/\d{1,2}/\d{4}) POR (.+)"
    coincidencias = re.findall(patron, frase_normalizada, re.IGNORECASE)
    if coincidencias:
        cliente, fecha_str, motivo = coincidencias[0]
        fecha_contacto = datetime.datetime.strptime(fecha_str.strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
        return normalizar(cliente), fecha_contacto, motivo.strip()
    else:
        raise ValueError("No se pudo interpretar la frase. Usá el formato sugerido.")

# Buscar posibles coincidencias
def buscar_clientes_similares(cliente_input):
    nombres = hoja_clientes.col_values(1)
    cliente_input_normalizado = normalizar(cliente_input)
    partes_input = cliente_input_normalizado.split()
    coincidencias = []

    for i, nombre in enumerate(nombres, start=1):
        nombre_normalizado = normalizar(nombre)
        partes_nombre = nombre_normalizado.split()

        if len(partes_input) == 1:
            # Input corto: aceptar si cualquier palabra coincide parcialmente
            if any(p in parte for p in partes_input for parte in partes_nombre):
                coincidencias.append((i, nombre))
        else:
            # Input más largo: coincidencia más estricta
            match_parcial = all(p in partes_nombre for p in partes_input)
            match_exacto = cliente_input_normalizado in nombre_normalizado
            if match_parcial or match_exacto:
                coincidencias.append((i, nombre))

    return coincidencias

# Procesar contacto
def procesar_contacto(cliente_real, fila_cliente, frase, estado, proximo_contacto, nota):
    _, fecha_contacto, detalle = extraer_datos(frase)

    codigo_asesor = hoja_clientes.cell(fila_cliente, 2).value.strip()
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
    for i, fila in enumerate(data, start=2):  # Empieza en fila 2 (con encabezado)
        if normalizar(fila.get("CLIENTE", "")) == normalizar(cliente):
            hoja.update_cell(i, 5, "Hecho")       # Estado
            hoja.update_cell(i, 7, "")            # Limpiar Próximo Contacto
            break

# Función para recordatorios de contactos vencidos
def obtener_recordatorios_pendientes(mail_ingresado):
    hoy = datetime.datetime.now().date()
    proximos_dias = hoy + datetime.timedelta(days=3)
    pendientes = []

    # Obtener código del asesor logueado
    mail = mail_ingresado.strip().lower()
    asesor_codigo = None

    if "facundo" in mail:
        asesor_codigo = "FACUNDO"
    elif "florencia" in mail:
        asesor_codigo = "FLORENCIA"
    elif "jeronimo" in mail:
        asesor_codigo = "JERONIMO"
    elif "agustin" in mail:
        asesor_codigo = "AGUSTIN"
    elif "regina" in mail:
        asesor_codigo = "REGINA"

    asesores_a_buscar = [asesor_codigo] if asesor_codigo else mapa_asesores.values()

    for asesor in asesores_a_buscar:
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

# STREAMLIT – Crear pestañas organizadas
if st.session_state.get("autenticado"):

    tabs = st.tabs(["📞 Cargar Contactos", "📅 Recordatorios Pendientes"])

    # 📞 Pestaña 1: Registro de Contactos Comerciales
    with tabs[0]:
        st.title("📋 Registro de Contactos Comerciales")

        frase = st.text_input("📝 Escribí el contacto realizado:", placeholder="Ej: Se habló con Lavaque el 10/7/2025 por revisión de cartera")
        estado = st.selectbox("📌 Estado del contacto:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"])

        agendar = st.radio("📅 ¿Querés agendar un próximo contacto?", ["No", "Sí"])
        proximo_contacto = ""
        if agendar == "Sí":
            fecha_proxima = st.date_input("🗓️ ¿Cuándo sería el próximo contacto?", format="YYYY/MM/DD")
            proximo_contacto = fecha_proxima.strftime("%d/%m/%Y")

        nota = st.text_input("🗒️ ¿Querés agregar una nota?", placeholder="Ej: seguimiento de bonos")

        # Estado temporal
        for key in ["coincidencias", "cliente_input", "frase_guardada", "proximo_contacto_guardado", "nota_guardada", "estado_guardado", "hoja_registro_final"]:
            if key not in st.session_state:
                st.session_state[key] = [] if key == "coincidencias" else ""

        if st.button("Actualizar contacto"):
            try:
                cliente_input, _, _ = extraer_datos(frase)
                coincidencias = buscar_clientes_similares(cliente_input)

                if len(coincidencias) == 0:
                    st.error(f"⚠️ No se encontró ningún cliente similar a '{cliente_input}'.")
                elif len(coincidencias) == 1:
                    fila, cliente_real = coincidencias[0]
                    hoja_registro = procesar_contacto(cliente_real, fila, frase, estado, proximo_contacto, nota)
                    st.success(f"✅ Contacto registrado correctamente en la hoja: **{hoja_registro}**.")
                    st.session_state.cliente_input = cliente_real 
                    st.session_state.hoja_registro_final = hoja_registro
                else:
                    st.session_state.coincidencias = coincidencias
                    st.session_state.cliente_input = cliente_input
                    st.session_state.frase_guardada = frase
                    st.session_state.proximo_contacto_guardado = proximo_contacto
                    st.session_state.nota_guardada = nota
                    st.session_state.estado_guardado = estado

            except Exception as e:
                st.error(f"⚠️ Error procesando la frase: {str(e)}")

        if st.session_state.coincidencias:
            opciones = [nombre for _, nombre in st.session_state.coincidencias]
            seleccion = st.selectbox("❗Se encontraron varios clientes, elegí el correcto:", opciones)

            if st.button("Confirmar cliente"):
                coincidencias_validas = [fila for fila, nombre in st.session_state.coincidencias if nombre == seleccion]

                if coincidencias_validas:
                    fila_cliente = coincidencias_validas[0]
                    hoja_registro = procesar_contacto(
                        seleccion,
                        fila_cliente,
                        st.session_state.frase_guardada,
                        st.session_state.estado_guardado,
                        st.session_state.proximo_contacto_guardado,
                        st.session_state.nota_guardada
                    )

                    st.success(f"✅ Contacto registrado correctamente en la hoja: **{hoja_registro}**.")
                    st.write(f"🧍 Cliente cargado en historial: **{seleccion}**")

                    st.session_state.hoja_registro_final = hoja_registro
                    st.session_state.cliente_input = seleccion 
                    st.session_state.coincidencias = []

                    nuevo_registro = {
                        "Cliente": seleccion,
                        "Detalle": st.session_state.frase_guardada,
                        "Fecha": datetime.datetime.now().strftime("%d/%m/%Y"),
                        "Estado": st.session_state.estado_guardado,
                        "Nota": st.session_state.nota_guardada,
                        "Próximo contacto": st.session_state.proximo_contacto_guardado,
                        "Asesor": hoja_registro
                    }
                    st.session_state.historial.insert(0, nuevo_registro)
                    st.session_state.historial = st.session_state.historial[:90]
                else:
                    st.error("❌ Error interno: no se pudo encontrar la fila del cliente seleccionado.")

        # Historial de registros recientes
        if "historial" not in st.session_state:
            st.session_state.historial = []

        if st.session_state.hoja_registro_final:
            nuevo_registro = {
                "Cliente": st.session_state.cliente_input,
                "Detalle": st.session_state.frase_guardada,
                "Fecha": datetime.datetime.now().strftime("%d/%m/%Y"),
                "Estado": st.session_state.estado_guardado,
                "Nota": st.session_state.nota_guardada,
                "Próximo contacto": st.session_state.proximo_contacto_guardado,
                "Asesor": st.session_state.hoja_registro_final
            }
            st.session_state.historial.insert(0, nuevo_registro)
            st.session_state.historial = st.session_state.historial[:90]
            st.session_state.hoja_registro_final = ""  # ✅ Evita duplicaciones en el rerun

        if st.session_state.historial:
            st.subheader("📂 Historial reciente de cargas")
            df_historial = pd.DataFrame.from_records(st.session_state.historial)
            st.dataframe(df_historial, use_container_width=True)

        # ----------------- FILTROS Y DESCARGAS AVANZADAS -------------------
        st.subheader("🔍 Filtros sobre el historial")
        clientes_disponibles = sorted(set([h["Cliente"] for h in st.session_state.historial]))
        cliente_seleccionado = st.selectbox("Filtrar historial por cliente", options=["Todos"] + clientes_disponibles)

        if cliente_seleccionado != "Todos":
            historial_filtrado = [r for r in st.session_state.historial if r["Cliente"] == cliente_seleccionado]
        else:
            historial_filtrado = st.session_state.historial

        df_filtrado = pd.DataFrame(historial_filtrado)
        st.dataframe(df_filtrado, use_container_width=True)

        if st.checkbox("📖 Ver historial completo (sin límite)"):
            st.markdown("⚠️ Esto puede tardar unos segundos si tenés muchas entradas.")
            df_completo = pd.DataFrame(st.session_state.historial)
            st.dataframe(df_completo, use_container_width=True)

    # 📅 Pestaña 2: Recordatorios Pendientes
    with tabs[1]:
        st.title("📅 Recordatorios Pendientes")

        if "mail_ingresado" in st.session_state:
            recordatorios = obtener_recordatorios_pendientes(st.session_state.mail_ingresado)
        else:
            recordatorios = []

        if recordatorios:
            st.subheader("📣 Contactos a seguir")
            for i, (cliente, asesor, fecha, detalle, tipo) in enumerate(recordatorios):
                icono = "🔴" if tipo == "vencido" else "🟡"
                col1, col2 = st.columns([5, 1])

                with col1:
                    st.markdown(f"{icono} **{cliente}** (Asesor: {asesor}) – contacto para **{fecha}**. _Motivo_: {detalle or '-sin info-'}")
                with col2:
                    if st.button("✔️ Hecho", key=f"hecho_{i}"):
                        marcar_contacto_como_hecho(cliente, asesor)
                        st.experimental_rerun()
        else:
            st.success("🎉 No hay contactos pendientes. ¡Buen trabajo!")

