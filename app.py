import streamlit as st
import base64
import pandas as pd
import unicodedata
from io import BytesIO
import os
import gdown

# Configurar carpeta temporal en Streamlit Cloud
TEMP_DIR = "/tmp"
os.makedirs(TEMP_DIR, exist_ok=True)

# === Logo ===
def mostrar_logo():
    with open("Logo_pmunive.png", "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
        st.markdown(f"""
            <div style='display: flex; justify-content: center; margin-top: 5px; margin-bottom: -30px;'>
                <img src='data:image/png;base64,{encoded}' alt='PMUNIVE Logo' style='width: 180px;'>
            </div>""", unsafe_allow_html=True)

mostrar_logo()

# === Config ===
st.set_page_config(page_title="🧮 Cruce de Archivos", layout="wide")

# === Título ===
st.title("🧮 Aplicación para cruzar y filtrar archivos de Excel o CSV")
st.markdown("""
Bienvenido/a 👋  
Esta herramienta permite cruzar archivos por una columna común, aplicar filtros, seleccionar columnas y descargar el resultado.

### 🧭 Pasos para usar la app:
1. **Carga archivos .csv o .xlsx o introduce URLs públicas de Google Drive**
2. Selecciona la **columna clave** para cruzar
3. (Opcional) Aplica filtros por columna
4. (Opcional) Elige qué columnas exportar
5. Escribe el nombre del archivo de salida y **descárgalo**
""")

# === Funciones auxiliares ===
def normalizar_columna(col):
    col = col.strip().lower()
    col = unicodedata.normalize('NFKD', col)
    return col.encode('ascii', 'ignore').decode('utf-8')

def cargar_archivo(filepath):
    if filepath.endswith(".csv"):
        return pd.read_csv(filepath, sep=";", encoding="utf-8", on_bad_lines="skip", low_memory=False)
    else:
        return pd.read_excel(filepath, engine='openpyxl')

# === Carga combinada ===
st.subheader("📥 Subida de archivos o carga por URL")
modo_carga = st.radio("¿Cómo quieres cargar los archivos?", ["Subir archivos", "Usar URLs", "Ambos"], horizontal=True)

archivos = []

if modo_carga in ["Subir archivos", "Ambos"]:
    uploaded_files = st.file_uploader("📤 Sube tus archivos (.csv o .xlsx)", type=['csv', 'xlsx'], accept_multiple_files=True)
    for file in uploaded_files:
        if file.size > 100 * 1024 * 1024:
            st.warning(f"⚠️ El archivo {file.name} supera los 100MB y no se puede cargar directamente.")
            continue
        try:
            df = pd.read_csv(file, sep=";", encoding="utf-8", on_bad_lines="skip", low_memory=False) if file.name.endswith('.csv') else pd.read_excel(file, engine='openpyxl')
            df.columns = [normalizar_columna(c) for c in df.columns]
            archivos.append(df)
            st.success(f"✅ {file.name} cargado con {df.shape[0]} filas")
        except Exception as e:
            st.error(f"❌ Error al cargar {file.name}: {e}")

if modo_carga in ["Usar URLs", "Ambos"]:
    st.text("🔗 Pega una o más URLs de Google Drive (una por línea):")
    input_urls = st.text_area("📎 URLs de archivos compartidos", height=100)
    if st.button("🌐 Cargar desde URLs"):
        urls = [u.strip() for u in input_urls.split("\n") if u.strip()]
        for url in urls:
            try:
                file_id = ""
                if "/d/" in url:
                    file_id = url.split("/d/")[1].split("/")[0]
                elif "id=" in url:
                    file_id = url.split("id=")[1].split("&")[0]
                if not file_id:
                    st.warning(f"⚠️ Formato no válido: {url}")
                    continue
                gdrive_url = f"https://drive.google.com/uc?id={file_id}"
                output_path = os.path.join(TEMP_DIR, f"{file_id}.file")
                gdown.download(gdrive_url, output_path, quiet=False)
                df = cargar_archivo(output_path)
                df.columns = [normalizar_columna(c) for c in df.columns]
                archivos.append(df)
                st.success(f"✅ Archivo desde URL cargado con {df.shape[0]} filas")
            except Exception as e:
                st.error(f"❌ No se pudo cargar: {url}\n{e}")

# === Procesamiento ===
if len(archivos) >= 2:
    st.subheader("🔑 Selecciona las columnas clave para cruzar")

    columnas_clave = []
    for i, df in enumerate(archivos):
        col = st.selectbox(f"Columna clave del archivo {i+1}:", df.columns.tolist(), key=f"col_df_{i}")
        columnas_clave.append(col)

    if all(columnas_clave):
        with st.spinner("🔗 Cruzando archivos..."):
            try:
                resultado = archivos[0]
                col_izq = columnas_clave[0]

                for i in range(1, len(archivos)):
                    col_der = columnas_clave[i]
                    resultado = pd.merge(
                        resultado,
                        archivos[i],
                        left_on=col_izq,
                        right_on=col_der,
                        how='inner',
                        suffixes=('', f'_dup{i}')
                    )

                # Renombrar la columna clave final como "columna_clave" y eliminar duplicados
                resultado.rename(columns={col_izq: "columna_clave"}, inplace=True)
                for col in columnas_clave[1:]:
                    if col in resultado.columns:
                        resultado.drop(columns=col, inplace=True)

                st.success(f"✅ Cruce completado con {resultado.shape[0]} filas.")
            except Exception as e:
                st.error(f"❌ Error al cruzar archivos: {e}")
                resultado = None
    else:
        st.warning("⚠️ Selecciona una columna en cada archivo para cruzar.")
        resultado = None

    if resultado is not None:
        st.subheader("✏️ Renombra las columnas (opcional)")
        nombres_actuales = resultado.columns.tolist()
        nuevos_nombres = []

        for nombre in nombres_actuales:
            nuevo = st.text_input(f"Renombrar '{nombre}' a:", value=nombre, key=f"rename_{nombre}")
            nuevos_nombres.append(nuevo)

        resultado.columns = nuevos_nombres

        st.subheader("🎯 Filtros opcionales")
        columnas_filtro = st.multiselect("Selecciona columnas para filtrar:", resultado.columns.tolist())
        for col in columnas_filtro:
            opciones = resultado[col].dropna().unique().tolist()
            seleccion = st.multiselect(f"Selecciona valores para '{col}':", opciones, key=f"filtro_{col}")
            if seleccion:
                resultado = resultado[resultado[col].isin(seleccion)]
                st.success(f"✅ Filtro aplicado. Filas restantes: {resultado.shape[0]}")

        st.subheader("✂️ Selecciona y ordena columnas a exportar")

        # Paso 1: selección de columnas
        columnas_default = resultado.columns.tolist()
        columnas_seleccionadas = st.multiselect(
            "Selecciona columnas para incluir:",
            columnas_default,
            default=columnas_default
        )

        # Paso 2: orden personalizado
        orden_columnas = []
        st.markdown("🔃 Ordena las columnas seleccionadas:")
        for i in range(len(columnas_seleccionadas)):
            col = st.selectbox(
                f"Columna en posición {i+1}:",
                [c for c in columnas_seleccionadas if c not in orden_columnas],
                key=f"orden_{i}"
            )
            orden_columnas.append(col)

        resultado = resultado[orden_columnas]

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

        st.subheader("👀 Vista previa")
        st.dataframe(resultado.head())
else:
    st.warning("📁 Debes subir al menos 2 archivos para cruzarlos.")
    
# === Pie ===
st.markdown("---")
st.caption("🔧 Desarrollado por Paulo Munive • App con Streamlit • © 2025")
