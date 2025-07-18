import datetime
import streamlit as st
import pandas as pd
import os
from utils import extraer_datos
from utils import detectar_tipo

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

def formatear_historial_exportable(df):
    filas = []
    for _, row in df.iterrows():
        cliente = row["Cliente"]
        asesor = row["Asesor"]
        estado = row["Estado"]
        nota = row["Nota"]
        prox = row["Próximo contacto"]

        # Intentar extraer MOTIVO y FECHA desde "Detalle"
        detalle = row["Detalle"]
        if "(" in detalle and detalle.endswith(")"):
            motivo = detalle.rsplit("(", 1)[0].strip()
            fecha_ultimo = detalle.rsplit("(", 1)[1].replace(")", "").strip()
        else:
            motivo = detalle
            fecha_ultimo = row["Fecha"]

        tipo = detectar_tipo(motivo)

        filas.append({
            "CLIENTE": cliente,
            "ASESOR/A": asesor,
            "FECHA ÚLTIMO CONTACTO": fecha_ultimo,
            "TIPO": tipo,
            "MOTIVO": motivo,
            "ESTADO": estado,
            "NOTA": nota,
            "PRÓXIMO CONTACTO": prox
        })

    return pd.DataFrame(filas)

