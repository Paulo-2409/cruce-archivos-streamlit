import streamlit as st
import streamlit_sortables as sortables
import base64
import pandas as pd
import unicodedata
from io import BytesIO
import os
import gdown
import json
from datetime import datetime

# === Configuración inicial ===
TEMP_DIR = "/tmp"
os.makedirs(TEMP_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(TEMP_DIR, "config_cruce.json")

# === Funciones auxiliares ===
def mostrar_logo():
    with open("Logo_pmunive.png", "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
        st.markdown(f"""
            <div style='display: flex; justify-content: center; margin-top: 5px; margin-bottom: -30px;'>
                <img src='data:image/png;base64,{encoded}' alt='PMUNIVE Logo' style='width: 180px;'>
            </div>
        """, unsafe_allow_html=True)

def normalizar_columna(col):
    col = col.strip().lower()
    col = unicodedata.normalize('NFKD', col)
    return col.encode('ascii', 'ignore').decode('utf-8')

def cargar_archivo(file, nombre_mostrar=None):
    filename = file.name if hasattr(file, 'name') else file
    if filename.endswith(".csv"):
        return pd.read_csv(file, sep=";", encoding="utf-8", on_bad_lines="skip", low_memory=False)
    else:
        xl = pd.ExcelFile(file, engine='openpyxl')
        hoja = st.selectbox(f"📄 Selecciona la hoja de {nombre_mostrar or filename}:", xl.sheet_names, key=f"hoja_{nombre_mostrar}")
        return xl.parse(hoja)

def guardar_configuracion(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def cargar_configuracion():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def generar_descarga(resultado, nombre_archivo):
    buffer = BytesIO()
    resultado.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    st.download_button("📥 Descargar archivo Excel", buffer, file_name=f"{nombre_archivo}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# === Lógica principal ===
def main():
    st.set_page_config(page_title="🧮 Cruce de Archivos", layout="wide")
    mostrar_logo()

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

    st.subheader("📥 Subida de archivos o carga por URL")
    modo_carga = st.radio("¿Cómo quieres cargar los archivos?", ["Subir archivos", "Usar URLs", "Ambos"], horizontal=True)

    archivos = []

    if modo_carga in ["Subir archivos", "Ambos"]:
        uploaded_files = st.file_uploader("📤 Sube tus archivos (.csv o .xlsx)", type=['csv', 'xlsx'], accept_multiple_files=True)
        for file in uploaded_files:
            try:
                df = cargar_archivo(file, file.name)
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
                    df = cargar_archivo(output_path, url)
                    df.columns = [normalizar_columna(c) for c in df.columns]
                    archivos.append(df)
                    st.success(f"✅ Archivo desde URL cargado con {df.shape[0]} filas")
                except Exception as e:
                    st.error(f"❌ No se pudo cargar: {url}\n{e}")

    if len(archivos) >= 2:
        resultado = None

        st.subheader("🔑 Selecciona las columnas clave y tipo de cruce")
        columnas_clave = []
        for i, df in enumerate(archivos):
            col = st.selectbox(f"Columna clave del archivo {i+1}:", df.columns.tolist(), key=f"col_df_{i}")
            columnas_clave.append(col)

        tipos_cruce_legibles = {
            "🟢 Coincidencias en ambos archivos (INNER JOIN)": "inner",
            "🟡 Todos del primer archivo, más coincidencias del segundo (LEFT JOIN)": "left",
            "🔵 Todos del segundo archivo, más coincidencias del primero (RIGHT JOIN)": "right",
            "⚪ Todos los registros de ambos archivos (FULL OUTER JOIN)": "outer"
        }

        tipo_legible = st.selectbox("Tipo de cruce:", list(tipos_cruce_legibles.keys()))
        tipo_cruce = tipos_cruce_legibles[tipo_legible]

        modo_resultado = st.selectbox("¿Qué deseas obtener del cruce?", [
            "🟢 Solo coincidencias",
            "🔴 Solo no coincidencias",
            "⚪ Todo (coincidencias y no coincidencias)",
            "🆕 Solo registros nuevos del segundo archivo (como un BUSCARX)"
        ])

        if modo_resultado == "🆕 Solo registros nuevos del segundo archivo (como un BUSCARX)":
            try:
                df_a = archivos[0]
                df_b = archivos[1]
                col_a = columnas_clave[0]
                col_b = columnas_clave[1]

                resultado = df_b[~df_b[col_b].isin(df_a[col_a])]
                st.success(f"✅ Comparación completada: {resultado.shape[0]} registros nuevos encontrados en el segundo archivo.")

                if not resultado.empty:
                    st.subheader("👀 Vista previa del resultado")
                    st.dataframe(resultado.head())

                    fecha_actual = datetime.today().strftime("%Y%m%d")
                    nombre_salida = st.text_input("📄 Nombre del archivo de salida:", f"Recobro_Impagos_{fecha_actual}")
                    generar_descarga(resultado, nombre_salida)

                st.stop()

            except Exception as e:
                st.error(f"❌ Error en la comparación tipo BUSCARX: {e}")
                st.stop()

        if modo_resultado != "🆕 Solo registros nuevos del segundo archivo (como un BUSCARX)":
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

                        columnas_dup = [col for col in resultado.columns if "_dup" in col]
                        resultado["_indicador"] = resultado[columnas_dup].notna().any(axis=1)

                        if modo_resultado == "🟢 Solo coincidencias":
                            resultado = resultado[resultado["_indicador"] == True]
                        elif modo_resultado == "🔴 Solo no coincidencias":
                            resultado = resultado[resultado["_indicador"] == False]

                        resultado.drop(columns=["_indicador"], inplace=True)

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

        if resultado is not None and not resultado.empty:
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

            if st.button("🔄 Reiniciar aplicación"):
                config = cargar_configuracion() if os.path.exists(CONFIG_FILE) else {}

                for archivo in os.listdir(TEMP_DIR):
                    archivo_path = os.path.join(TEMP_DIR, archivo)
                    try:
                        os.remove(archivo_path)
                    except Exception as e:
                        st.warning(f"No se pudo eliminar {archivo_path}: {e}")

                st.session_state.clear()
                st.session_state["config_prev"] = config
                st.markdown("<meta http-equiv='refresh' content='0'>", unsafe_allow_html=True)

            st.subheader("📂 Cargar configuración guardada")
            if os.path.exists(CONFIG_FILE):
                if st.button("📥 Aplicar configuración previa"):
                    config_prev = cargar_configuracion()
                    st.session_state["columnas_clave"] = config_prev.get("columnas_clave", [])
                    st.session_state["tipo_cruce"] = config_prev.get("tipo_cruce", "inner")
                    st.session_state["filtros"] = config_prev.get("filtros", {})
                    st.session_state["columnas"] = config_prev.get("columnas", [])
                    st.success("✅ Configuración previa cargada. Sube archivos nuevos para usarla.")

            st.subheader("👀 Vista previa del resultado")
            st.dataframe(resultado.head())

            nombre_salida = st.text_input("📄 Nombre del archivo de salida:", "resultado_cruce")
            generar_descarga(resultado, nombre_salida)
    else:
        st.warning("📁 Debes subir al menos 2 archivos para cruzarlos.")

    st.markdown("---")
    st.caption("🔧 Desarrollado por Paulo Munive • App con Streamlit • © 2025")

# === Ejecutar ===
if __name__ == "__main__":
    main()
