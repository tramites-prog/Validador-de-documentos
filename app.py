import json
import time
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Optional

# -------------------------------------------------------------
# Configuración de la interfaz
# -------------------------------------------------------------
st.set_page_config(page_title="Validador", layout="centered")

if "historial_registros" not in st.session_state:
    st.session_state.historial_registros = []

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .stApp { background-color: #F2F4F7; color: #101828; }
    #MainMenu, header, footer { visibility: hidden !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 820px !important; }

    .app-card {
        background: #FFFFFF;
        border-radius: 28px;
        padding: 2.2rem 2rem;
        box-shadow: 0 15px 30px rgba(0, 0, 0, 0.04);
        border: 1px solid #EAECF0;
        margin-bottom: 1.5rem;
    }

    .app-header h1 { color: #101828 !important; font-size: 1.45rem !important; font-weight: 700 !important; margin: 0 !important; }
    .app-subtitle { color: #667085; font-size: 0.88rem; margin-bottom: 1.5rem; }

    [data-testid="stWidgetLabel"] p { color: #101828 !important; font-weight: 700 !important; font-size: 0.88rem !important; }

    [data-testid="stFileUploadDropzone"] {
        background-color: #FFFFFF !important;
        border: 2px dashed #CBD5E1 !important;
        border-radius: 18px !important;
        padding: 1.2rem !important;
    }

    [data-testid="stFileUploadDropzone"] div, [data-testid="stFileUploadDropzone"] span,
    [data-testid="stFileUploadDropzone"] small, [data-testid="stFileUploadDropzone"] p { color: #334155 !important; }

    [data-testid="stFileUploadDropzone"] button {
        background-color: #101828 !important; color: #FFFFFF !important;
        border-radius: 10px !important; font-weight: 600 !important; border: none !important;
    }

    .stButton > button {
        background-color: #101828 !important; color: #FFFFFF !important;
        border-radius: 100px !important; border: none !important;
        padding: 0.8rem 1.5rem !important; font-size: 0.95rem !important;
        font-weight: 600 !important; width: 100% !important;
        box-shadow: 0 8px 16px rgba(16, 24, 40, 0.1) !important;
        margin-top: 1rem;
    }

    .stButton > button:hover { background-color: #FF8117 !important; }

    .status-badge-success {
        background-color: #F0FDF4; border: 1px solid #DCFCE7;
        border-radius: 16px; padding: 1rem 1.2rem; margin-top: 1rem; color: #166534; font-size: 0.88rem;
    }

    .status-badge-warning {
        background-color: #FFFAEB; border: 1px solid #FEF0C7;
        border-radius: 16px; padding: 1rem 1.2rem; margin-top: 1rem; color: #B45309; font-size: 0.88rem;
    }

    .copy-box-title {
        font-size: 0.85rem; font-weight: 700; color: #101828;
        text-transform: uppercase; letter-spacing: 0.04em; margin-top: 1.2rem; margin-bottom: 0.2rem;
    }
    .copy-box-desc {
        font-size: 0.82rem; color: #667085; margin-bottom: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# Lectura de Claves (Nube / Local)
# -------------------------------------------------------------
try:
    LISTA_API_KEYS = st.secrets["API_KEYS"]
except Exception:
    LISTA_API_KEYS = [
        "TU_API_KEY_CUENTA_1",
        "TU_API_KEY_CUENTA_2"
    ]

class ValidacionYPlanilla(BaseModel):
    nombre_coincide: bool
    cedula_coincide: bool
    chasis_coincide: bool
    detalle_validacion: str
    nombres: Optional[str]
    cedula: Optional[str]
    n_motor: Optional[str]
    n_chasis: Optional[str]
    modelo: Optional[str]
    placa: Optional[str]
    marca: Optional[str]
    linea: Optional[str]
    cilindraje: Optional[str]
    valor_soat: Optional[str]
    auxiliar: Optional[str]
    direccion: Optional[str]
    celular: Optional[str]
    correo: Optional[str]
    ciudad: Optional[str]
    tipo_de_venta: Optional[str]

def procesar_con_gemini(partes_pdf, prompt):
    modelos = ["gemini-3.6-flash", "gemini-2.5-pro"]
    ultimo_error = ""

    for key in LISTA_API_KEYS:
        key_limpia = str(key).strip()
        if not key_limpia or key_limpia.startswith("TU_API_KEY"):
            continue

        client = genai.Client(api_key=key_limpia)
        for model in modelos:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=partes_pdf + [prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ValidacionYPlanilla,
                    ),
                )
                return response
            except Exception as e:
                ultimo_error = str(e)
                continue

    raise Exception(f"No se pudo procesar con ninguna clave. Error: {ultimo_error}")

# -------------------------------------------------------------
# Vista Principal
# -------------------------------------------------------------
st.markdown("""
    <div class="app-card">
        <div class="app-header">
            <h1>Validador de Documentos</h1>
        </div>
        <div class="app-subtitle">Suba los 3 archivos PDF (Cédula, Manifiesto y Factura en cualquier orden).</div>
""", unsafe_allow_html=True)

archivos_subidos = st.file_uploader(
    "Selecciona o arrastra los 3 archivos PDF", 
    type=["pdf"], 
    accept_multiple_files=True
)

if st.button("Procesar y Generar Fila"):
    if not archivos_subidos or len(archivos_subidos) != 3:
        st.warning("Debes seleccionar exactamente los 3 archivos PDF (Cédula, Manifiesto y Factura).")
    else:
        with st.spinner("Analizando y comparando los 3 documentos..."):
            try:
                partes_pdf = [
                    types.Part.from_bytes(data=f.read(), mime_type="application/pdf")
                    for f in archivos_subidos
                ]

                prompt = """
                Analiza los 3 archivos PDF adjuntos (Cédula de ciudadanía, Manifiesto de aduana y Factura electrónica):
                1. Identifica qué archivo corresponde a cada documento.
                2. Verifica si el NOMBRE del cliente coincide entre la cédula y la factura (marca nombre_coincide=True/False).
                3. Verifica si la CÉDULA coincide entre la cédula física y la factura (marca cedula_coincide=True/False).
                4. Verifica si el número de CHASIS/VIN coincide entre el manifiesto y la factura (marca chasis_coincide=True/False).
                5. Si alguna comprobación falla, detalla con precisión el descuadre en 'detalle_validacion'.
                6. Extrae los datos exactos para la planilla:
                   nombres (de la cédula), cedula, n_motor, n_chasis, modelo, placa (pon 'AGREGAR'),
                   marca, linea, cilindraje, valor_soat ('0'), auxiliar ('N/A'),
                   direccion, celular, correo, ciudad, tipo_de_venta ('CREDITO' o 'CONTADO').
                """

                response = procesar_con_gemini(partes_pdf, prompt)
                datos = json.loads(response.text)

                orden_columnas = [
                    "nombres", "cedula", "n_motor", "n_chasis", "modelo", "placa", 
                    "marca", "linea", "cilindraje", "valor_soat", "auxiliar", 
                    "direccion", "celular", "correo", "ciudad", "tipo_de_venta"
                ]

                nueva_fila = {col: datos.get(col, "") for col in orden_columnas}

                # Comprobación de las tres reglas
                es_valido = datos.get("nombre_coincide") and datos.get("cedula_coincide") and datos.get("chasis_coincide")

                if es_valido:
                    st.session_state.historial_registros.append(nueva_fila)
                    st.markdown("""
                        <div class="status-badge-success">
                            <b>Verificación Correcta:</b> Nombre, cédula y chasis coinciden en los 3 documentos. Fila agregada.
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    detalle = datos.get("detalle_validacion", "Inconsistencia detectada en los documentos.")
                    st.markdown(f"""
                        <div class="status-badge-warning">
                            <b>Descuadre Detectado:</b> {detalle}<br>
                            <i>Atención: Este registro NO se agregó al área de copiado.</i>
                        </div>
                    """, unsafe_allow_html=True)

            except Exception as err:
                st.error(f"Error: {err}")

# -------------------------------------------------------------
# ÁREA DE COPIADO
# -------------------------------------------------------------
if st.session_state.historial_registros:
    st.markdown("---")
    st.markdown('<div class="copy-box-title">Registros acumulados para Excel</div>', unsafe_allow_html=True)
    st.markdown('<div class="copy-box-desc">Haz clic en el icono de copiar (arriba a la derecha de la caja negra) y presiona Ctrl+V en tu Excel:</div>', unsafe_allow_html=True)

    orden_columnas = [
        "nombres", "cedula", "n_motor", "n_chasis", "modelo", "placa", 
        "marca", "linea", "cilindraje", "valor_soat", "auxiliar", 
        "direccion", "celular", "correo", "ciudad", "tipo_de_venta"
    ]

    lineas_tsv = []
    for reg in st.session_state.historial_registros:
        linea = "\t".join([str(reg.get(col, "")) for col in orden_columnas])
        lineas_tsv.append(linea)

    texto_copiable_acumulado = "\n".join(lineas_tsv)
    st.code(texto_copiable_acumulado, language="text")

    if st.button("Limpiar Lista"):
        st.session_state.historial_registros = []
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)