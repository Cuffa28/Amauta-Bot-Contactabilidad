import streamlit as st
import pandas as pd
from drive import (
    obtener_hoja_clientes,
    procesar_contacto,
    marcar_contacto_como_hecho,
    obtener_recordatorios_pendientes
)
from historial import guardar_en_historial
from utils import normalizar, extraer_datos, detectar_tipo

# Autenticación por mail
usuarios_autorizados = [
    "facundo@amautainversiones.com",
    "florencia@amautainversiones.com",
    "jeronimo@amautainversiones.com",
    "agustin@amautainversiones.com",
    "regina@amautainversiones.com"
]

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

# ---------------------- APP ----------------------

def buscar_clientes_similares(cliente_input):
    df_clientes = obtener_hoja_clientes()
    nombres = df_clientes["CLIENTE"].tolist()
    cliente_input_normalizado = normalizar(cliente_input)
    partes_input = cliente_input_normalizado.split()
    coincidencias = []

    for i, nombre in enumerate(nombres, start=1):
        nombre_normalizado = normalizar(nombre)
        partes_nombre = nombre_normalizado.split()

        if len(partes_input) == 1:
            if any(p in parte for p in partes_input for parte in partes_nombre):
                coincidencias.append((i, nombre))
        else:
            match_parcial = all(p in partes_nombre for p in partes_input)
            match_exacto = cliente_input_normalizado in nombre_normalizado
            if match_parcial or match_exacto:
                coincidencias.append((i, nombre))

    return coincidencias

tabs = st.tabs(["📞 Cargar Contactos", "📅 Recordatorios Pendientes"])

# -------- TAB 1: Cargar Contactos --------
with tabs[0]:
    st.title("📋 Registro de Contactos Comerciales")
    frase = st.text_input("📝 Escribí el contacto realizado:", placeholder="Ej: Se habló con Lavaque el 10/7/2025 por revisión de cartera")

    try:
        cliente_preview, fecha_preview, motivo_preview = extraer_datos(frase)
        st.markdown(f"📌 Se detectó: **{cliente_preview}**, fecha: **{fecha_preview}**, motivo: _{motivo_preview}_")
    except Exception as e:
        st.error(f"⚠️ No se pudo interpretar correctamente: {e}")

    estado = st.selectbox("📌 Estado del contacto:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"])
    agendar = st.radio("📅 ¿Querés agendar un próximo contacto?", ["No", "Sí"])
    proximo_contacto = ""
    if agendar == "Sí":
        fecha_proxima = st.date_input("🗓️ ¿Cuándo sería el próximo contacto?", format="YYYY/MM/DD")
        proximo_contacto = fecha_proxima.strftime("%d/%m/%Y")

    nota = st.text_input("🗒️ ¿Querés agregar una nota?", placeholder="Ej: seguimiento de bonos")

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
                hoja_registro = procesar_contacto(cliente_real, fila, frase, estado, proximo_contacto, nota, extraer_datos, detectar_tipo)
                guardar_en_historial(cliente_real, hoja_registro, frase, estado, nota, proximo_contacto)
                st.success(f"✅ Contacto registrado correctamente en la hoja: **{hoja_registro}**.")
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
    st.selectbox(
        "❗Se encontraron varios clientes, elegí el correcto:",
        opciones,
        key="cliente_input_seleccionado"
    )

if st.button("Confirmar cliente"):
    seleccion = st.session_state.get("cliente_input_seleccionado", "")
    fila_cliente = None

    for fila, nombre in st.session_state.coincidencias:
        if normalizar(nombre) == normalizar(seleccion):
            fila_cliente = fila
            break

    if fila_cliente:
        hoja_registro = procesar_contacto(
            seleccion,
            fila_cliente,
            st.session_state.frase_guardada,
            st.session_state.estado_guardado,
            st.session_state.proximo_contacto_guardado,
            st.session_state.nota_guardada,
            extraer_datos,
            detectar_tipo
        )

        st.success(f"✅ Contacto registrado correctamente en la hoja: **{hoja_registro}**.")
        st.session_state.hoja_registro_final = hoja_registro
        st.session_state.cliente_input = seleccion
        st.session_state.coincidencias = []

        guardar_en_historial(
            seleccion,
            hoja_registro,
            st.session_state.frase_guardada,
            st.session_state.estado_guardado,
            st.session_state.nota_guardada,
            st.session_state.proximo_contacto_guardado
        )
    else:
        st.error("❌ Error interno: no se pudo encontrar la fila del cliente seleccionado.")

    if "historial" not in st.session_state:
        st.session_state.historial = []

    if st.session_state.historial:
        st.subheader("📂 Historial reciente de cargas")
        df_historial = pd.DataFrame.from_records(st.session_state.historial)
        st.dataframe(df_historial, use_container_width=True)

    st.subheader("🔍 Filtros sobre el historial")
    clientes_disponibles = sorted(set([h["Cliente"] for h in st.session_state.historial]))
    cliente_seleccionado = st.selectbox("Filtrar historial por cliente", options=["Todos"] + clientes_disponibles)

    historial_filtrado = st.session_state.historial if cliente_seleccionado == "Todos" else [r for r in st.session_state.historial if r["Cliente"] == cliente_seleccionado]
    df_filtrado = pd.DataFrame(historial_filtrado)
    st.dataframe(df_filtrado, use_container_width=True)

    if st.checkbox("📖 Ver historial completo (sin límite)"):
        st.markdown("⚠️ Esto puede tardar unos segundos si tenés muchas entradas.")
        df_completo = pd.DataFrame(st.session_state.historial)
        st.dataframe(df_completo, use_container_width=True)

# -------- TAB 2: Recordatorios Pendientes --------
with tabs[1]:
    st.title("📅 Recordatorios Pendientes")

    recordatorios = obtener_recordatorios_pendientes(st.session_state.mail_ingresado)

    if recordatorios:
        st.subheader("📣 Contactos a seguir")

        for i, (cliente, asesor, fecha, detalle, tipo) in enumerate(recordatorios):
            icono = "🔴" if tipo == "vencido" else "🟡"
            fila_container = st.container()

            with fila_container:
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"{icono} **{cliente}** (Asesor: {asesor}) – contacto para **{fecha}**. _Motivo_: {detalle or '-sin info-'}")
                with col2:
                    if st.button("✔️ Hecho", key=f"hecho_{i}"):
                        try:
                            marcar_contacto_como_hecho(cliente, asesor)
                            fila_container.empty()
                            st.success(f"✅ {cliente} marcado como hecho")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Error al marcar como hecho: {e}")
    else:
        st.success("🎉 No hay contactos pendientes. ¡Buen trabajo!")
