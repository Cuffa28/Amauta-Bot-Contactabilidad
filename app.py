# app.py – versión completa, corregida y lista para pegar
# Funcionalidades:
# - Confirmación + limpieza de formularios (clear_on_submit) y toasts
# - Autocompletado mejorado (buscador + ranking de coincidencias)
# - Alta rápida de clientes (agrega a hoja CLIENTES con el asesor logueado)
# - Mini panel “Lo cargado” (Solo hoy / Últimos 30) + buscador + deduplicado
# - Filtro por ASESOR para que cada uno vea solo lo suyo (y alerta de duplicado por asesor)
# - Selector de próximo contacto que aparece al marcar "Sí"

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional
import difflib

# === IMPORTS de conectores a Drive con *fallback* seguro ===
try:
    import drive_utils as drive_local
except Exception as e:
    drive_local = None
    st.warning(f"⚠️ No se pudo importar drive_utils (Local). Motivo: {e}")

try:
    import drive_utils_internacional as drive_int
except Exception as e:
    drive_int = None
    st.warning(f"⚠️ No se pudo importar drive_utils_internacional. Motivo: {e}")

# Si no se pudieron importar, defino *stubs* para que la app arranque igual
if drive_local is None and drive_int is None:
    st.info("🚧 Modo sin conectores: se usarán funciones de prueba (no escriben en Drive).")

    def _stub_obtener_hoja_clientes():
        # hoja mínima para que cargue el combo de clientes
        return pd.DataFrame({"CLIENTE": ["CLIENTE DEMO 1", "CLIENTE DEMO 2"]})

    def _stub_procesar_contacto(*args, **kwargs):
        st.toast("(Demo) Contacto procesado localmente")

    def _stub_marcar_contacto_como_hecho(*args, **kwargs):
        st.toast("(Demo) Recordatorio marcado como hecho")

    def _stub_obtener_recordatorios_pendientes(*args, **kwargs):
        return []

    def _stub_agregar_cliente_si_no_existe(*args, **kwargs):
        st.toast("(Demo) Cliente agregado localmente")

    # Asigno los stubs a ambas variantes para que el resto del código funcione
    class _DL:  # dummy local/internacional
        obtener_hoja_clientes = staticmethod(_stub_obtener_hoja_clientes)
        procesar_contacto = staticmethod(_stub_procesar_contacto)
        marcar_contacto_como_hecho = staticmethod(_stub_marcar_contacto_como_hecho)
        obtener_recordatorios_pendientes = staticmethod(_stub_obtener_recordatorios_pendientes)
        agregar_cliente_si_no_existe = staticmethod(_stub_agregar_cliente_si_no_existe)

    drive_local = _DL
    drive_int = _DL

from historial import cargar_historial_completo, formatear_historial_exportable
from gestor_contactos import registrar_contacto
from utils import normalizar

# ------------------- Autenticación simple -------------------
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

# ---------------- Selección de planilla ----------------
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

# --- Identificador del asesor actual (para filtrar mini panel/alertas) ---
usuario_codigo_actual = st.session_state.mail_ingresado.split("@")[0][:2].upper()
# En Locales el historial guarda el código corto (AC, JE, etc.).
# En Internacionales podría guardar el nombre de hoja; si existe un helper, usarlo; si no, usamos el código igual.
asesor_actual = usuario_codigo_actual

# ------------------- helpers --------------------
@st.cache_data(ttl=60)
def obtener_hoja_clientes_cached():
    return obtener_hoja_clientes()

# ranking de coincidencias para el buscador

def rankear_coincidencias(query: str, universe: list[str], top_n: int = 50) -> list[str]:
    if not query:
        return universe
    q = normalizar(query)

    def score(nombre: str) -> tuple:
        n = normalizar(nombre)
        if n == q:
            return (1.0, -len(nombre))
        if n.startswith(q):
            return (0.95, -len(nombre))
        if q in n:
            return (0.90, -len(nombre))
        q_tokens = set(q.split())
        n_tokens = set(n.split())
        inter = len(q_tokens & n_tokens)
        jacc = inter / max(1, len(q_tokens | n_tokens))
        sm = difflib.SequenceMatcher(None, q, n).ratio()
        return (0.5 * sm + 0.5 * jacc, -len(nombre))

    ordenados = sorted(universe, key=score, reverse=True)
    exactos = [n for n in ordenados if normalizar(n) == q]
    if exactos:
        ordenados = exactos + [n for n in ordenados if normalizar(n) != q]
    return ordenados[:top_n]

# panel/alerta anti-duplicados

def _df_hist_sesion() -> pd.DataFrame:
    if "historial" in st.session_state and st.session_state.historial:
        return pd.DataFrame(st.session_state.historial)
    return pd.DataFrame(columns=["Cliente","Detalle","Fecha","Estado","Nota","Próximo contacto","Asesor"])


def mostrar_alerta_posible_duplicado(cliente: str, asesor_actual: str):
    """Advierte si HOY ya cargaste algo para ese cliente.
    Si el código del asesor no coincide con lo que hay en la planilla, NO filtra (para no ocultar registros).
    """
    hoy = datetime.now().strftime("%d/%m/%Y")
    df = pd.concat([_df_hist_sesion(), cargar_historial_completo()], ignore_index=True)
    if df.empty:
        return

    # Normalizo Asesor
    asesores_norm = df["Asesor"].astype(str).str.strip().str.upper()
    target = str(asesor_actual).strip().upper()

    # Si el target existe tal cual, filtro exacto; si no, pruebo startswith/contains; si ninguna matchea, NO filtro
    if (asesores_norm == target).any():
        df = df[asesores_norm == target]
    elif asesores_norm.str.startswith(target).any():
        df = df[asesores_norm.str.startswith(target)]
    elif asesores_norm.str.contains(target, na=False).any():
        df = df[asesores_norm.str.contains(target, na=False)]

    if not df.empty and any((df["Cliente"].str.upper() == cliente.upper()) & (df["Fecha"] == hoy)):
        st.warning("⚠️ Ya tenés un registro HOY para este cliente. Mirá el mini panel para no duplicar.")


def render_mini_panel(
    cliente_foco: Optional[str] = None,
    asesor_actual: Optional[str] = None,
    key_prefix: str = "mini",
):
    """Panel con Solo hoy / Últimos 30 + buscador.
    - Muestra registros por asesor con un SELECTOR visible.
    - Si el código de asesor no coincide, podés elegir manualmente cuál ver.
    - Saca duplicados entre sesión y CSV.
    - Usa claves únicas por instancia (key_prefix) para evitar StreamlitDuplicateElementKey.
    """
    df_s = _df_hist_sesion()
    df_c = cargar_historial_completo()
    df = pd.concat([df_s, df_c], ignore_index=True)
    if df.empty:
        return

    # Dedup básico
    df = df.drop_duplicates(subset=["Cliente", "Detalle", "Fecha"], keep="first")

    # --- Selector de asesor ---
    asesores_disponibles = (
        df["Asesor"].dropna().astype(str).str.strip().unique().tolist()
    )
    asesores_disponibles = sorted([a for a in asesores_disponibles if a])

    # Sugerencia de índice según asesor_actual
    idx_def = 0
    if asesor_actual:
        target = str(asesor_actual).strip().upper()
        for i, a in enumerate(asesores_disponibles):
            au = a.strip().upper()
            if au == target or au.startswith(target) or target in au:
                idx_def = i
                break

    if asesores_disponibles:
        sel_asesor = st.selectbox(
            "👤 Asesor a mostrar:", asesores_disponibles, index=idx_def, key=f"{key_prefix}_sel_asesor"
        )
        df = df[df["Asesor"].astype(str).str.strip() == sel_asesor]
    else:
        st.info("No hay columna 'Asesor' o está vacía en el historial.")
        return

    # Controles del panel (con keys únicas)
    modo = st.radio(
        "🧾 Qué ver en el panel:", ["Solo hoy", "Últimos 30"], horizontal=True, key=f"{key_prefix}_modo"
    )
    filtro_texto = st.text_input("🔎 Filtrar por cliente/motivo/nota:", key=f"{key_prefix}_busca")
    filtrar_cliente_actual = st.checkbox("👤 Ver solo cliente actual", value=False, key=f"{key_prefix}_toggle")

    if modo == "Solo hoy":
        hoy = datetime.now().strftime("%d/%m/%Y")
        df = df[df["Fecha"] == hoy]
    else:
        df = df.tail(30)

    if filtrar_cliente_actual and cliente_foco:
        df = df[df["Cliente"].str.contains(cliente_foco, case=False, na=False)]

    if filtro_texto:
        mask = (
            df["Cliente"].str.contains(filtro_texto, case=False, na=False)
            | df["Detalle"].str.contains(filtro_texto, case=False, na=False)
            | df["Nota"].str.contains(filtro_texto, case=False, na=False)
        )
        df = df[mask]

    if df.empty:
        st.info("No hay registros para ese filtro.")
        return

    with st.expander("🧾 Lo cargado (mini panel)", expanded=True):
        st.dataframe(
            df[["Fecha", "Cliente", "Detalle", "Estado", "Nota", "Próximo contacto", "Asesor"]].reset_index(drop=True),
            hide_index=True,
            use_container_width=True,
            height=260,
        )

# ------------------- Datos base --------------------
try:
    df_clientes = obtener_hoja_clientes_cached()
except Exception:
    st.error("❌ No se pudo acceder a la hoja de clientes. Esperá unos segundos e intentá de nuevo.")
    st.stop()

nombres = sorted(df_clientes["CLIENTE"].dropna().unique())

# ---------------- Alta rápida de CLIENTE ----------------
usuario_codigo = usuario_codigo_actual  # reuso
with st.container(border=True):
    st.markdown("**➕ Alta rápida**: escribí un cliente nuevo y guardalo directo en la hoja *CLIENTES*. Queda asignado a tu usuario.")
    cols = st.columns([3, 1])
    nuevo_cliente = cols[0].text_input("👤 Cliente (podés escribir libremente):", value="", key="cliente_libre")
    agregar = cols[1].button("Guardar", key="btn_alta_cliente", use_container_width=True, disabled=not nuevo_cliente.strip())
    if agregar:
        try:
            agregar_cliente_si_no_existe(nuevo_cliente.strip(), usuario_codigo)
            st.toast("✅ Cliente agregado a la hoja CLIENTES")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"⚠️ No se pudo agregar: {e}")

# ---------------- Pestañas ----------------
tabs = st.tabs(["📞 Cargar Contactos", "📅 Recordatorios Pendientes"])

with tabs[0]:
    st.title("📋 Registro de Contactos Comerciales")

    modo_carga = st.radio(
        "🔀 ¿Cómo querés cargar el contacto?",
        ["Carga guiada", "Carga rápida", "Carga múltiple"],
        horizontal=True,
    )

    if modo_carga == "Carga guiada":
        q = st.text_input("🔎 Buscá el cliente por nombre o parte del nombre:")
        opciones = rankear_coincidencias(q, nombres, top_n=40) if q else nombres
        cliente_seleccionado = st.selectbox("👤 Cliente:", opciones, key="cg_cliente")

        # Alerta anti-duplicado (por asesor)
        mostrar_alerta_posible_duplicado(cliente_seleccionado, asesor_actual)

        # Radio fuera del form para que el date picker aparezca al instante
        agendar = st.radio("📅 Próximo contacto?", ["No", "Sí"], key="up_agenda")

        with st.form("form_guiada", clear_on_submit=True):
            fecha_contacto = st.date_input("📅 Fecha del contacto:", format="YYYY/MM/DD", key="cg_fecha")
            tipo_contacto = st.selectbox("📞 Tipo de contacto:", ["LLAMADA", "MENSAJES", "REUNION", "OTRO"], key="cg_tipo")
            motivo_contacto = st.text_input("📝 Motivo:", placeholder="Ej: revisión de cartera", key="cg_motivo")
            estado = st.selectbox("📌 Estado:", ["En curso", "Hecho", "REUNION", "Respuesta positiva"], key="up_estado")

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
                st.toast("Guardado ✔️ – formulario limpio para seguir cargando")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ {e}")

        # Mini panel filtrado por el asesor actual (y opcional por cliente)
        render_mini_panel(cliente_seleccionado, asesor_actual, key_prefix="panel_guiada")

    elif modo_carga == "Carga rápida":
        st.subheader("⚡ Carga rápida de hoy")
        q2 = st.text_input("🔎 Buscar cliente:")
        opciones2 = rankear_coincidencias(q2, nombres, top_n=40) if q2 else nombres
        cliente_flash = st.selectbox("👤 Cliente:", opciones2, key="flash_cliente")

        mostrar_alerta_posible_duplicado(cliente_flash, asesor_actual)

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

        render_mini_panel(cliente_flash, asesor_actual, key_prefix="panel_rapida")

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
            lineas = [l.strip() for l in texto_masivo.splitlines() if l.strip()]
            for idx, l in enumerate(lineas, start=1):
                try:
                    registrar_contacto(
                        l,
                        estado_masivo,
                        nota_masiva,
                        prox,
                        df_clientes,
                        procesar_contacto,
                    )
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
        key="descarga_historial",
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


