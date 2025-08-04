import datetime
from utils import extraer_datos, detectar_tipo, normalizar
from historial import guardar_en_historial


def buscar_coincidencia(nombre_cliente, df_clientes):
    normal_input = normalizar(nombre_cliente)

    exactas = [
        (i + 2, row["CLIENTE"], row["ASESOR/A"])
        for i, row in df_clientes.iterrows()
        if normalizar(row["CLIENTE"]) == normal_input
    ]
    if exactas:
        return exactas

    parciales = [
        (i + 2, row["CLIENTE"], row["ASESOR/A"])
        for i, row in df_clientes.iterrows()
        if normal_input in normalizar(row["CLIENTE"]) or normalizar(row["CLIENTE"]) in normal_input
    ]
    if len(parciales) == 1:
        return parciales

    if len(parciales) > 1:
        nombres = [c[1] for c in parciales]
        raise ValueError(f"Coincidencias múltiples para '{nombre_cliente}': {', '.join(nombres)}")

    raise ValueError(f"No se encontró ninguna coincidencia para '{nombre_cliente}'.")

def registrar_contacto(frase, estado, nota, proximo_contacto, df_clientes, procesar_fn, tipo_forzado=None):
    try:
        cliente_input, _, _ = extraer_datos(frase)
        coincidencias = buscar_coincidencia(cliente_input, df_clientes)

        if len(coincidencias) != 1:
            raise ValueError("Cliente no claro o ambigüedad no resuelta.")

        _, cliente_real, asesor = coincidencias[0]
        tipo_contacto = tipo_forzado if tipo_forzado else detectar_tipo(frase)

        hoja = procesar_fn(
            cliente_real,
            _,
            frase,
            estado,
            proximo_contacto,
            nota,
            extraer_datos,
            lambda _: tipo_contacto
        )
        guardar_en_historial(cliente_real, hoja, frase, estado, nota, proximo_contacto)
        return cliente_real, hoja

    except ValueError as e:
        mensaje = str(e)
        if "no se encontró" in mensaje.lower() or "coincidencias múltiples" in mensaje.lower():
            sugerencias = sugerir_clientes_similares(cliente_input, df_clientes)
            if sugerencias:
                sugerencia_texto = ", ".join(sugerencias)
                raise ValueError(f"{mensaje}. ¿Quisiste decir: {sugerencia_texto}?")
        raise

def sugerir_clientes_similares(nombre_cliente, df_clientes, max_sugerencias=5):
    normal_input = normalizar(nombre_cliente)
    sugerencias = [
        c for c in df_clientes["CLIENTE"].dropna().unique()
        if normal_input in normalizar(c) or normalizar(c) in normal_input
    ]
    return sorted(sugerencias)[:max_sugerencias]


