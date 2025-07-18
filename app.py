import streamlit as st
import base64
import pandas as pd
import unicodedata
import requests
from io import BytesIO

# Mostrar logo centrado arriba
def mostrar_logo():
    with open("Logo_Final.png", "rb") as f:
        logo_bytes = f.read()
        encoded = base64.b64encode(logo_bytes).decode()
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; margin-top: 5px; margin-bottom: -30px;">
                <img src="data:image/png;base64,{encoded}" alt="PMUNIVE Logo" style="width: 180px; max-width: 100%;">
            </div>
            """,
            unsafe_allow_html=True
        )

mostrar_logo()

# Configuración de página
st.set_page_config(page_title="🧮 Cruce de Archivos", layout="wide")

# === Título e instrucciones ===
st.title("🧮 Aplicación para cruzar y filtrar archivos de Excel o CSV")
st.markdown("""
Bienvenido/a 👋  
Esta herramienta permite cruzar archivos por una columna común, aplicar filtros, seleccionar columnas y descargar el resultado.

### 🧭 Pasos para usar la app:
1. **Carga uno o más archivos (.csv o .xlsx) o desde URL**
2. Selecciona la **columna clave** para cruzar
3. (Opcional) Aplica filtros por columna
4. (Opcional) Elige qué columnas exportar
5. Escribe el nombre del archivo de salida y **descárgalo**
""")

# === Función para normalizar columnas ===
def normalizar_columna(col):
    col = col.strip().lower()
    col = unicodedata.normalize('NFKD', col)
    col = col.encode('ascii', 'ignore').decode('utf-8')
    return col

# === Cargar archivos desde local o URL ===
opcion_carga = st.radio("📤 Subida de archivos o carga por URL", ["Subir archivos", "Usar URLs"], horizontal=True)
archivos = []

if opcion_carga == "Subir archivos":
    uploaded_files = st.file_uploader("Carga tus archivos (.csv o .xlsx)", type=['csv', 'xlsx'], accept_multiple_files=True)
    if uploaded_files:
        for file in uploaded_files:
            if file.size > 100 * 1024 * 1024:
                st.error(f"❌ El archivo {file.name} supera el límite de 100 MB.")
                continue
            with st.spinner(f"⏳ Cargando {file.name}..."):
                try:
                    if file.name.endswith('.csv'):
                        df = pd.read_csv(file, sep=';', encoding='utf-8', on_bad_lines='skip', low_memory=False)
                    else:
                        df = pd.read_excel(file)
                    df.columns = [normalizar_columna(c) for c in df.columns]
                    archivos.append(df)
                    st.success(f"✅ {file.name} cargado con {df.shape[0]} filas")
                except Exception as e:
                    st.error(f"❌ Error al cargar {file.name}: {e}")

elif opcion_carga == "Usar URLs":
    urls_input = st.text_area("Pega aquí las URLs de los archivos (una por línea)", height=100)
    if st.button("📥 Cargar desde URLs"):
        urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
        for url in urls:
            try:
                with st.spinner(f"⏳ Descargando archivo desde URL..."):
                    response = requests.get(url)
                    filename = url.split("/")[-1].split("?")[0]
                    if ".csv" in filename:
                        df = pd.read_csv(BytesIO(response.content), sep=';', encoding='utf-8', on_bad_lines='skip', low_memory=False)
                    elif ".xlsx" in filename:
                        df = pd.read_excel(BytesIO(response.content))
                    else:
                        st.warning(f"❗ Formato no reconocido en URL: {url}")
                        continue
                    df.columns = [normalizar_columna(c) for c in df.columns]
                    archivos.append(df)
                    st.success(f"✅ Archivo desde URL cargado con {df.shape[0]} filas")
            except Exception as e:
                st.error(f"❌ Error al descargar desde {url}: {e}")

if len(archivos) >= 2:
    columnas_comunes = set(archivos[0].columns)
    for df in archivos[1:]:
        columnas_comunes &= set(df.columns)

    if columnas_comunes:
        columna_clave = st.selectbox("🔑 Selecciona la columna clave para cruzar:", sorted(columnas_comunes))

        # === Cruce ===
        with st.spinner("🔗 Cruzando archivos..."):
            resultado = archivos[0]
            for df in archivos[1:]:
                resultado = pd.merge(resultado, df, on=columna_clave, how='inner')
            st.info(f"🔗 Cruce completado con {resultado.shape[0]} filas.")

        # === Filtros ===
        st.subheader("🎯 Filtros opcionales")
        columnas_filtro = st.multiselect("Selecciona columnas para filtrar:", resultado.columns.tolist())
        for col in columnas_filtro:
            opciones = resultado[col].dropna().unique().tolist()
            seleccion = st.multiselect(f"Selecciona valores para '{col}':", opciones)
            if seleccion:
                resultado = resultado[resultado[col].isin(seleccion)]
                st.success(f"✅ Filtro aplicado en '{col}'. Filas restantes: {resultado.shape[0]}")

        # === Selección de columnas ===
        st.subheader("✂️ Selecciona columnas a exportar")
        columnas_exportar = st.multiselect("¿Qué columnas deseas incluir en el archivo final?", resultado.columns.tolist(), default=resultado.columns.tolist())
        resultado = resultado[columnas_exportar]

        # === Nombre y descarga ===
        nombre_salida = st.text_input("📄 Nombre del archivo de salida:", "resultado_cruce")
        buffer = BytesIO()
        with st.spinner("📦 Generando archivo para descarga..."):
            resultado.to_excel(buffer, index=False, engine='openpyxl')
            buffer.seek(0)

        st.download_button(
            label="📥 Descargar archivo Excel",
            data=buffer,
            file_name=f"{nombre_salida.strip()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # === Vista previa ===
        st.subheader("👀 Vista previa")
        st.dataframe(resultado.head())

    else:
        st.error("❌ No se encontraron columnas comunes entre todos los archivos.")
else:
    st.info("📁 Debes cargar al menos 2 archivos para continuar.")

# === Pie de página ===
st.markdown("---")
st.caption("🔧 Desarrollado por Paulo Munive • App con Streamlit • © 2025")
