import streamlit as st
from database import get_db_connection

# ==========================================
# FUNCIONES DE BASE DE DATOS
# ==========================================

def registrar_lectura_con_nombre(sesion_id, zona_id, codigo_barras, usuario_id):
    """
    Busca el nombre en catálogo y registra +1 automáticamente.
    """
    conn = get_db_connection()
    if not conn:
        return False, "Sin conexión a la base de datos.", None
    try:
        with conn.cursor() as cursor:
            # 1. Buscar descripción en el catálogo local
            sql_buscar = "SELECT descripcion FROM catalogo_local WHERE codigo_barras = %s LIMIT 1;"
            cursor.execute(sql_buscar, (codigo_barras,))
            resultado = cursor.fetchone()

            if resultado and resultado.get("descripcion"):
                descripcion = resultado["descripcion"]
            else:
                descripcion = "⚠️ PRODUCTO NO REGISTRADO EN CATÁLOGO"

            # 2. Insertar +1 unidad directamente
            sql_insert = """
                INSERT INTO lecturas_inventario 
                    (sesion_id, zona_id, codigo_barras, descripcion, cantidad, usuario_id)
                VALUES (%s, %s, %s, %s, 1.00, %s);
            """
            cursor.execute(sql_insert, (sesion_id, zona_id, codigo_barras, descripcion, usuario_id))
            
        conn.commit()
        return True, f"[{codigo_barras}] — {descripcion}", descripcion
    except Exception as e:
        return False, f"Error al registrar lectura: {e}", None
    finally:
        conn.close()


def obtener_acumulado_zona(sesion_id, zona_id):
    """
    Obtiene los productos contados en la zona ordenados del más reciente al más antiguo.
    """
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    codigo_barras,
                    MAX(descripcion) AS descripcion,
                    SUM(cantidad) AS total_acumulado,
                    COUNT(*) AS conteo_disparos
                FROM lecturas_inventario
                WHERE sesion_id = %s AND zona_id = %s
                GROUP BY codigo_barras
                ORDER BY MAX(lectura_id) DESC;
            """
            cursor.execute(sql, (sesion_id, zona_id))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al obtener acumulados: {e}")
        return []
    finally:
        conn.close()


def obtener_sesiones_activas():
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT sesion_id, almacen_id, estado, observaciones 
                FROM sesiones_inventario 
                WHERE UPPER(estado) IN ('ABIERTA', 'EN_PROCESO', 'ACTIVA')
                   OR estado IS NULL 
                   OR TRIM(estado) = ''
                ORDER BY sesion_id DESC;
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            for r in rows:
                if "almacen_id" not in r or not r["almacen_id"]:
                    r["almacen_id"] = 1
            return rows
    except Exception as e:
        st.error(f"Error al cargar sesiones: {e}")
        return []
    finally:
        conn.close()


def obtener_zonas_por_sesion(sesion_id):
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


# ==========================================
# INTERFAZ DE CAPTURA AUTOMÁTICA
# ==========================================

def render_modulo_captura_ciega():
    st.title("⚡ Escaneo Automático (+1 por Disparo)")
    st.caption("Dispara la pistola al código de barras. El registro se procesa automáticamente sin dar clics.")

    # 1. SELECCIÓN DE SESIÓN Y ZONA
    sesiones = obtener_sesiones_activas()
    if not sesiones:
        st.warning("⚠️ No hay auditorías ABIERTAS.")
        return

    col_ses, col_zon = st.columns(2)
    with col_ses:
        mapa_sesiones = {
            f"Sesión #{s['sesion_id']} - Almacén #{s['almacen_id']}": s['sesion_id'] 
            for s in sesiones
        }
        sesion_sel = st.selectbox("1. Auditoría Activa:", list(mapa_sesiones.keys()))
        sesion_id_activa = mapa_sesiones[sesion_sel]

    zonas = obtener_zonas_por_sesion(sesion_id_activa)
    if not zonas:
        st.warning(f"⚠️ La sesión #{sesion_id_activa} no tiene zonas asignadas.")
        return

    with col_zon:
        mapa_zonas = {
            f"📍 {z['codigo_zona']} - {z['nombre_zona']}": z['zona_id'] 
            for z in zonas
        }
        zona_sel = st.selectbox("2. Zona / Ubicación:", list(mapa_zonas.keys()))
        zona_id_activa = mapa_zonas[zona_sel]

    st.markdown("---")

    user_info = st.session_state.get("user_info", {})
    user_id = user_info.get("usuario_id", 1)

    # 2. CAMPO DE ENTRADA AUTOMÁTICO
    # clear_on_submit=True vacía el texto inmediatamente tras procesar el ENTER de la pistola
    with st.form("form_escaneo_auto", clear_on_submit=True):
        codigo_escaneado = st.text_input(
            "📷 Campo de Lectura Directa (Asegúrate de tener el foco aquí):",
            key="input_codigo_auto",
            placeholder="Dispara la pistola aquí...",
            help="Al escanear, el lector envía ENTER automáticamente y registra +1 unidad."
        )
        # Ocultamos visualmente el botón o lo dejamos como respaldo sin que sea necesario pulsar
        submit_scan = st.form_submit_button("Registrar Lectura", use_container_width=True)

    # 3. PROCESAMIENTO AUTOMÁTICO
    if submit_scan and codigo_escaneado.strip():
        clave = codigo_escaneado.strip()
        exito, msj, desc = registrar_lectura_con_nombre(sesion_id_activa, zona_id_activa, clave, user_id)
        
        if exito:
            st.toast(f"✅ +1 Registrado: {msj}", icon="📦")
        else:
            st.error(msj)
        st.rerun()

    st.markdown("---")

    # 4. RESUMEN EN TIEMPO REAL
    st.subheader("📋 Productos Contados en esta Ubicación")
    acumulados = obtener_acumulado_zona(sesion_id_activa, zona_id_activa)

    if not acumulados:
        st.info("Aún no hay lecturas registradas en esta ubicación.")
    else:
        total_piezas_zona = sum([float(a.get("total_acumulado", 0)) for a in acumulados])
        total_codigos = len(acumulados)

        m1, m2 = st.columns(2)
        m1.metric("📦 Total Piezas Registradas", f"{total_piezas_zona:,.0f} pzs")
        m2.metric("🏷️ SKUs Distintos", f"{total_codigos}")

        st.caption("Últimos escaneos realizados:")
        
        for item in acumulados:
            c_barras = item.get("codigo_barras", "S/C")
            nombre = item.get("descripcion", "Sin Descripción")
            tot = float(item.get("total_acumulado", 0))
            disparos = item.get("conteo_disparos", 0)

            if "NO REGISTRADO" in nombre:
                st.write(f"⚠️ **{c_barras}** — *{nombre}* | **Acumulado:** `{tot:,.0f}` pzs ({disparos} disparos)")
            else:
                st.write(f"🔹 **{c_barras}** — **{nombre}** | **Acumulado:** `{tot:,.0f}` pzs ({disparos} disparos)")