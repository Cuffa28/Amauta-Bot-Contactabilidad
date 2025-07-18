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
    mail_ingresado = st.text_input("📧 Ingresá tu mail institucional", placeholder="tuusuario@amautainversiones.com", key="login_mail")
    if st.button("Ingresar", key="login_btn"):
        if mail_ingresado.strip().lower() in usuarios_autorizados:
            st.session_state.autenticado = True
            st.session_state.mail_ingresado = mail_ingresado.strip().lower()
            st.rerun()
        else:
            st.error("❌ No estás autorizado para ingresar a esta aplicación.")
    st.stop()

tabs = st.tabs(["📞 Cargar Contactos", "📅 Recordatorios Pendientes"])

# ======================== TAB 0 ========================
with tabs[0]:
    st.title("📋 Registro de Contactos Comerciales")

    modo_carga = st.radio(
        "🔀 ¿Cómo querés cargar el contacto?",
        ["Carga guiada", "Redacción libre", "Carga rápida", "Carga múltiple"],
        horizontal=True,
        key="modo_carga"
    )

    df_clientes = obtener_hoja_clientes()

    if modo_carga == "Carga guiada":
        nombres_clientes = sorted(df_clientes["CLIENTE"].unique())
        cliente_seleccionado = st.selectbox("👤 Seleccioná el cliente:", options=nombres_clientes, key="cg_cliente")

        fecha_contacto = st.date_input("📅 Fecha del contacto:", format="YYYY/MM/DD", key="cg_fecha")
        tipo_contacto = st.selectbox("📞 Tipo de contacto:", ["LLAMADA", "MENSAJES", "REUNION", "OTRO"], key="cg_tipo")
        motivo_contacto = st.text_input("📝 Motivo del contacto:", placeholder="Ej: revisión de cartera", key="cg_motivo")

        frase = f"Se realizó una {tipo_contacto.lower()} con {cliente_seleccionado} el {fecha_contacto.strftime('%d/%m/%Y')} por {motivo_contacto.lower()}"

    elif modo_carga == "Redacción libre":
        frase = st.text_input("📝 Escribí el contacto realizado:", placeholder="Ej: Hablé con Lavaque el 10/7/2025 por revisión de cartera", key="rl_frase")

    elif modo_carga == "Carga rápida":
        st.markdown("---")
        st.subheader("⚡ Carga rápida de contacto hecho hoy")

        lista_clientes = sorted(df_clientes["CLIENTE"].unique())
        cliente_flash = st.selectbox("👤 Cliente:", lista_clientes, key="cr_cliente")

        tipo_contacto = st.selectbox("📞 Tipo:", ["LLAMADA", "MENSAJES", "REUNION", "OTRO"], key="cr_tipo")
        motivo_flash = st.text_input("📝 Motivo (opcional)", value="seguimiento general", key="cr_motivo")
        nota_flash = st.text_input("🗒️ Nota (opcional)", key="cr_nota")

        if st.button(f"✔️ Contacto hecho hoy con {cliente_flash}", key="cr_btn"):
            try:
                fecha_hoy = datetime.today().strftime("%d/%m/%Y")
                frase_flash = f"Se realizó una {tipo_contacto.lower()} con {cliente_flash} el {fecha_hoy} por {motivo_flash}"

                coincidencias = [
                    (i + 2, row["CLIENTE"], row["ASESOR/A"])
                    for i, row in df_clientes.iterrows()
                    if normalizar(row["CLIENTE"]) == normalizar(cliente_flash)
                ]

                if len(coincidencias) == 1:
                    fila_cliente, cliente_nombre_real, asesor = coincidencias[0]
                    hoja = procesar_contacto(cliente_nombre_real, fila_cliente, frase_flash, "Hecho", "", nota_flash, extraer_datos, detectar_tipo)
                    guardar_en_historial(cliente_nombre_real, hoja, frase_flash, "Hecho", nota_flash, "")
                    st.success(f"✅ Contacto registrado con {cliente_nombre_real} en la hoja: **{hoja}**.")
                    st.rerun()
                else:
                    st.error("❌ No se pudo determinar el asesor del cliente.")
            except Exception as e:
                st.error(f"⚠️ Error en carga rápida: {e}")

    elif modo_carga == "Carga múltiple":
        st.markdown("---")
        st.subheader("📥 Carga múltiple de contactos")

        texto_masivo = st.text_area("🧾 Pegá aquí varias frases (una por línea):", key="cm_texto")
        estado_masivo = st.selectbox("📌 Estado general:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"], key="cm_estado")
        nota_masiva = st.text_input("🗒️ Nota general (opcional):", key="cm_nota")
        agendar_masivo = st.radio("📅 ¿Agendar próximo contacto?", ["No", "Sí"], key="cm_agendar")
        proximo_contacto_masivo = ""
        if agendar_masivo == "Sí":
            fecha_prox = st.date_input("🗓️ Próximo contacto:", format="YYYY/MM/DD", key="cm_fecha_prox")
            proximo_contacto_masivo = fecha_prox.strftime("%d/%m/%Y")

        if st.button("📌 Cargar múltiples contactos", key="cm_btn"):
            exitosos, fallidos = 0, []
            for i, linea in enumerate(texto_masivo.strip().split("\n"), start=1):
                try:
                    cliente_in, _, _ = extraer_datos(linea)
                    coincidencias = [
                        (j + 2, row["CLIENTE"], row["ASESOR/A"])
                        for j, row in df_clientes.iterrows()
                        if normalizar(row["CLIENTE"]) == normalizar(cliente_in)
                    ]

                    if len(coincidencias) == 1:
                        fila, cliente_nombre_real, asesor = coincidencias[0]
                        hoja = procesar_contacto(cliente_nombre_real, fila, linea, estado_masivo, proximo_contacto_masivo, nota_masiva, extraer_datos, detectar_tipo)
                        guardar_en_historial(cliente_nombre_real, hoja, linea, estado_masivo, nota_masiva, proximo_contacto_masivo)
                        exitosos += 1
                    else:
                        fallidos.append(f"Línea {i}: no se encontró asesor")
                except Exception as e:
                    fallidos.append(f"Línea {i}: {e}")
            st.success(f"✅ {exitosos} contactos cargados.")
            if fallidos:
                st.warning("⚠️ Las siguientes líneas fallaron:")
                for f in fallidos:
                    st.text(f"- {f}")
            st.rerun()

    if 'frase' in locals():
        try:
            cliente_preview, fecha_preview, motivo_preview = extraer_datos(frase)
            st.markdown(f"📌 Se detectó: **{cliente_preview}**, fecha: **{fecha_preview}**, motivo: _{motivo_preview}_")
        except Exception as e:
            st.error(f"⚠️ No se pudo interpretar correctamente: {e}")

        estado = st.selectbox("📌 Estado del contacto:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"], key="cg_estado")
        agendar = st.radio("📅 ¿Querés agendar un próximo contacto?", ["No", "Sí"], key="cg_agendar")
        proximo_contacto = ""
        if agendar == "Sí":
            fecha_proxima = st.date_input("🗓️ Próximo contacto:", format="YYYY/MM/DD", key="cg_fecha_prox")
            proximo_contacto = fecha_proxima.strftime("%d/%m/%Y")

        nota = st.text_input("🗒️ ¿Querés agregar una nota?", placeholder="Ej: seguimiento...", key="cg_nota")
        if st.button("Actualizar contacto", key="cg_btn_actualizar"):
            try:
                cliente_input, _, _ = extraer_datos(frase)
                coincidencias = [
                    (i + 2, row["CLIENTE"], row["ASESOR/A"])
                    for i, row in df_clientes.iterrows()
                    if normalizar(row["CLIENTE"]) == normalizar(cliente_input)
                ]
                if len(coincidencias) == 1:
                    fila, cliente_real, asesor = coincidencias[0]
                    hoja = procesar_contacto(cliente_real, fila, frase, estado, proximo_contacto, nota, extraer_datos, detectar_tipo)
                    guardar_en_historial(cliente_real, hoja, frase, estado, nota, proximo_contacto)
                    st.success("✅ Contacto registrado correctamente.")
                else:
                    st.error("❌ Cliente no encontrado o hay varias coincidencias.")
            except Exception as e:
                st.error(f"⚠️ Error procesando el contacto: {e}")

    st.subheader("📥 Descargar historial completo")
    df_completo = cargar_historial_completo()
    df_formateado = formatear_historial_exportable(df_completo)
    st.download_button(
        label="⬇️ Descargar historial",
        data=df_formateado.to_csv(index=False).encode("utf-8"),
        file_name="historial_contactos.csv",
        mime="text/csv",
        key="descarga_historial"
    )

# ======================== TAB 1 ========================
with tabs[1]:
    st.title("📅 Recordatorios Pendientes")
    recordatorios = obtener_recordatorios_pendientes(st.session_state.mail_ingresado)
    if recordatorios:
        st.subheader("📣 Contactos a seguir")
        for i, (cliente, asesor, fecha, detalle, tipo) in enumerate(recordatorios):
            icono = "🔴" if tipo == "vencido" else "🟡"
            fila = st.container()
            with fila:
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"{icono} **{cliente}** – contacto para **{fecha}**. Motivo: {detalle or '-'} (Asesor: {asesor})")
                with col2:
                    if st.button("✔️ Hecho", key=f"recordatorio_hecho_{i}"):
                        try:
                            marcar_contacto_como_hecho(cliente, asesor)
                            fila.empty()
                            st.success(f"✅ {cliente} marcado como hecho")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Error al marcar como hecho: {e}")
    else:
        st.success("🎉 No hay contactos pendientes. ¡Buen trabajo!")
