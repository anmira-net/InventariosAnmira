import streamlit as st
import pandas as pd
from database import get_db_connection, obtener_almacenes_empresa

def obtener_sesiones_empresa(empresa_id: int):
    """Consulta las sesiones de inventario pertenecientes exclusivamente a la empresa activa."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT s.sesion_id, s.almacen_id, a.nombre_almacen, s.estado, s.observaciones, s.fecha_inicio
                FROM sesiones_inventario s
                LEFT JOIN almacenes a ON s.almacen_id = a.almacen_id
                WHERE s.empresa_id = %s
                ORDER BY s.sesion_id DESC;
            """
            cursor.execute(sql, (empresa_id,))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al obtener sesiones: {e}")
        return []
    finally:
        conn.close()

def crear_nueva_sesion(empresa_id: int, almacen_id: int, observaciones: str):
    """Inserta una nueva sesión asociando el empresa_id correspondiente."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO sesiones_inventario (empresa_id, almacen_id, estado, observaciones)
                VALUES (%s, %s, 'ABIERTA', %s);
            """
            cursor.execute(sql, (empresa_id, almacen_id, observaciones))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al crear la sesión: {e}")
        return False
    finally:
        conn.close()

def obtener_zonas_sesion(sesion_id: int):
    """Obtiene las zonas registradas para una sesión en específico."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = "SELECT zona_id, codigo_zona, nombre_zona FROM zonas_inventario WHERE sesion_id = %s ORDER BY codigo_zona ASC;"
            cursor.execute(sql, (sesion_id,))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al consultar zonas: {e}")
        return []
    finally:
        conn.close()

def crear_nueva_zona(sesion_id: int, codigo_zona: str, nombre_zona: str):
    """Crea una zona ligada a la sesión seleccionada."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO zonas_inventario (sesion_id, codigo_zona, nombre_zona)
                VALUES (%s, %s, %s);
            """
            cursor.execute(sql, (sesion_id, codigo_zona.strip(), nombre_zona.strip()))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al registrar zona: {e}")
        return False
    finally:
        conn.close()

def render_modulo_sesiones_zonas():
    user_info = st.session_state.get("user_info", {})
    empresa_id = user_info.get("empresa_id")

    st.title("📍 Gestión de Sesiones y Zonas de Conteo")

    tab_sesiones, tab_zonas = st.tabs(["🚀 Sesiones de Inventario", "🗺️ Zonas / Pasillos"])

    # ---------------- TAB 1: SESIONES ----------------
    with tab_sesiones:
        st.subheader("Crear Nueva Sesión de Inventario")
        
        almacenes = obtener_almacenes_empresa(empresa_id)
        if not almacenes:
            st.warning("⚠️ No existen almacenes dados de alta para su empresa.")
            return

        with st.form("form_nueva_sesion"):
            almacen_nombre = st.selectbox("Seleccione el Almacén:", list(almacenes.keys()))
            obs = st.text_input("Observaciones / Notas de la sesión:")
            
            if st.form_submit_button("Aperturar Sesión", type="primary"):
                almacen_id = almacenes[almacen_nombre]
                if crear_nueva_sesion(empresa_id, almacen_id, obs):
                    st.success("¡Sesión creada correctamente!")
                    st.rerun()

        st.markdown("---")
        st.subheader("Sesiones Registradas")
        
        sesiones = obtener_sesiones_empresa(empresa_id)
        if sesiones:
            df_s = pd.DataFrame(sesiones)
            st.dataframe(df_s, use_container_width=True, hide_index=True)
        else:
            st.info("No hay sesiones registradas para esta empresa.")

    # ---------------- TAB 2: ZONAS ----------------
    with tab_zonas:
        st.subheader("Alta de Zonas / Pasillos")
        
        sesiones = obtener_sesiones_empresa(empresa_id)
        if not sesiones:
            st.warning("No hay sesiones activas para gestionar zonas.")
            return

        mapa_sesiones = {f"Sesión #{s['sesion_id']} ({s['nombre_almacen'] or 'Almacén ' + str(s['almacen_id'])})": s['sesion_id'] for s in sesiones}
        sesion_sel = st.selectbox("Seleccione la Sesión de Inventario:", list(mapa_sesiones.keys()))
        sesion_id = mapa_sesiones[sesion_sel]

        with st.form("form_nueva_zona"):
            c1, c2 = st.columns([1, 2])
            with c1:
                codigo_z = st.text_input("Código de Zona (ej. Z1, PASILLO-A):")
            with c2:
                nombre_z = st.text_input("Descripción de la Zona (ej. Estantería Central):")

            if st.form_submit_button("Agregar Zona", type="primary"):
                if codigo_z and nombre_z:
                    if crear_nueva_zona(sesion_id, codigo_z, nombre_z):
                        st.success(f"Zona '{codigo_z}' registrada.")
                        st.rerun()
                else:
                    st.warning("Complete todos los campos de la zona.")

        st.markdown("---")
        zonas = obtener_zonas_sesion(sesion_id)
        if zonas:
            st.dataframe(pd.DataFrame(zonas), use_container_width=True, hide_index=True)
        else:
            st.info("Esta sesión aún no tiene zonas asignadas.")