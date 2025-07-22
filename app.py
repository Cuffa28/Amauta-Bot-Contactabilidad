import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit.components.v1 import html

# 🔁 Importar ambos módulos: local e internacional
import drive_utils as drive_local
import drive_utils_internacional as drive_int

from historial import guardar_en_historial, cargar_historial_completo, formatear_historial_exportable
from utils import extraer_datos, detectar_tipo

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
    st.title("\U0001F512 Acceso restringido")
    mail_ingresado = st.text_input("\U0001F4E7 Ingresá tu mail institucional", placeholder="tuusuario@amautainversiones.com")
    if st.button("Ingresar"):
        correo = mail_ingresado.strip().lower()
        if correo in usuarios_autorizados:
            st.session_state.autenticado = True
            st.session_state.mail_ingresado = correo
            st.rerun()
        else:
            st.error("❌ No estás autorizado.")
    st.stop()

# 🌍 Selección entre clientes locales o internacionales para REGINA
if st.session_state.mail_ingresado == "regina@amautainversiones.com":
    tipo_dato = st.radio("🌐 ¿Con qué clientes querés trabajar?", ["Locales", "Internacionales"], key="origen_datos")
else:
    tipo_dato = "Locales" if st.session_state.mail_ingresado != "julieta@amautainversiones.com" else "Internacionales"

# Selección de funciones según el tipo de dato
if tipo_dato == "Locales":
    obtener_hoja_clientes = drive_local.obtener_hoja_clientes
    procesar_contacto = drive_local.procesar_contacto
    marcar_contacto_como_hecho = drive_local.marcar_contacto_como_hecho
    obtener_recordatorios_pendientes = drive_local.obtener_recordatorios_pendientes
    normalizar = drive_local.normalizar
else:
    obtener_hoja_clientes = drive_int.obtener_hoja_clientes
    procesar_contacto = drive_int.procesar_contacto
    marcar_contacto_como_hecho = drive_int.marcar_contacto_como_hecho
    obtener_recordatorios_pendientes = drive_int.obtener_recordatorios_pendientes
    normalizar = drive_int.normalizar

# 🎮 POP-UP EMERGENTE DE VENCIMIENTOS HOY
if "popup_oculto" not in st.session_state:
    st.session_state.popup_oculto = False

recordatorios = obtener_recordatorios_pendientes(st.session_state.mail_ingresado)
vencen_hoy = [r for r in recordatorios if r[4] == "pendiente"]

if vencen_hoy and not st.session_state.popup_oculto:
    clientes_html = "".join([
        f"<li><b>{c}</b> – {f} – {n if n else '-'} </li>"
        for c, _, f, n, _ in vencen_hoy
    ])

    st.markdown(
        f"""
        <div style='position: relative; margin-bottom: 10px; background-color: #fff3cd; color: #856404;
        border: 1px solid #ffeeba; border-radius: 8px; padding: 15px 20px;
        box-shadow: 0 0 15px rgba(0,0,0,0.2); max-width: 500px;'>
            <b>📣 ¡Tenés contactos que vencen hoy!</b>
            <ul style='margin-top: 10px; padding-left: 20px; font-size: 0.9rem;'>
                {clientes_html}
            </ul>
        </div>
        """,
        unsafe_allow_html=True
    )
    if st.button("❌ Cerrar recordatorios", key="cerrar_popup"):
        st.session_state.popup_oculto = True
        st.rerun()

tabs = st.tabs(["📞 Cargar Contactos", "📅 Recordatorios Pendientes"])

with tabs[0]:
    st.title("📋 Registro de Contactos Comerciales")

    modo_carga = st.radio(
        "🔀 ¿Cómo querés cargar el contacto?",
        ["Carga guiada", "Carga rápida", "Carga múltiple"],
        horizontal=True
    )

    df_clientes = obtener_hoja_clientes()

    def buscar_coincidencia(cliente_input):
        normal_input = normalizar(cliente_input)
        exactas = [
            (i + 2, row["CLIENTE"], row["ASESOR/A"])
            for i, row in df_clientes.iterrows()
            if normalizar(row["CLIENTE"]) == normal_input
        ]
        if exactas:
            return exactas  # devuelve aunque haya varias exactas

        parciales = [
            (i + 2, row["CLIENTE"], row["ASESOR/A"])
            for i, row in df_clientes.iterrows()
            if normal_input in normalizar(row["CLIENTE"]) or normalizar(row["CLIENTE"]) in normal_input
        ]
        if len(parciales) == 1:
            return parciales

        # 🚨 Nueva mejora: si hay múltiples coincidencias, mostrar sugerencias
        if len(parciales) > 1:
            nombres = [c[1] for c in parciales]
            raise ValueError(f"Coincidencias múltiples para '{cliente_input}': {', '.join(nombres)}")

        raise ValueError(f"No se encontró ninguna coincidencia para '{cliente_input}'.")

    # --- Modo: Carga guiada ---
    if modo_carga == "Carga guiada":
        nombres = sorted(df_clientes["CLIENTE"].unique())
        cliente_seleccionado = st.selectbox("👤 Cliente:", nombres, key="cg_cliente")
        fecha_contacto = st.date_input("📅 Fecha del contacto:", format="YYYY/MM/DD", key="cg_fecha")
        tipo_contacto = st.selectbox("📞 Tipo de contacto:", ["LLAMADA", "MENSAJES", "REUNION", "OTRO"], key="cg_tipo")
        motivo_contacto = st.text_input("📝 Motivo:", placeholder="Ej: revisión de cartera", key="cg_motivo")

        frase = f"Se realizó una {tipo_contacto.lower()} con {cliente_seleccionado} el {fecha_contacto.strftime('%d/%m/%Y')} por {motivo_contacto.strip().lower()}"

        try:
            st.markdown(f"📌 Detectado: **{cliente_seleccionado}**, **{fecha_contacto.strftime('%d/%m/%Y')}**, _{motivo_contacto}_")
        except Exception as e:
            st.warning(f"⚠️ Error mostrando frase: {e}")

    # --- Modo: Carga rápida ---
    elif modo_carga == "Carga rápida":
        st.markdown("---")
        st.subheader("⚡ Carga rápida de hoy")
        nombres = sorted(df_clientes["CLIENTE"].unique())
        cliente_flash = st.selectbox("👤 Cliente:", nombres, key="flash_cliente")
        tipo_flash = st.selectbox("📞 Tipo:", ["LLAMADA", "MENSAJES", "REUNION", "OTRO"], key="flash_tipo")
        motivo_flash = st.text_input("📝 Motivo (opcional)", "seguimiento general", key="flash_motivo")
        nota_flash = st.text_input("🗒️ Nota (opcional)", "", key="flash_nota")

        if st.button(f"✔️ Contacto con {cliente_flash}", key="flash_btn"):
            try:
                fh = datetime.today().strftime("%d/%m/%Y")
                frase = f"Se realizó una {tipo_flash.lower()} con {cliente_flash} el {fh} por {motivo_flash.strip().lower()}"
                coincidencias = buscar_coincidencia(cliente_flash)
                if len(coincidencias) == 1:
                    _, cliente_real, asesor = coincidencias[0]
                    hoja = procesar_contacto(cliente_real, _, frase, "Hecho", "", nota_flash, extraer_datos, detectar_tipo)
                    guardar_en_historial(cliente_real, hoja, frase, "Hecho", nota_flash, "")
                    st.success(f"✅ {cliente_real} registrado.")
                    st.rerun()
                else:
                    st.error("❌ Cliente no claro.")
            except Exception as e:
                st.error(f"⚠️ {e}")

    elif modo_carga == "Carga múltiple":
        st.markdown("---")
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
                    c, _, _ = extraer_datos(l)
                    matches = buscar_coincidencia(c)
                    if len(matches) == 1:
                        _, creal, asesor = matches[0]
                        hoja = procesar_contacto(creal, _, l, estado_masivo, prox, nota_masiva, extraer_datos, detectar_tipo)
                        guardar_en_historial(creal, hoja, l, estado_masivo, nota_masiva, prox)
                        exitosos += 1
                    else:
                        fallidos.append(f"Línea {idx}: cliente no encontrado o ambigüo")
                except Exception as e:
                    fallidos.append(f"Línea {idx}: {e}")
            st.success(f"✅ {exitosos} contactos cargados.")
            if fallidos:
                st.warning("⚠️ Fallaron:")
                for f in fallidos:
                    st.text(f"- {f}")
            st.rerun()

    if modo_carga == "Carga guiada":
        estado = st.selectbox("📌 Estado:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"], key="up_estado")
        agendar = st.radio("📅 Próximo contacto?", ["No", "Sí"], key="up_agenda")
        proximo = ""
        if agendar == "Sí":
            proximo = st.date_input("🗓️ Fecha:", key="up_prox").strftime("%d/%m/%Y")
        nota = st.text_input("🗒️ Nota:", key="up_nota")

        if st.button("Actualizar contacto", key="up_btn"):
            try:
                # Obtener cliente desde frase, siempre
                cliente_input, _, _ = extraer_datos(frase)
                matches = buscar_coincidencia(cliente_input)

                if len(matches) == 1:
                    _, creal, asesor = matches[0]
                    hoja = procesar_contacto(creal, _, frase, estado, proximo, nota, extraer_datos, detectar_tipo)
                    guardar_en_historial(creal, hoja, frase, estado, nota, proximo)
                    st.success("✅ Registrado correctamente.")
                else:
                    st.error("❌ Cliente no encontrado o ambigüo.")
            except Exception as e:
                st.error(f"⚠️ {e}")

    st.subheader("📂 Historial reciente")
    if "historial" in st.session_state and st.session_state.historial:
        dfh = pd.DataFrame(st.session_state.historial)
        st.dataframe(dfh, use_container_width=True)

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
