import streamlit as st
from auth import autenticar_usuario
from usuarios_ui import render_abc_usuarios
from importador_ui import render_importador_inventario
from captura_ui import render_modulo_captura_inventario
from sesiones_ui import render_modulo_sesiones_zonas
from monitoreo_ui import render_modulo_monitoreo
from reportes_ui import render_modulo_comparativa
from captura_excel_ui import render_modulo_captura_excel
from captura_ciega_ui import render_modulo_captura_ciega
from importar_lineas_ui import render_importador_inventario_lineas

st.set_page_config(page_title="Sistema de Inventarios SaaS", page_icon="📦", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

# Pantalla de Login
if not st.session_state["logged_in"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])

    with c2:
        st.title("🔒 Sistema de Inventarios Multi-Tenant")
        st.subheader("Acceso al Sistema")

        with st.form("login_form"):
            usr = st.text_input("Usuario:")
            pwd = st.text_input("Contraseña:", type="password")

            if st.form_submit_button("Iniciar Sesión", use_container_width=True, type="primary"):
                if usr and pwd:
                    if autenticar_usuario(usr, pwd):
                        st.rerun()
                else:
                    st.warning("Escribe tu usuario y contraseña.")

# Pantalla Principal
else:
    u = st.session_state["user_info"]

    # Menú Lateral Personalizado por Empresa
    st.sidebar.title(f"🏢 {u['nombre_empresa']}")
    st.sidebar.caption(f"👤 **{u['nombre']}** ({u['rol']})")
    st.sidebar.markdown("---")

    opciones = []
    if u["rol"] == "Admin":
        opciones = [
            "Gestión de Usuarios",
            "Importar Inventario",
            "📊Importar Inventario de lineas",
            "📍 Gestión de Sesiones/Zonas",
            "📲 Captura de Conteo",
            "📲 Captura de Conteo formato Excel",
            "📲 Captura de Conteo a Ciegas",
            "📊 Monitoreo de Inventario en Tiempo Real",
            "⚖️ Comparativa: Inventario Teórico vs. Contado",
        ]
    else:
        opciones = ["Captura de Conteo", "📲 Captura de Conteo formato Excel"]

    opcion = st.sidebar.radio("Ir a:", opciones)

    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # Renders
    if opcion == "Gestión de Usuarios":
        render_abc_usuarios()
    elif opcion == "Importar Inventario":
        render_importador_inventario()
    elif opcion == "📊Importar Inventario de lineas":
        render_importador_inventario_lineas()
    elif opcion == "📲 Captura de Conteo":
        render_modulo_captura_inventario()
    elif opcion == "📲 Captura de Conteo formato Excel":
        render_modulo_captura_excel()
    elif opcion == "📲 Captura de Conteo a Ciegas":
        render_modulo_captura_ciega()
    elif opcion == "📍 Gestión de Sesiones/Zonas":
        render_modulo_sesiones_zonas()
    elif opcion == "📊 Monitoreo de Inventario en Tiempo Real":
        render_modulo_monitoreo()
    elif opcion == "⚖️ Comparativa: Inventario Teórico vs. Contado":
        render_modulo_comparativa()