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

# 🚀 Autorización
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
            st.error("❌ No estás autorizado")
    st.stop()

# 📝 Carga recordatorios (una sola vez)
recordatorios = obtener_recordatorios_pendientes(st.session_state.mail_ingresado)

def mostrar_recordatorios(tab_key):
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
                    btn_key = f"{tab_key}_hecho_{i}"
                    if st.button("✔️ Hecho", key=btn_key):
                        try:
                            marcar_contacto_como_hecho(cliente, asesor)
                            fila.empty()
                            st.success(f"✅ {cliente} marcado como hecho")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Error: {e}")
    else:
        st.success("🎉 No hay contactos pendientes.")

# 🌐 Tabs
tabs = st.tabs(["📞 Cargar Contactos", "📅 Recordatorios Pendientes"])

with tabs[0]:
    st.title("📋 Registro de Contactos Comerciales")
    mostrar_recordatorios("t0")

    modo = st.radio("🔀 ¿Cómo querés cargar?", ["Carga guiada","Redacción libre","Carga rápida","Carga múltiple"], horizontal=True)
    tipo = "CONTACTO"

    if modo == "Carga guiada":
        df = obtener_hoja_clientes()
        cliente = st.selectbox("👤 Cliente", sorted(df["CLIENTE"].unique()))
        fecha = st.date_input("📅 Fecha:", format="YYYY/MM/DD")
        tipo = st.selectbox("📞 Tipo:", ["LLAMADA","MENSAJES","REUNION","OTRO"])
        motivo = st.text_input("📝 Motivo:", placeholder="Ej: revisión de cartera")
        frase = f"Se realizó una {tipo.lower()} con {cliente} el {fecha.strftime('%d/%m/%Y')} por {motivo.lower()}"

    elif modo == "Redacción libre":
        frase = st.text_input("📝 Contacto realizado:", placeholder="Ej: Hablé con Lavaque el 10/7/2025 por revisión de cartera")

    elif modo == "Carga rápida":
        st.markdown("---")
        st.subheader("⚡ Carga rápida hoy")
        df = obtener_hoja_clientes()
        cliente = st.selectbox("👤 Cliente:", sorted(df["CLIENTE"].unique()), key="flash_c")
        tipo = st.selectbox("📞 Tipo:", ["LLAMADA","MENSAJES","REUNION","OTRO"], key="flash_t")
        motivo = st.text_input("📝 Motivo (opcional)", "seguimiento general", key="flash_m")
        nota = st.text_input("🗒️ Nota (opcional)", key="flash_n")

        if st.button(f"✔️ Contacto hecho hoy con {cliente}", key="flash_btn"):
            try:
                hoy = datetime.today().strftime("%d/%m/%Y")
                frase = f"Se realizó una {tipo.lower()} con {cliente} el {hoy} por {motivo}"
                df = obtener_hoja_clientes()
                cands = [(i+2,row["CLIENTE"],row["ASESOR/A"]) for i,row in df.iterrows() if normalizar(row["CLIENTE"])==normalizar(cliente)]
                if len(cands)==1:
                    fcli, creal, ases = cands[0]
                    hoja = procesar_contacto(creal,fcli,frase,"Hecho","",nota,extraer_datos,detectar_tipo,tipo)
                    guardar_en_historial(creal,hoja,frase,"Hecho",nota,"",tipo)
                    st.success(f"✅ Contacto con {creal} registrado en hoja **{hoja}**.")
                    st.rerun()
                else:
                    st.error("❌ No se determinó asesor")
            except Exception as e:
                st.error(f"⚠️ Error: {e}")

    elif modo == "Carga múltiple":
        st.markdown("---")
        st.subheader("📥 Carga múltiple")
        texto = st.text_area("🧾 Varias frases (una por línea):")
        estado = st.selectbox("📌 Estado:", ["En curso","Hecho","REUNION","Respuesta positiva"])
        nota = st.text_input("🗒️ Nota (opcional):", key="mm_nota")
        agendar = st.radio("📅 Agendar próximo contacto?", ["No","Sí"], key="mm_agenda")
        prox = ""
        if agendar=="Sí":
            fp = st.date_input("🗓️ Próximo contacto:", format="YYYY/MM/DD", key="mm_fecha")
            prox = fp.strftime("%d/%m/%Y")

        if st.button("📌 Cargar múltiples", key="mm_btn"):
            df = obtener_hoja_clientes()
            ok, err = 0, []
            for idx,line in enumerate(texto.strip().split("\n"),start=1):
                try:
                    cin,_,_ = extraer_datos(line)
                    cands = [(j+2,row["CLIENTE"],row["ASESOR/A"]) for j,row in df.iterrows() if normalizar(row["CLIENTE"])==normalizar(cin)]
                    if len(cands)==1:
                        fcli,creal,ases= cands[0]
                        hoja = procesar_contacto(creal,fcli,line,estado,prox,nota,extraer_datos,detectar_tipo)
                        guardar_en_historial(creal,hoja,line,estado,nota,prox)
                        ok+=1
                    else:
                        err.append(f"L{idx}: no se encontró asesor")
                except Exception as e:
                    err.append(f"L{idx}: {e}")
            st.success(f"✅ {ok} contactos cargados.")
            if err:
                st.warning("⚠️ Errores:")
                for e in err: st.text(f"- {e}")
            st.rerun()

    if 'frase' in locals() and frase:
        try:
            cli, fcha, mot = extraer_datos(frase)
            st.markdown(f"📌 Detectado: **{cli}**, fecha: **{fcha}**, motivo: _{mot}_")
        except Exception as e:
            st.error(f"⚠️ No se interpretó: {e}")

    # 💼 Actualización manual
    estado = st.selectbox("📌 Estado:", ["En curso","Hecho","REUNION","Respuesta positiva"])
    agendar = st.radio("📅 Próximo contacto?", ["No","Sí"], key="u_ag")
    prox = ""
    if agendar=="Sí":
        fp = st.date_input("🗓️ Próxima:", format="YYYY/MM/DD", key="u_fecha")
        prox = fp.strftime("%d/%m/%Y")
    nota = st.text_input("🗒️ Nota (opcional):", key="u_nota")

    if st.button("Actualizar contacto", key="u_btn"):
        df = obtener_hoja_clientes()
        try:
            cli,_,_ = extraer_datos(frase)
            cands = [(i+2,row["CLIENTE"],row["ASESOR/A"]) for i,row in df.iterrows() if normalizar(row["CLIENTE"])==normalizar(cli)]
            if len(cands)==1:
                fcli,creal,ases = cands[0]
                hoja = procesar_contacto(creal,fcli,frase,estado,prox,nota,extraer_datos,detectar_tipo,tipo)
                guardar_en_historial(creal,hoja,frase,estado,nota,prox,tipo)
                st.success("✅ Contacto actualizado.")
            else:
                st.error("❌ Cliente no encontrado o múltiples coincidencias.")
        except Exception as e:
            st.error(f"⚠️ Error: {e}")

    st.subheader("📂 Historial reciente")
    if "historial" not in st.session_state:
        st.session_state.historial = []
    if st.session_state.historial:
        st.dataframe(pd.DataFrame.from_records(st.session_state.historial), use_container_width=True)

    st.subheader("📥 Descargar historial completo")
    dfc = cargar_historial_completo()
    df_rep = formatear_historial_exportable(dfc)
    st.download_button(
        "⬇️ Descargar historial",
        data=df_rep.to_csv(index=False).encode("utf-8"),
        file_name="historial_contactos.csv",
        mime="text/csv"
    )

with tabs[1]:
    st.title("📅 Recordatorios Pendientes")
    mostrar_recordatorios("t1")
