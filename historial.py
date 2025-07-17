# historial.py

import datetime
import streamlit as st
from utils import extraer_datos

def guardar_en_historial(cliente_real, hoja_registro, frase, estado, nota, proximo_contacto):
    try:
        cliente_nombre, fecha_detalle, motivo = extraer_datos(frase)
        detalle_actual = f"{motivo} ({fecha_detalle})"
    except Exception:
        detalle_actual = frase  # fallback si falla el parseo

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

    # Evitar duplicados exactos
    if (
        st.session_state.historial and
        st.session_state.historial[0]["Cliente"] == cliente_real and
        st.session_state.historial[0]["Detalle"] == detalle_actual
    ):
        st.session_state.historial.pop(0)

    st.session_state.historial.insert(0, nuevo_registro)
    st.session_state.historial = st.session_state.historial[:90]  # Limitar a 90 entradas
