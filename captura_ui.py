import streamlit as st
from database import get_db_connection

def obtener_sesiones_activas_empresa(empresa_id: int):
    """Obtiene únicamente las sesiones de la empresa actual que se encuentren abiertas."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT sesion_id, almacen_id, observaciones 
                FROM sesiones_inventario 
                WHERE empresa_id = %s 
                  AND (UPPER(estado) IN ('ABIERTA', 'EN_PROCESO', 'ACTIVA') OR estado IS NULL)
                ORDER BY sesion_id DESC;
            """
            cursor.execute(sql, (empresa_id,))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al obtener sesiones: {e}")
        return []
    finally:
        conn.close()

def obtener_zonas_por_sesion(sesion_id: int):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = "SELECT zona_id, codigo_zona, nombre_zona FROM zonas_inventario WHERE sesion_id = %s ORDER BY codigo_zona ASC;"
            cursor.execute(sql, (sesion_id,))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al obtener zonas: {e}")
        return []
    finally:
        conn.close()

def buscar_producto_empresa(codigo_barras: str, empresa_id: int):
    """Busca el artículo exclusivamente en el catálogo asignado al cliente."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cursor:
            sql = "SELECT codigo_barras, descripcion FROM catalogo_local WHERE codigo_barras = %s AND empresa_id = %s LIMIT 1;"
            cursor.execute(sql, (codigo_barras.strip(), empresa_id))
            return cursor.fetchone()
    except Exception as e:
        st.error(f"Error al consultar el catálogo: {e}")
        return None
    finally:
        conn.close()

def guardar_lectura_escaneo(sesion_id: int, zona_id: int, codigo_barras: str, descripcion: str, cantidad: float, usuario_id: int):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO lecturas_inventario (sesion_id, zona_id, codigo_barras, descripcion, cantidad, usuario_id)
                VALUES (%s, %s, %s, %s, %s, %s);
            """
            cursor.execute(sql, (sesion_id, zona_id, codigo_barras, descripcion, cantidad, usuario_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al guardar lectura: {e}")
        return False
    finally:
        conn.close()

def render_modulo_captura_inventario():
    user_info = st.session_state.get("user_info", {})
    empresa_id = user_info.get("empresa_id")
    usuario_id = user_info.get("id")

    st.title("📲 Captura de Conteo por Escáner / Código de Barras")

    sesiones = obtener_sesiones_activas_empresa(empresa_id)
    if not sesiones:
        st.warning("⚠️ No existen sesiones de inventario activas para su empresa.")
        return

    c1, c2 = st.columns(2)
    with c1:
        mapa_s = {f"Sesión #{s['sesion_id']} (Almacén #{s['almacen_id']})": s['sesion_id'] for s in sesiones}
        sesion_sel = st.selectbox("1. Seleccionar Sesión:", list(mapa_s.keys()))
        sesion_id = mapa_s[sesion_sel]

    zonas = obtener_zonas_por_sesion(sesion_id)
    if not zonas:
        st.warning("⚠️ La sesión seleccionada no cuenta con zonas registradas.")
        return

    with c2:
        mapa_z = {f"📍 {z['codigo_zona']} - {z['nombre_zona']}": z['zona_id'] for z in zonas}
        zona_sel = st.selectbox("2. Seleccionar Zona / Pasillo:", list(mapa_z.keys()))
        zona_id = mapa_z[zona_sel]

    st.markdown("---")

    with st.form("form_captura_codigo", clear_on_submit=True):
        col_barras, col_cant = st.columns([3, 1])
        with col_barras:
            codigo = st.text_input("Código de Barras / Clave del Producto:", key="input_barcode")
        with col_cant:
            cantidad = st.number_input("Cantidad:", min_value=0.01, value=1.0, step=1.0)

        submitted = st.form_submit_button("⚡ Registrar Lectura", type="primary", use_container_width=True)

        if submitted and codigo.strip():
            producto = buscar_producto_empresa(codigo.strip(), empresa_id)
            if producto:
                desc = producto["descripcion"]
            else:
                desc = "PRODUCTO NO ENCONTRADO EN CATÁLOGO"
                st.warning("⚠️ El código ingresado no pertenece al catálogo de su empresa. Se registrará como un ítem fuera de catálogo.")

            if guardar_lectura_escaneo(sesion_id, zona_id, codigo.strip(), desc, cantidad, usuario_id):
                st.toast(f"✅ Registrado: {codigo.strip()} x {cantidad}", icon="📦")