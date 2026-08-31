import streamlit as st
from database import get_db_connection

# ==========================================
# FUNCIONES DE BASE DE DATOS Y PERMISOS
# ==========================================

def obtener_almacenes_permitidos():
    """Obtiene únicamente los almacenes permitidos para el usuario logueado en la sesión."""
    user_info = st.session_state.get("user_info")
    if not user_info or "usuario_id" not in user_info:
        return {}

    usuario_id = user_info["usuario_id"]
    conn = get_db_connection()
    if not conn:
        return {}

    try:
        with conn.cursor() as cursor:
            if user_info.get("rol") in ["Admin", "Administrador"]:
                sql = "SELECT almacen_id, nombre_almacen FROM almacenes ORDER BY nombre_almacen ASC"
                cursor.execute(sql)
            else:
                sql = """
                    SELECT a.almacen_id, a.nombre_almacen 
                    FROM almacenes a
                    INNER JOIN usuario_almacenes ua ON a.almacen_id = ua.almacen_id
                    WHERE ua.usuario_id = %s
                    ORDER BY a.nombre_almacen ASC
                """
                cursor.execute(sql, (usuario_id,))

            res = cursor.fetchall()
            return {r["nombre_almacen"]: r["almacen_id"] for r in res}
    except Exception as e:
        st.error(f"Error al obtener almacenes permitidos: {e}")
        return {}
    finally:
        conn.close()


def obtener_sesiones_activas(almacenes_ids):
    """Recupera sesiones activas asociadas únicamente a los almacenes del usuario."""
    if not almacenes_ids:
        return []
        
    conn = get_db_connection()
    if not conn:
        return []
    try:
        format_strings = ','.join(['%s'] * len(almacenes_ids))
        with conn.cursor() as cursor:
            sql = f"""
                SELECT sesion_id, almacen_id, estado, observaciones 
                FROM sesiones_inventario 
                WHERE (UPPER(estado) IN ('ABIERTA', 'EN_PROCESO', 'ACTIVA')
                   OR estado IS NULL 
                   OR TRIM(estado) = '')
                   AND almacen_id IN ({format_strings})
                ORDER BY sesion_id DESC;
            """
            cursor.execute(sql, list(almacenes_ids))
            rows = cursor.fetchall()

            for r in rows:
                if not r.get("estado") or str(r.get("estado")).strip() == "":
                    r["estado"] = "ABIERTA"
                if "observaciones" not in r or not r.get("observaciones"):
                    r["observaciones"] = "Sesión Activa"
            return rows
    except Exception as e:
        st.error(f"Error al cargar sesiones: {e}")
        return []
    finally:
        conn.close()


def obtener_zonas_por_sesion(sesion_id):
    """Obtiene las zonas asociadas a la sesión activa."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT zona_id, sesion_id, codigo_zona, nombre_zona, estado 
                FROM zonas_inventario 
                WHERE sesion_id = %s 
                ORDER BY codigo_zona ASC;
            """
            cursor.execute(sql, (sesion_id,))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al cargar zonas: {e}")
        return []
    finally:
        conn.close()


def registrar_lectura_con_nombre(sesion_id, zona_id, almacen_id, codigo_barras, usuario_id):
    """
    Busca la descripción en el catálogo filtrado por almacén y registra +1 automáticamente.
    """
    conn = get_db_connection()
    if not conn:
        return False, "Sin conexión a la base de datos.", None
    try:
        with conn.cursor() as cursor:
            # 1. Buscar descripción en catalogo_local acotado al almacén de la sesión activa
            sql_buscar = """
                SELECT descripcion 
                FROM catalogo_local 
                WHERE codigo_barras = %s AND almacen_id = %s 
                LIMIT 1;
            """
            cursor.execute(sql_buscar, (codigo_barras, almacen_id))
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


# ==========================================
# INTERFAZ DE CAPTURA AUTOMÁTICA (+1 DISPARO)
# ==========================================

def render_modulo_captura_ciega():
    st.title("⚡ Escaneo Automático (+1 por Disparo)")
    st.caption("Dispara la pistola al código de barras. El registro se procesa automáticamente sumando +1 unidad.")

    # 1. OBTENER ALMACENES PERMITIDOS Y SESIONES
    dict_almacenes = obtener_almacenes_permitidos()
    if not dict_almacenes:
        st.warning("⚠️ No tienes almacenes permitidos asignados a tu usuario.")
        return

    almacenes_ids = list(dict_almacenes.values())
    sesiones = obtener_sesiones_activas(almacenes_ids)

    if not sesiones:
        st.warning("⚠️ No hay auditorías ABIERTAS en tus almacenes autorizados.")
        return

    # 2. SELECCIÓN DE SESIÓN Y ZONA
    col_ses, col_zon = st.columns(2)
    with col_ses:
        id_a_nombre = {v: k for k, v in dict_almacenes.items()}
        mapa_sesiones = {
            f"Sesión #{s['sesion_id']} - {id_a_nombre.get(s['almacen_id'], f'Almacén #{s['almacen_id']}')} ({s.get('observaciones', 'Activa')})": s
            for s in sesiones
        }
        sesion_sel_label = st.selectbox("1. Auditoría Activa:", list(mapa_sesiones.keys()))
        sesion_activa = mapa_sesiones[sesion_sel_label]
        sesion_id_activa = sesion_activa['sesion_id']
        almacen_id_activo = sesion_activa['almacen_id']

    zonas = obtener_zonas_por_sesion(sesion_id_activa)
    if not zonas:
        st.warning(f"⚠️ La sesión #{sesion_id_activa} no tiene zonas creadas. Registra zonas antes de capturar.")
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

    # 3. CAMPO DE ENTRADA AUTOMÁTICO (PISTOLA LÁSER / ENTER)
    with st.form("form_escaneo_auto", clear_on_submit=True):
        codigo_escaneado = st.text_input(
            "📷 Campo de Lectura Directa (Asegúrate de tener el foco aquí):",
            key="input_codigo_auto",
            placeholder="Dispara la pistola aquí...",
            help="Al escanear, el lector envía ENTER automáticamente y registra +1 unidad."
        )
        submit_scan = st.form_submit_button("⚡ Registrar Lectura", use_container_width=True)

    # 4. PROCESAMIENTO AUTOMÁTICO
    if submit_scan and codigo_escaneado.strip():
        clave = codigo_escaneado.strip()
        exito, msj, desc = registrar_lectura_con_nombre(
            sesion_id_activa, 
            zona_id_activa, 
            almacen_id_activo, 
            clave, 
            user_id
        )
        
        if exito:
            st.toast(f"✅ +1 Registrado: {msj}", icon="📦")
        else:
            st.error(msj)
        st.rerun()

    st.markdown("---")

    # 5. RESUMEN EN TIEMPO REAL
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