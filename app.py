import streamlit as st
import streamlit_sortables as sortables
import base64
import pandas as pd
import unicodedata
from io import BytesIO
import os
import gdown
import json

# Configurar carpeta temporal en Streamlit Cloud
TEMP_DIR = "/tmp"
os.makedirs(TEMP_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(TEMP_DIR, "config_cruce.json")

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
2. Selecciona la **columna clave** para cruzar y el tipo de cruce
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

def guardar_configuracion(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def cargar_configuracion():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

# === Carga combinada ===
st.subheader("📥 Subida de archivos o carga por URL")
modo_carga = st.radio("¿Cómo quieres cargar los archivos?", ["Subir archivos", "Usar URLs", "Ambos"], horizontal=True)

archivos = []

if modo_carga in ["Subir archivos", "Ambos"]:
    uploaded_files = st.file_uploader("📤 Sube tus archivos (.csv o .xlsx)", type=['csv', 'xlsx'], accept_multiple_files=True)
    for file in uploaded_files:
        try:
            df = cargar_archivo(file)
            df.columns = [normalizar_columna(c) for c in df.columns]
            archivos.append(df)
            st.success(f"✅ {file.name} cargado con {df.shape[0]} filas")
        except Exception as e:
            st.error(f"❌ Error al cargar {file.name}: {e}")

if modo_carga in ["Usar URLs", "Ambos"]:
    input_urls = st.text_area("📎 URLs de archivos compartidos (una por línea):", height=100)
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

# === Cruce de archivos ===
if len(archivos) >= 2:
    st.subheader("🔑 Selecciona las columnas clave y tipo de cruce")

    columnas_clave = []
    for i, df in enumerate(archivos):
        col = st.selectbox(f"Columna clave del archivo {i+1}:", df.columns.tolist(), key=f"col_df_{i}")
        columnas_clave.append(col)

    tipo_cruce = st.selectbox("Tipo de cruce:", ["inner", "left", "right", "outer"], index=0, help="Selecciona cómo combinar los archivos")

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
                        how=tipo_cruce,
                        suffixes=('', f'_dup{i}')
                    )
                st.success(f"✅ Cruce completado con {resultado.shape[0]} filas.")
            except Exception as e:
                st.error(f"❌ Error al cruzar archivos: {e}")
                resultado = None
    else:
        st.warning("⚠️ Selecciona una columna en cada archivo para cruzar.")
        resultado = None

    if resultado is not None:
        st.subheader("✏️ Renombra las columnas (opcional)")
        nuevos_nombres = [st.text_input(f"Renombrar '{c}' a:", value=c) for c in resultado.columns]
        resultado.columns = nuevos_nombres

        st.subheader("🎯 Filtros opcionales")
        columnas_filtro = st.multiselect("Selecciona columnas para filtrar:", resultado.columns.tolist())
        filtros_aplicados = {}
        for col in columnas_filtro:
            opciones = resultado[col].dropna().unique().tolist()
            seleccion = st.multiselect(f"Valores para '{col}':", opciones)
            if seleccion:
                resultado = resultado[resultado[col].isin(seleccion)]
                filtros_aplicados[col] = seleccion

        st.subheader("✂️ Selecciona y ordena columnas a exportar")
        columnas_seleccionadas = st.multiselect("Selecciona columnas para incluir:", resultado.columns.tolist(), default=resultado.columns.tolist())
        orden_columnas = sortables.sort_items(columnas_seleccionadas)
        resultado = resultado[orden_columnas]

        st.subheader("⚙️ Guardar configuración")
        if st.button("💾 Guardar configuración actual"):
            guardar_configuracion({
                "columnas_clave": columnas_clave,
                "tipo_cruce": tipo_cruce,
                "filtros": filtros_aplicados,
                "columnas": orden_columnas
            })
            st.success("✅ Configuración guardada.")

        st.subheader("👀 Vista previa del resultado")
        st.dataframe(resultado.head())

        nombre_salida = st.text_input("📄 Nombre del archivo de salida:", "resultado_cruce")
        buffer = BytesIO()
        resultado.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)
        st.download_button("📥 Descargar archivo Excel", buffer, file_name=f"{nombre_salida}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.warning("📁 Debes subir al menos 2 archivos para cruzarlos.")

# === Pie ===
st.markdown("---")
st.caption("🔧 Desarrollado por Paulo Munive • App con Streamlit • © 2025")
