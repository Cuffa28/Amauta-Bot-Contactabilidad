import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit.components.v1 import html
import gspread

import drive_utils as drive_local
import drive_utils_internacional as drive_int

from historial import cargar_historial_completo, formatear_historial_exportable
from gestor_contactos import registrar_contacto

usuarios_autorizados = [
    "facundo@amautainversiones.com",
    "florencia@amautainversiones.com",
    "jeronimo@amautainversiones.com",
    "agustin@amautainversiones.com",
    "regina@amautainversiones.com",
    "julieta@amautainversiones.com"
]

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acceso restringido")
    mail_ingresado = st.text_input("📧 Ingresá tu mail institucional", placeholder="tuusuario@amautainversiones.com")
    if st.button("Ingresar"):
        correo = mail_ingresado.strip().lower()
        if correo in usuarios_autorizados:
            st.session_state.autenticado = True
            st.session_state.mail_ingresado = correo
            st.rerun()
        else:
            st.error("❌ No estás autorizado.")
    st.stop()

if st.session_state.mail_ingresado == "regina@amautainversiones.com":
    tipo_dato = st.radio("🌐 ¿Con qué clientes querés trabajar?", ["Locales", "Internacionales"], key="origen_datos")
    st.markdown("---")
    if "tipo_dato_confirmado" not in st.session_state:
        st.session_state.tipo_dato_confirmado = False
    if st.button("Continuar"):
        st.session_state.tipo_dato_confirmado = True
    if not st.session_state.tipo_dato_confirmado:
        st.stop()
else:
    tipo_dato = "Locales" if st.session_state.mail_ingresado != "julieta@amautainversiones.com" else "Internacionales"

if tipo_dato == "Locales":
    obtener_hoja_clientes = drive_local.obtener_hoja_clientes
    procesar_contacto = drive_local.procesar_contacto
    marcar_contacto_como_hecho = drive_local.marcar_contacto_como_hecho
    obtener_recordatorios_pendientes = drive_local.obtener_recordatorios_pendientes
else:
    obtener_hoja_clientes = drive_int.obtener_hoja_clientes
    procesar_contacto = drive_int.procesar_contacto
    marcar_contacto_como_hecho = drive_int.marcar_contacto_como_hecho
    obtener_recordatorios_pendientes = drive_int.obtener_recordatorios_pendientes

@st.cache_data(ttl=60)
def obtener_hoja_clientes_cached():
    return obtener_hoja_clientes()

try:
    df_clientes = obtener_hoja_clientes_cached()
except Exception as e:
    st.error("❌ No se pudo acceder a la hoja de clientes. Esperá unos segundos e intentá de nuevo.")
    st.stop()

nombres = sorted(df_clientes["CLIENTE"].dropna().unique())
cliente_seleccionado = st.text_input("👤 Cliente (podés escribir libremente):", "", key="cliente_libre")

usuario_codigo = st.session_state.mail_ingresado.split("@")[0][:2].upper()

tabs = st.tabs(["📞 Cargar Contactos", "📅 Recordatorios Pendientes"])

with tabs[0]:
    st.title("📋 Registro de Contactos Comerciales")

    modo_carga = st.radio(
        "🔀 ¿Cómo querés cargar el contacto?",
        ["Carga guiada", "Carga rápida", "Carga múltiple"],
        horizontal=True
    )

    if modo_carga == "Carga guiada":
        nombres = sorted(df_clientes["CLIENTE"].unique())
        cliente_seleccionado = st.selectbox("👤 Cliente:", nombres, key="cg_cliente")
        fecha_contacto = st.date_input("📅 Fecha del contacto:", format="YYYY/MM/DD", key="cg_fecha")
        tipo_contacto = st.selectbox("📞 Tipo de contacto:", ["LLAMADA", "MENSAJES", "REUNION", "OTRO"], key="cg_tipo")
        motivo_contacto = st.text_input("📝 Motivo:", placeholder="Ej: revisión de cartera", key="cg_motivo")

        frase = f"Se realizó una {tipo_contacto.lower()} con {cliente_seleccionado} el {fecha_contacto.strftime('%d/%m/%Y')} por {motivo_contacto.strip().lower()}"
        estado = st.selectbox("📌 Estado:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"], key="up_estado")
        agendar = st.radio("📅 Próximo contacto?", ["No", "Sí"], key="up_agenda")
        proximo = ""
        if agendar == "Sí":
            proximo = st.date_input("🗓️ Fecha:", key="up_prox").strftime("%d/%m/%Y")
        nota = st.text_input("🗒️ Nota:", key="up_nota")

        if st.button("Actualizar contacto", key="up_btn"):
            try:
                registrar_contacto(frase, estado, nota, proximo, df_clientes, procesar_contacto)
                st.success("✅ Registrado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ {e}")

    elif modo_carga == "Carga rápida":
        st.subheader("⚡ Carga rápida de hoy")
        cliente_flash = st.selectbox("👤 Cliente:", nombres, key="flash_cliente")
        tipo_flash = st.selectbox("📞 Tipo:", ["LLAMADA", "MENSAJES", "REUNION", "OTRO"], key="flash_tipo")
        motivo_flash = st.text_input("📝 Motivo (opcional)", "seguimiento general", key="flash_motivo")
        nota_flash = st.text_input("🗒️ Nota (opcional)", "", key="flash_nota")

        if st.button(f"✔️ Contacto con {cliente_flash}", key="flash_btn"):
            try:
                fh = datetime.today().strftime("%d/%m/%Y")
                frase = f"Se realizó una {tipo_flash.lower()} con {cliente_flash} el {fh} por {motivo_flash.strip().lower()}"
                registrar_contacto(frase, "Hecho", nota_flash, "", df_clientes, procesar_contacto)
                st.success(f"✅ {cliente_flash} registrado.")
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ {e}")

    elif modo_carga == "Carga múltiple":
        st.subheader("📥 Carga múltiple")
        texto_masivo = st.text_area("🧾 Una frase por línea:", key="mm_texto")
        estado_masivo = st.selectbox("📌 Estado:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"], key="mm_estado")
        nota_masiva = st.text_input("🗒️ Nota (opcional):", key="mm_nota")
        agendar = st.radio("📅 Agendar próximo contacto?", ["No", "Sí"], key="mm_agenda")
        prox = ""
        if agendar == "Sí":
            prox = st.date_input("🗓️ Próximo contacto:", format="YYYY/MM/DD", key="mm_prox").strftime("%d/%m/%Y")

        if st.button("📌 Cargar múltiples", key="mm_btn"):
            exitosos, fallidos = 0, []
            for idx, l in enumerate(texto_masivo.split("\n"), start=1):
                try:
                    registrar_contacto(l, estado_masivo, nota_masiva, prox, df_clientes, procesar_contacto)
                    exitosos += 1
                except Exception as e:
                    fallidos.append(f"Línea {idx}: {e}")
            st.success(f"✅ {exitosos} contactos cargados.")
            if fallidos:
                st.warning("⚠️ Fallaron:")
                for f in fallidos:
                    st.text(f"- {f}")
            st.rerun()

    st.subheader("📥 Descargar historial completo")
    dfc = cargar_historial_completo()
    dfout = formatear_historial_exportable(dfc)
    st.download_button(
        label="⬇️ Descargar historial",
        data=dfout.to_csv(index=False).encode("utf-8"),
        file_name="historial_contactos.csv",
        mime="text/csv",
        key="descarga_historial"
    )

with tabs[1]:
    st.title("📅 Recordatorios Pendientes")
    recs = obtener_recordatorios_pendientes(st.session_state.mail_ingresado)
    if recs:
        st.subheader("📣 Contactos a seguir")
        for i, (cliente, asesor, fecha, det, tp) in enumerate(recs):
            icon = "🔴" if tp == "vencido" else "🟡"
            cols = st.columns([6, 1], gap="small")
            cols[0].markdown(f"{icon} **{cliente}** – fecha: **{fecha}**. Motivo: {det or '-'} (Asesor: {asesor})")
            if cols[1].button("✔️ Hecho", key=f"recordatorio_hecho_{i}"):
                try:
                    marcar_contacto_como_hecho(cliente, asesor)
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"⚠️ {e}")
    else:
        st.success("🎉 No hay pendientes. Buen trabajo.")
