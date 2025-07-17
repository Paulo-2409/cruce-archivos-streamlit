import streamlit as st
import pandas as pd
import unicodedata
from io import BytesIO

st.set_page_config(page_title="Cruzar Archivos", layout="wide")
st.title("🔄 Cruzar archivos por columna común")

# === Función para normalizar columnas ===
def normalizar_columna(col):
    col = col.strip().lower()
    col = unicodedata.normalize('NFKD', col)
    col = col.encode('ascii', 'ignore').decode('utf-8')  # Elimina acentos
    return col

# === Cargar múltiples archivos ===
uploaded_files = st.file_uploader("📤 Sube 2 o más archivos (.csv o .xlsx)", type=['csv', 'xlsx'], accept_multiple_files=True)

if uploaded_files and len(uploaded_files) >= 2:
    archivos = []
    nombres = []
    for file in uploaded_files:
        nombre = file.name
        if nombre.endswith('.csv'):
            df = pd.read_csv(file, sep=';', encoding='utf-8', on_bad_lines='skip', low_memory=False)
        else:
            df = pd.read_excel(file)
        df.columns = [normalizar_columna(col) for col in df.columns]
        archivos.append(df)
        nombres.append(nombre)
        st.success(f"✅ '{nombre}' cargado con {df.shape[0]} filas.")

    # === Detectar columnas comunes ===
    columnas_comunes = set(archivos[0].columns)
    for df in archivos[1:]:
        columnas_comunes &= set(df.columns)

    if columnas_comunes:
        columna_clave = st.selectbox("🔑 Selecciona la columna común para cruzar:", sorted(columnas_comunes))

        # === Cruce de archivos ===
        resultado = archivos[0]
        for df in archivos[1:]:
            resultado = pd.merge(resultado, df, on=columna_clave, how='inner')

        st.success(f"🔗 Cruce completo. Filas resultantes: {resultado.shape[0]}")

        # === Filtrado interactivo por columna ===
        st.subheader("🎯 Filtrar columnas por valores")
        columnas_disponibles = resultado.columns.tolist()
        columnas_filtro = st.multiselect("Selecciona las columnas que quieres filtrar:", columnas_disponibles)

        for col in columnas_filtro:
            valores = resultado[col].dropna().unique().tolist()
            seleccion = st.multiselect(f"Valores para filtrar '{col}':", opciones := sorted(valores), default=[])
            if seleccion:
                resultado = resultado[resultado[col].isin(seleccion)]
                st.success(f"✅ Filtro aplicado en '{col}'. Filas restantes: {resultado.shape[0]}")

        # === Selección de columnas para exportar ===
        st.subheader("✂️ Selección de columnas para exportar")
        columnas_exportar = st.multiselect("Selecciona las columnas que quieres incluir en el archivo final:", resultado.columns.tolist(), default=resultado.columns.tolist())
        resultado = resultado[columnas_exportar]

        # === Nombre del archivo de salida ===
        nombre_salida = st.text_input("📝 Nombre del archivo de salida (sin extensión):", value="resultado_cruce")

        # === Descargar resultado ===
        buffer = BytesIO()
        resultado.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)

        st.download_button(
            label="📥 Descargar archivo",
            data=buffer,
            file_name=f"{nombre_salida.strip()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # === Vista previa final ===
        st.subheader("👀 Vista previa del archivo final")
        st.dataframe(resultado.head())

    else:
        st.error("❌ No hay ninguna columna en común entre todos los archivos.")
else:
    st.info("📁 Sube al menos 2 archivos (.csv o .xlsx) para empezar.")