import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit.components.v1 import html
import gspread
import difflib

import drive_utils as drive_local
import drive_utils_internacional as drive_int

from historial import cargar_historial_completo, formatear_historial_exportable
from gestor_contactos import registrar_contacto
from utils import normalizar

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

# -----------------------------------------------
# Elección de planilla (Locales / Internacionales)
# -----------------------------------------------
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
    agregar_cliente_si_no_existe = drive_local.agregar_cliente_si_no_existe
else:
    obtener_hoja_clientes = drive_int.obtener_hoja_clientes
    procesar_contacto = drive_int.procesar_contacto
    marcar_contacto_como_hecho = drive_int.marcar_contacto_como_hecho
    obtener_recordatorios_pendientes = drive_int.obtener_recordatorios_pendientes
    agregar_cliente_si_no_existe = drive_int.agregar_cliente_si_no_existe

# ------------------- helpers --------------------
@st.cache_data(ttl=60)
def obtener_hoja_clientes_cached():
    return obtener_hoja_clientes()

def rankear_coincidencias(query: str, universe: list[str], top_n: int = 50) -> list[str]:
    """Devuelve las mejores coincidencias priorizando exacta, prefijo y token match.
    Evita el "me vuelvo loco" del selectbox estándar 😉
    """
    if not query:
        return universe
    q = normalizar(query)

    def score(nombre: str) -> tuple:
        n = normalizar(nombre)
        # pesos: exacta (1), prefijo (0.95), contiene (0.9), similitud difflib
        if n == q:
            return (1.0, -len(nombre))
        if n.startswith(q):
            return (0.95, -len(nombre))
        if q in n:
            return (0.90, -len(nombre))
        # token overlap
        q_tokens = set(q.split())
        n_tokens = set(n.split())
        inter = len(q_tokens & n_tokens)
        jacc = inter / max(1, len(q_tokens | n_tokens))
        sm = difflib.SequenceMatcher(None, q, n).ratio()
        return (0.5 * sm + 0.5 * jacc, -len(nombre))

    ordenados = sorted(universe, key=score, reverse=True)
    # Traer exacta primero si existe
    exactos = [n for n in ordenados if normalizar(n) == q]
    if exactos:
        ordenados = exactos + [n for n in ordenados if normalizar(n) != q]
    return ordenados[:top_n]

try:
    df_clientes = obtener_hoja_clientes_cached()
except Exception:
    st.error("❌ No se pudo acceder a la hoja de clientes. Esperá unos segundos e intentá de nuevo.")
    st.stop()

nombres = sorted(df_clientes["CLIENTE"].dropna().unique())

# ---------------- Alta rápida de CLIENTE ----------------
usuario_codigo = st.session_state.mail_ingresado.split("@")[0][:2].upper()
with st.container(border=True):
    st.markdown("**➕ Alta rápida**: escribí un cliente nuevo y guardalo directo en la hoja *CLIENTES*. Queda asignado a tu usuario.")
    cols = st.columns([3,1])
    nuevo_cliente = cols[0].text_input("👤 Cliente (podés escribir libremente):", value="", key="cliente_libre")
    agregar = cols[1].button("Guardar", key="btn_alta_cliente", use_container_width=True, disabled=not nuevo_cliente.strip())
    if agregar:
        try:
            agregar_cliente_si_no_existe(nuevo_cliente.strip(), usuario_codigo)
            st.toast("✅ Cliente agregado a la hoja CLIENTES")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"⚠️ No se pudo agregar: {e}")

# ---------------- Pestañas principales ----------------

tabs = st.tabs(["📞 Cargar Contactos", "📅 Recordatorios Pendientes"])

with tabs[0]:
    st.title("📋 Registro de Contactos Comerciales")

    modo_carga = st.radio(
        "🔀 ¿Cómo querés cargar el contacto?",
        ["Carga guiada", "Carga rápida", "Carga múltiple"],
        horizontal=True
    )

    if modo_carga == "Carga guiada":
        # Autocompletado mejorado
        nombres = sorted(df_clientes["CLIENTE"].unique())
        q = st.text_input("🔎 Buscá el cliente por nombre o parte del nombre:")
        opciones = rankear_coincidencias(q, nombres, top_n=40) if q else nombres
        cliente_seleccionado = st.selectbox("👤 Cliente:", opciones, key="cg_cliente")

        # 👉 El selector de "Próximo contacto" VA FUERA DEL FORM para que aparezca el date picker al instante
        agendar = st.radio("📅 Próximo contacto?", ["No", "Sí"], key="up_agenda")

        with st.form("form_guiada", clear_on_submit=True):
            fecha_contacto = st.date_input("📅 Fecha del contacto:", format="YYYY/MM/DD", key="cg_fecha")
            tipo_contacto = st.selectbox("📞 Tipo de contacto:", ["LLAMADA", "MENSAJES", "REUNION", "OTRO"], key="cg_tipo")
            motivo_contacto = st.text_input("📝 Motivo:", placeholder="Ej: revisión de cartera", key="cg_motivo")
            estado = st.selectbox("📌 Estado:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"], key="up_estado")

            # Si tildaste "Sí" arriba, ahora sí mostramos el selector de fecha dentro del form
            proximo = ""
            if agendar == "Sí":
                proximo = st.date_input("🗓️ Fecha:", format="YYYY/MM/DD", key="up_prox").strftime("%d/%m/%Y")
            nota = st.text_input("🗒️ Nota:", key="up_nota")
            submitted = st.form_submit_button("Actualizar contacto", use_container_width=True)

        if submitted:
            try:
                frase = f"Se realizó una {tipo_contacto.lower()} con {cliente_seleccionado} el {fecha_contacto.strftime('%d/%m/%Y')} por {motivo_contacto.strip().lower()}"
                registrar_contacto(frase, estado, nota, proximo, df_clientes, procesar_contacto, tipo_contacto)
                st.success("✅ Contacto actualizado correctamente.")
                st.toast("Contacto guardado ✔️ y formulario limpio para seguir cargando")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ {e}")

    elif modo_carga == "Carga rápida":
        st.subheader("⚡ Carga rápida de hoy")
        # Autocompletado también acá
        q2 = st.text_input("🔎 Buscar cliente:")
        opciones2 = rankear_coincidencias(q2, nombres, top_n=40) if q2 else nombres
        cliente_flash = st.selectbox("👤 Cliente:", opciones2, key="flash_cliente")

        with st.form("form_flash", clear_on_submit=True):
            tipo_flash = st.selectbox("📞 Tipo:", ["LLAMADA", "MENSAJES", "REUNION", "OTRO"], key="flash_tipo")
            motivo_flash = st.text_input("📝 Motivo (opcional)", "seguimiento general", key="flash_motivo")
            nota_flash = st.text_input("🗒️ Nota (opcional)", "", key="flash_nota")
            submitted_fast = st.form_submit_button(f"✔️ Contacto con {cliente_flash}")
        
        if submitted_fast:
            try:
                fh = datetime.today().strftime("%d/%m/%Y")
                frase = f"Se realizó una {tipo_flash.lower()} con {cliente_flash} el {fh} por {motivo_flash.strip().lower()}"
                registrar_contacto(frase, "Hecho", nota_flash, "", df_clientes, procesar_contacto, tipo_flash)
                st.success(f"✅ {cliente_flash} registrado.")
                st.toast("Guardado ✔️ – listo para el siguiente")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ {e}")

    elif modo_carga == "Carga múltiple":
        st.subheader("📥 Carga múltiple")
        with st.form("form_multi", clear_on_submit=True):
            texto_masivo = st.text_area("🧾 Una frase por línea:", key="mm_texto")
            estado_masivo = st.selectbox("📌 Estado:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"], key="mm_estado")
            nota_masiva = st.text_input("🗒️ Nota (opcional):", key="mm_nota")
            agendar = st.radio("📅 Agendar próximo contacto?", ["No", "Sí"], key="mm_agenda")
            prox = ""
            if agendar == "Sí":
                prox = st.date_input("🗓️ Próximo contacto:", format="YYYY/MM/DD", key="mm_prox").strftime("%d/%m/%Y")
            submitted_multi = st.form_submit_button("📌 Cargar múltiples")

        if submitted_multi:
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
            st.toast("Carga múltiple procesada")
            st.cache_data.clear()
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
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ {e}")
    else:
        st.success("🎉 No hay pendientes. Buen trabajo.")




