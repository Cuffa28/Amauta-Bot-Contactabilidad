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


def registrar_contacto(frase, estado, nota, proximo_contacto, df_clientes, procesar_fn):
    cliente_input, _, _ = extraer_datos(frase)
    coincidencias = buscar_coincidencia(cliente_input, df_clientes)

    if len(coincidencias) != 1:
        raise ValueError("Cliente no claro o ambigüedad no resuelta.")

    _, cliente_real, asesor = coincidencias[0]
    hoja = procesar_fn(
        cliente_real,
        _,
        frase,
        estado,
        proximo_contacto,
        nota,
        extraer_datos,
        detectar_tipo
    )
    guardar_en_historial(cliente_real, hoja, frase, estado, nota, proximo_contacto)
    return cliente_real, hoja
