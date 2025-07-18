import streamlit as st
import pandas as pd
from datetime import datetime
from drive_utils import (
    obtener_hoja_clientes,
    procesar_contacto,
    marcar_contacto_como_hecho,
    obtener_recordatorios_pendientes,
    normalizar
)
from historial import guardar_en_historial, cargar_historial_completo, formatear_historial_exportable
from utils import extraer_datos, detectar_tipo

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
        correo = mail_ingresado.strip().lower()
        if correo in usuarios_autorizados:
            st.session_state.autenticado = True
            st.session_state.mail_ingresado = correo
            st.rerun()
        else:
            st.error("❌ No estás autorizado.")
    st.stop()

tabs = st.tabs(["📞 Cargar Contactos", "📅 Recordatorios Pendientes"])

with tabs[0]:
    st.title("📋 Registro de Contactos Comerciales")

    modo_carga = st.radio(
        "🔀 ¿Cómo querés cargar el contacto?",
        ["Carga guiada", "Redacción libre", "Carga rápida", "Carga múltiple"],
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
            return exactas

        parciales = []
        for i, row in df_clientes.iterrows():
            nombre = row["CLIENTE"]
            norm_nombre = normalizar(nombre)
            if normal_input in norm_nombre or norm_nombre in normal_input:
                distancia = abs(len(norm_nombre) - len(normal_input))
                parciales.append((i + 2, nombre, row["ASESOR/A"], distancia))

        if len(parciales) == 1:
            return [parciales[0][:3]]

        if len(parciales) > 1:
            # Ordenamos por menor distancia de longitud y luego alfabéticamente
            parciales_ordenadas = sorted(parciales, key=lambda x: (x[3], x[1]))
            nombres = [p[1] for p in parciales_ordenadas]
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

    elif modo_carga == "Redacción libre":
        frase = st.text_input(
            "📝 Escribí el contacto:",
            placeholder="Ej: Se contactó con Pepito el 17/07/2025 por revisión de cartera",
            key="rl_frase"
        )

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

    if modo_carga in ["Carga guiada", "Redacción libre"]:
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
