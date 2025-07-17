import streamlit as st
import pandas as pd
from datetime import datetime
from drive_utils import (
    obtener_hoja_clientes,
    procesar_contacto,
    marcar_contacto_como_hecho,
    obtener_recordatorios_pendientes,
    buscar_clientes_similares_por_asesor
)
from historial import guardar_en_historial, cargar_historial_completo
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

tabs = st.tabs(["📞 Cargar Contactos", "📅 Recordatorios Pendientes"])

# -------- TAB 1: Cargar Contactos --------
with tabs[0]:
    st.title("📋 Registro de Contactos Comerciales")

    modo_carga = st.radio(
        "🔀 ¿Cómo querés cargar el contacto?",
        ["Carga guiada", "Redacción libre", "Carga rápida", "Carga múltiple"],
        horizontal=True
    )

    # --- Modo guiado ---
    if modo_carga == "Carga guiada":
        df_clientes = obtener_hoja_clientes()
        nombres_clientes = sorted(df_clientes["CLIENTE"].unique())
        cliente_seleccionado = st.selectbox("👤 Seleccioná el cliente:", options=nombres_clientes)

        fecha_contacto = st.date_input("📅 Fecha del contacto:", format="YYYY/MM/DD")
        tipo_contacto = st.selectbox("📞 Tipo de contacto:", ["LLAMADA", "MENSAJES", "REUNION", "VISITA", "OTRO"])
        motivo_contacto = st.text_input("📝 Motivo del contacto:", placeholder="Ej: revisión de cartera")

        frase = f"Se contactó con {cliente_seleccionado} el {fecha_contacto.strftime('%d/%m/%Y')} por {motivo_contacto.lower()}"

    elif modo_carga == "Redacción libre":
        frase = st.text_input("📝 Escribí el contacto realizado:", placeholder="Ej: Hablé con Lavaque el 10/7/2025 por revisión de cartera")

    elif modo_carga == "Carga rápida":
        st.markdown("---")
        st.subheader("⚡ Carga rápida de contacto hecho hoy")

        df_clientes = obtener_hoja_clientes()
        lista_clientes = sorted(df_clientes["CLIENTE"].unique())
        cliente_flash = st.selectbox("👤 Cliente:", lista_clientes, key="cliente_flash")

        motivo_flash = st.text_input("📝 Motivo (opcional)", value="seguimiento general", key="motivo_flash")
        nota_flash = st.text_input("🗒️ Nota (opcional)", key="nota_flash")

        if st.button(f"✔️ Contacto hecho hoy con {cliente_flash}"):
            try:
                fecha_hoy = datetime.today().strftime("%d/%m/%Y")
                frase_flash = f"Se contactó con {cliente_flash} el {fecha_hoy} por {motivo_flash}"

                asesor = df_clientes[df_clientes["CLIENTE"] == cliente_flash]["ASESOR/A"].values[0]
                coincidencias = buscar_clientes_similares_por_asesor(cliente_flash, asesor)
                fila_cliente = coincidencias[0][0] if len(coincidencias) == 1 else None

                if fila_cliente is not None:
                    hoja = procesar_contacto(cliente_flash, fila_cliente, frase_flash, "Hecho", "", nota_flash, extraer_datos, detectar_tipo)
                    guardar_en_historial(cliente_flash, hoja, frase_flash, "Hecho", nota_flash, "")
                    st.success(f"✅ Contacto registrado con {cliente_flash} en la hoja: **{hoja}**.")
                else:
                    st.error("❌ No se encontró al cliente exacto para contacto rápido.")
            except Exception as e:
                st.error(f"⚠️ Error en carga rápida: {e}")
        st.stop()

    elif modo_carga == "Carga múltiple":
        st.markdown("---")
        st.subheader("📥 Carga múltiple de contactos")

        texto_masivo = st.text_area("🧾 Pegá aquí varias frases (una por línea):")
        estado_masivo = st.selectbox("📌 Estado general:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"])
        nota_masiva = st.text_input("🗒️ Nota general (opcional):")
        agendar_masivo = st.radio("📅 ¿Agendar próximo contacto?", ["No", "Sí"], key="agenda_masivo")
        proximo_contacto_masivo = ""
        if agendar_masivo == "Sí":
            fecha_prox = st.date_input("🗓️ Próximo contacto:", format="YYYY/MM/DD", key="proximo_contacto_masivo_fecha")
            proximo_contacto_masivo = fecha_prox.strftime("%d/%m/%Y")

        if st.button("📌 Cargar múltiples contactos"):
            exitosos, fallidos = 0, []
            for i, linea in enumerate(texto_masivo.strip().split("\n"), start=1):
                try:
                    cliente_in, _, _ = extraer_datos(linea)
                    asesor = df_clientes[df_clientes["CLIENTE"] == cliente_input]["ASESOR/A"].values[0]
                    coincidencias = buscar_clientes_similares_por_asesor(cliente_input, asesor)
                    if len(coincidencias) == 1:
                        fila, nombre = coincidencias[0]
                        hoja = procesar_contacto(nombre, fila, linea, estado_masivo, proximo_contacto_masivo, nota_masiva, extraer_datos, detectar_tipo)
                        guardar_en_historial(nombre, hoja, linea, estado_masivo, nota_masiva, proximo_contacto_masivo)
                        exitosos += 1
                    else:
                        fallidos.append(f"Línea {i}: {linea}")
                except Exception as e:
                    fallidos.append(f"Línea {i}: {e}")
            st.success(f"✅ {exitosos} contactos cargados.")
            if fallidos:
                st.warning("⚠️ Las siguientes líneas fallaron:")
                for f in fallidos:
                    st.text(f"- {f}")
        st.stop()

    try:
        cliente_preview, fecha_preview, motivo_preview = extraer_datos(frase)
        st.markdown(f"📌 Se detectó: **{cliente_preview}**, fecha: **{fecha_preview}**, motivo: _{motivo_preview}_")
    except Exception as e:
        st.error(f"⚠️ No se pudo interpretar correctamente: {e}")

    estado = st.selectbox("📌 Estado del contacto:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"])
    agendar = st.radio("📅 ¿Querés agendar un próximo contacto?", ["No", "Sí"])
    proximo_contacto = ""
    if agendar == "Sí":
        fecha_proxima = st.date_input("🗓️ Próximo contacto:", format="YYYY/MM/DD", key="proximo_contacto_fecha")
        proximo_contacto = fecha_proxima.strftime("%d/%m/%Y")

    nota = st.text_input("🗒️ ¿Querés agregar una nota?", placeholder="Ej: seguimiento de bonos")

    if st.button("Actualizar contacto"):
        try:
            cliente_input, _, _ = extraer_datos(frase)
            asesor = df_clientes[df_clientes["CLIENTE"] == cliente_input]["ASESOR/A"].values[0]
            coincidencias = buscar_clientes_similares_por_asesor(cliente_input, asesor)
            if len(coincidencias) == 1:
                fila, cliente_real = coincidencias[0]
                hoja = procesar_contacto(cliente_real, fila, frase, estado, proximo_contacto, nota, extraer_datos, detectar_tipo)
                guardar_en_historial(cliente_real, hoja, frase, estado, nota, proximo_contacto)
                st.success("✅ Contacto registrado correctamente.")
            else:
                st.error("❌ Cliente no encontrado o hay varias coincidencias.")
        except Exception as e:
            st.error(f"⚠️ Error procesando el contacto: {e}")

    st.subheader("📂 Historial reciente de cargas")
    if "historial" not in st.session_state:
        st.session_state.historial = []

    if st.session_state.historial:
        df_historial = pd.DataFrame.from_records(st.session_state.historial)
        st.dataframe(df_historial, use_container_width=True)

    st.subheader("📥 Descargar historial completo")
    df_completo = cargar_historial_completo()
    st.download_button(
        label="⬇️ Descargar historial",
        data=df_completo.to_csv(index=False).encode("utf-8"),
        file_name="historial_contactos.csv",
        mime="text/csv"
    )

# -------- TAB 2: Recordatorios Pendientes --------
with tabs[1]:
    st.title("📅 Recordatorios Pendientes")
    recordatorios = obtener_recordatorios_pendientes(st.session_state.mail_ingresado)
    if recordatorios:
        st.subheader("📣 Contactos a seguir")
        for i, (cliente, asesor, fecha, detalle, tipo) in enumerate(recordatorios):
            icono = "🔴" if tipo == "vencido" else "🟡"
            fila = st.container()
            with fila:
                col1, col2 = st.columns([5,1])
                with col1:
                    st.markdown(f"{icono} **{cliente}** – contacto para **{fecha}**. Motivo: {detalle or '-'} (Asesor: {asesor})")
                with col2:
                    if st.button("✔️ Hecho", key=f"hecho_{i}"):
                        try:
                            marcar_contacto_como_hecho(cliente, asesor)
                            fila.empty()
                            st.success(f"✅ {cliente} marcado como hecho")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Error al marcar como hecho: {e}")
    else:
        st.success("🎉 No hay contactos pendientes. ¡Buen trabajo!")
