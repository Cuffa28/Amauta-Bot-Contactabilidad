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

    nuevo_registro = {
        "Cliente": cliente_real,
        "Detalle": detalle_actual,
        "Fecha": datetime.datetime.now().strftime("%d/%m/%Y"),
        "Estado": estado,
        "Nota": nota,
        "Próximo contacto": proximo_contacto,
        "Asesor": hoja_registro
    }

    if "historial" not in st.session_state:
        st.session_state.historial = []

    if (
        st.session_state.historial and
        st.session_state.historial[0]["Cliente"] == cliente_real and
        st.session_state.historial[0]["Detalle"] == detalle_actual
    ):
        st.session_state.historial.pop(0)

    st.session_state.historial.insert(0, nuevo_registro)
    st.session_state.historial = st.session_state.historial[:90]

    df_historial = pd.DataFrame([nuevo_registro])
    if os.path.exists(ARCHIVO_HISTORIAL):
        df_historial.to_csv(ARCHIVO_HISTORIAL, mode='a', header=False, index=False)
    else:
        df_historial.to_csv(ARCHIVO_HISTORIAL, index=False)

def cargar_historial_completo():
    if os.path.exists(ARCHIVO_HISTORIAL):
        return pd.read_csv(ARCHIVO_HISTORIAL)
    else:
        return pd.DataFrame(columns=["Cliente", "Detalle", "Fecha", "Estado", "Nota", "Próximo contacto", "Asesor"])
