import datetime
import streamlit as st
import pandas as pd
import os
from utils import extraer_datos

ARCHIVO_HISTORIAL = "historial_completo.csv"

def guardar_en_historial(cliente_real, hoja_registro, frase, estado, nota, proximo_contacto):
    try:
        cliente_nombre, fecha_detalle, motivo = extraer_datos(frase)
        detalle_actual = f"{motivo} ({fecha_detalle})"
    except Exception:
        detalle_actual = frase

    fecha_hoy = datetime.datetime.now().strftime("%d/%m/%Y")
    nuevo_registro = {
        "Cliente": cliente_real,
        "Detalle": detalle_actual,
        "Fecha": fecha_hoy,
        "Estado": estado,
        "Nota": nota,
        "Próximo contacto": proximo_contacto,
        "Asesor": hoja_registro
    }

    # Verificar duplicado en sesión
    if "historial" not in st.session_state:
        st.session_state.historial = []

    for reg in st.session_state.historial:
        if (
            reg["Cliente"] == cliente_real and
            reg["Detalle"] == detalle_actual and
            reg["Fecha"] == fecha_hoy
        ):
            return  # ⚠️ No guardar duplicado

    st.session_state.historial.insert(0, nuevo_registro)
    st.session_state.historial = st.session_state.historial[:90]

    # Verificar duplicado en CSV
    if os.path.exists(ARCHIVO_HISTORIAL):
        df_hist = pd.read_csv(ARCHIVO_HISTORIAL)
        duplicado = df_hist[
            (df_hist["Cliente"] == cliente_real) &
            (df_hist["Detalle"] == detalle_actual) &
            (df_hist["Fecha"] == fecha_hoy)
        ]
        if duplicado.empty:
            pd.DataFrame([nuevo_registro]).to_csv(ARCHIVO_HISTORIAL, mode='a', header=False, index=False)
    else:
        pd.DataFrame([nuevo_registro]).to_csv(ARCHIVO_HISTORIAL, index=False)

def cargar_historial_completo():
    if os.path.exists(ARCHIVO_HISTORIAL):
        return pd.read_csv(ARCHIVO_HISTORIAL)
    else:
        return pd.DataFrame(columns=["Cliente", "Detalle", "Fecha", "Estado", "Nota", "Próximo contacto", "Asesor"])

