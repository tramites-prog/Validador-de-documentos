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
st.set_page_config(page_title="Validador Vehicular", layout="centered")

if "historial_registros" not in st.session_state:
    st.session_state.historial_registros = []

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

if "ultimo_mensaje" not in st.session_state:
    st.session_state.ultimo_mensaje = None

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

def obtener_mime_type(archivo):
    """Detecta automáticamente el tipo MIME según la extensión."""
    ext = archivo.name.split('.')[-1].lower()
    mapa_mime = {
        'pdf': 'application/pdf',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'heic': 'image/heic'
    }
    return mapa_mime.get(ext, archivo.type or 'application/octet-stream')

def procesar_con_gemini(partes_archivos, prompt):
    # Usamos gemini-2.5-flash que permite hasta 1,500 solicitudes diarias en el Plan Gratuito
    modelos = ["gemini-2.5-flash", "gemini-1.5-flash"]
    ultimo_error = ""

    for key in LISTA_API_KEYS:
        key_limpia = str(key).strip()
        if not key_limpia or key_limpia.startswith("TU_API_KEY"):
            continue

        client = genai.Client(api_key=key_limpia)
        clave_agotada = False

        for model in modelos:
            if clave_agotada:
                break

            for intento in range(2):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=partes_archivos + [prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=ValidacionYPlanilla,
                        ),
                    )
                    return response
                except Exception as e:
                    ultimo_error = str(e)
                    
                    # Si la clave sobrepasó la cuota (429), salta de inmediato a probar la siguiente API Key
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        clave_agotada = True
                        break
                    
                    # Si el servidor de Google está saturado (503), espera 2 segundos
                    elif "503" in str(e) or "UNAVAILABLE" in str(e):
                        time.sleep(2)
                        continue
                    else:
                        break

    raise Exception(f"No se pudo procesar con ninguna clave. Error: {ultimo_error}")
# -------------------------------------------------------------
# Vista Principal
# -------------------------------------------------------------
st.markdown("""
    <div class="app-card">
        <div class="app-header">
            <h1>Validador de Documentos</h1>
        </div>
        <div class="app-subtitle">Suba los 2 o 3 archivos (Cédula, Manifiesto y/o Factura en PDF o Imagen).</div>
""", unsafe_allow_html=True)

archivos_subidos = st.file_uploader(
    "Selecciona o arrastra 2 o 3 archivos (PDF, JPG, PNG, WEBP)", 
    type=["pdf", "jpg", "jpeg", "png", "webp", "heic"], 
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_key}"
)

if st.button("Procesar y Generar Fila"):
    if not archivos_subidos or len(archivos_subidos) not in [2, 3]:
        st.warning("Debes seleccionar exactamente 2 o 3 archivos (Cédula, Manifiesto y/o Factura).")
    else:
        with st.spinner("Analizando y comparando los documentos..."):
            try:
                partes_archivos = [
                    types.Part.from_bytes(
                        data=f.read(), 
                        mime_type=obtener_mime_type(f)
                    )
                    for f in archivos_subidos
                ]

                prompt = """
                Analiza exhaustivamente los archivos adjuntos (pueden ser 2 o 3 archivos en formato PDF o imágenes: Cédula de ciudadanía, Manifiesto de aduana y Factura electrónica):

                REGLAS ESTRICTAS DE VALIDACIÓN:
                1. COMPROBACIÓN DE NOMBRE (nombre_coincide):
                   - Compara el NOMBRE Y APELLIDOS COMPLETOS que figuran en la Cédula/Identificación contra el cliente en la Factura.
                   - Debes verificar letra por letra. Si falta un segundo nombre, si un apellido es distinto (ej. Pérez vs Yepes), o si hay errores ortográficos/tipográficos en cualquier apellido o nombre, marca OBLIGATORIAMENTE nombre_coincide = False.
                   - Solo marca nombre_coincide = True si el nombre y los apellidos coinciden exactamente en ambos documentos.

                2. COMPROBACIÓN DE CÉDULA (cedula_coincide):
                   - Compara el número de documento/cédula en la cédula física vs la factura.
                   - Debe coincidir dígito por dígito. Marca False si hay alguna diferencia.

                3. COMPROBACIÓN DE CHASIS / VIN (chasis_coincide):
                   - Compara el número de chasis/VIN entre el Manifiesto de aduana y la Factura.
                   - Marca False si hay alguna letra o número diferente.

                4. DETALLE DE VALIDACIÓN (detalle_validacion):
                   - Si alguna de las 3 verificaciones es False, debes explicar explícitamente la discrepancia encontrada. Por ejemplo: "El nombre en la cédula es Maria Pérez pero en la factura figura Maria Yepes".

                5. EXTRACCIÓN DE DATOS:
                   - Extrae los datos exactos para la planilla:
                     nombres (usa el nombre completo exacto que aparece en la Cédula), cedula, n_motor, n_chasis, modelo, placa (escribe 'AGREGAR'),
                     marca, linea, cilindraje, valor_soat ('0'), auxiliar ('N/A'),
                     direccion, celular, correo, ciudad, tipo_de_venta ('CREDITO' o 'CONTADO').
                """

                response = procesar_con_gemini(partes_archivos, prompt)
                datos = json.loads(response.text)

                orden_columnas = [
                    "nombres", "cedula", "n_motor", "n_chasis", "modelo", "placa", 
                    "marca", "linea", "cilindraje", "valor_soat", "auxiliar", 
                    "direccion", "celular", "correo", "ciudad", "tipo_de_venta"
                ]

                nueva_fila = {col: datos.get(col, "") for col in orden_columnas}

                # Comprobación
                es_valido = datos.get("nombre_coincide") and datos.get("cedula_coincide") and datos.get("chasis_coincide")

                if es_valido:
                    st.session_state.historial_registros.append(nueva_fila)
                    st.session_state.uploader_key += 1
                    st.session_state.ultimo_mensaje = {
                        "tipo": "exito",
                        "texto": "<b>Verificación Correcta:</b> Nombre, cédula y chasis coinciden perfectamente en los documentos. Fila agregada."
                    }
                    st.rerun()
                else:
                    detalle = datos.get("detalle_validacion", "Inconsistencia detectada en los documentos.")
                    st.session_state.ultimo_mensaje = {
                        "tipo": "advertencia",
                        "texto": f"<b>Descuadre Detectado:</b> {detalle}<br><i>Atención: Este registro NO se agregó al área de copiado.</i>"
                    }

            except Exception as err:
                st.error(f"Error: {err}")

# Mostrar el resultado del procesamiento
if st.session_state.ultimo_mensaje:
    if st.session_state.ultimo_mensaje["tipo"] == "exito":
        st.markdown(f"""
            <div class="status-badge-success">
                {st.session_state.ultimo_mensaje['texto']}
            </div>
        """, unsafe_allow_html=True)
    elif st.session_state.ultimo_mensaje["tipo"] == "advertencia":
        st.markdown(f"""
            <div class="status-badge-warning">
                {st.session_state.ultimo_mensaje['texto']}
            </div>
        """, unsafe_allow_html=True)

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
        st.session_state.ultimo_mensaje = None
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)
