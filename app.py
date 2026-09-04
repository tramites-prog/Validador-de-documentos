import json
import re
import time
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Optional


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

try:
    LISTA_API_KEYS = st.secrets["API_KEYS"]
except Exception:
    LISTA_API_KEYS = [
        "TU_API_KEY_CUENTA_1",
        "TU_API_KEY_CUENTA_2"
    ]

class ExtraccionDocumentos(BaseModel):
    nombre_cedula: Optional[str]
    cedula_documento: Optional[str]
    nombre_factura: Optional[str]
    cedula_factura: Optional[str]
    chasis_manifiesto: Optional[str]
    motor_manifiesto: Optional[str]
    chasis_factura: Optional[str]
    motor_factura: Optional[str]
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


def normalizar(valor):
    """Limpia espacios y mayúsculas/minúsculas para comparar de forma justa
    (evita falsos negativos por ' Cindy' vs 'Cindy' o 'cindy' vs 'CINDY')."""
    return (valor or "").strip().upper()

def normalizar_texto(valor):
    """Limpia espacios extras y convierte a mayúsculas."""
    if not valor:
        return ""
    return " ".join(valor.strip().upper().split())

def limpiar_documento(valor):
    """Elimina puntos, guiones, espacios y letras para comparar solo números/caracteres clave.
    Sirve para Cédulas, Cédula de Extranjería, TI, Pasaportes o NIT."""
    if not valor:
        return ""
    # Conserva solo letras y números (elimina ., -, espacios)
    return re.sub(r'[^A-Z0-9]', '', valor.upper().strip())


def procesar_con_gemini(partes_archivos, prompt):

    modelos = ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
    ultimo_error = ""

    for key in LISTA_API_KEYS:
        key_limpia = str(key).strip()
        if not key_limpia or key_limpia.startswith("TU_API_KEY"):
            continue

        client = genai.Client(api_key=key_limpia)

        for model in modelos:
            for intento in range(3): 
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=partes_archivos + [prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=ExtraccionDocumentos,
                        ),
                    )
                    return response
                except Exception as e:
                    ultimo_error = str(e)

                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        break  
                    elif "503" in str(e) or "UNAVAILABLE" in str(e):
                        time.sleep(2 * (intento + 1))
                        continue
                    elif "404" in str(e) or "NOT_FOUND" in str(e):
                        break 
                    else:
                        break

    raise Exception(f"No se pudo procesar con ninguna clave. Error: {ultimo_error}")

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
                Analiza exhaustivamente los 2 o 3 archivos adjuntos (Documento de Identificación, Manifiesto de aduana y/o Factura electrónica).
                
                Tu única tarea es EXTRAER exactamente lo que está escrito en cada documento sin juzgar si coinciden entre sí:
                
                1. Del DOCUMENTO DE IDENTIFICACIÓN (Cédula de ciudadanía, Cédula de extranjería, Tarjeta de identidad, Pasaporte o RUT/NIT):
                   - extrae el nombre completo o razón social tal cual aparece (nombre_cedula).
                   - extrae el número de documento tal cual aparece, incluyendo puntos si los tiene (cedula_documento).
                
                2. De la FACTURA ELECTRONICA:
                   - extrae el nombre completo del cliente o razón social (nombre_factura).
                   - extrae el número de cédula/NIT del cliente (cedula_factura).
                   - extrae el número de chasis (campo "CH:") tal cual (chasis_factura).
                   - extrae el número de motor (campo "MT:") tal cual (motor_factura).
                
                3. Del MANIFIESTO DE ADUANA:
                   - extrae el número de Chasis/VIN (SERIAL No. / VIN NO. / No. CHASIS) (chasis_manifiesto).
                   - extrae el número de Motor (MOTOR No.) (motor_manifiesto).
                
                4. EXTRACCIÓN DE DATOS ADICIONALES PARA LA PLANILLA:
                   modelo, placa ('AGREGAR'), marca, linea, cilindraje, valor_soat ('0'), auxiliar ('N/A'),
                   direccion, celular, correo, ciudad, tipo_de_venta ('CREDITO' o 'CONTADO').
                """

                response = procesar_con_gemini(partes_archivos, prompt)
                datos = json.loads(response.text)

            nombre_coincide = normalizar_texto(datos.get("nombre_cedula")) == normalizar_texto(datos.get("nombre_factura"))
            cedula_coincide = limpiar_documento(datos.get("cedula_documento")) == limpiar_documento(datos.get("cedula_factura"))
            chasis_coincide = limpiar_documento(datos.get("chasis_manifiesto")) == limpiar_documento(datos.get("chasis_factura")
            motor_coincide = limpiar_documento(datos.get("motor_manifiesto")) == limpiar_documento(datos.get("motor_factura"))
            
            es_valido = nombre_coincide and cedula_coincide and chasis_coincide and motor_coincide

                orden_columnas = [
                    "nombres", "cedula", "n_motor", "n_chasis", "modelo", "placa",
                    "marca", "linea", "cilindraje", "valor_soat", "auxiliar",
                    "direccion", "celular", "correo", "ciudad", "tipo_de_venta"
                ]

                datos_planilla = {
                    "nombres": datos.get("nombre_cedula", ""),
                    "cedula": datos.get("cedula_documento", ""),
                    "n_motor": datos.get("motor_manifiesto", ""),
                    "n_chasis": datos.get("chasis_manifiesto", ""),
                    "modelo": datos.get("modelo", ""),
                    "placa": datos.get("placa", ""),
                    "marca": datos.get("marca", ""),
                    "linea": datos.get("linea", ""),
                    "cilindraje": datos.get("cilindraje", ""),
                    "valor_soat": datos.get("valor_soat", ""),
                    "auxiliar": datos.get("auxiliar", ""),
                    "direccion": datos.get("direccion", ""),
                    "celular": datos.get("celular", ""),
                    "correo": datos.get("correo", ""),
                    "ciudad": datos.get("ciudad", ""),
                    "tipo_de_venta": datos.get("tipo_de_venta", ""),
                }

                nueva_fila = {col: datos_planilla.get(col, "") for col in orden_columnas}

                if es_valido:
                    st.session_state.historial_registros.append(nueva_fila)
                    st.session_state.uploader_key += 1
                    st.session_state.ultimo_mensaje = {
                        "tipo": "exito",
                        "texto": "<b>Verificación Correcta:</b> Nombre, cédula, chasis y motor coinciden perfectamente. Fila agregada."
                    }
                    st.rerun()
                else:
                    diferencias = []
                    if not nombre_coincide:
                        diferencias.append(
                            f"Nombre: '{datos.get('nombre_cedula')}' (cédula) vs '{datos.get('nombre_factura')}' (factura)"
                        )
                    if not cedula_coincide:
                        diferencias.append(
                            f"Cédula: '{datos.get('cedula_documento')}' (cédula) vs '{datos.get('cedula_factura')}' (factura)"
                        )
                    if not chasis_coincide:
                        diferencias.append(
                            f"Chasis: '{datos.get('chasis_manifiesto')}' (manifiesto) vs '{datos.get('chasis_factura')}' (factura)"
                        )
                    if not motor_coincide:
                        diferencias.append(
                            f"Motor: '{datos.get('motor_manifiesto')}' (manifiesto) vs '{datos.get('motor_factura')}' (factura)"
                        )
                    detalle = " | ".join(diferencias) if diferencias else "Inconsistencia detectada en los documentos."

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
