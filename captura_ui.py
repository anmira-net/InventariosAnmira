import streamlit as st
import pandas as pd
from database import get_db_connection

# ==========================================
# FUNCIONES DE CONSULTA A BASE DE DATOS
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
    """Recupera sesiones activas de los almacenes permitidos para el usuario."""
    if not almacenes_ids:
        return []
        
    conn = get_db_connection()
    if not conn:
        return []
    try:
        format_strings = ','.join(['%s'] * len(almacenes_ids))
        with conn.cursor() as cursor:
            # Trae sesiones abiertas o activas de los almacenes permitidos
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


def buscar_producto_catalogo(termino, almacen_id):
    """Busca en catalogo_local por código de barras o descripción restringido al almacén."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            term_clean = termino.strip()
            
            # 1. Búsqueda exacta por Código de Barras (Clave) en el almacén de la sesión
            sql_exacta = """
                SELECT * FROM catalogo_local 
                WHERE codigo_barras = %s AND almacen_id = %s
                LIMIT 1;
            """
            cursor.execute(sql_exacta, (term_clean, almacen_id))
            exacto = cursor.fetchone()
            if exacto:
                return [exacto]

            # 2. Búsqueda parcial por Código de Barras o Descripción dentro del almacén
            sql_like = """
                SELECT * FROM catalogo_local 
                WHERE almacen_id = %s AND (codigo_barras LIKE %s OR descripcion LIKE %s)
                LIMIT 15;
            """
            term_like = f"%{term_clean}%"
            cursor.execute(sql_like, (almacen_id, term_like, term_like))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error en catálogo: {e}")
        return []
    finally:
        conn.close()


def registrar_conteo(sesion_id, zona_id, articulo_id_microsip, codigo_barras, descripcion, cantidad, usuario_id):
    """Guarda la lectura en lecturas_inventario vinculando al usuario actual."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO lecturas_inventario 
                    (sesion_id, zona_id, codigo_barras, descripcion, cantidad, usuario_id)
                VALUES (%s, %s, %s, %s, %s, %s);
            """
            cursor.execute(sql, (
                sesion_id, 
                zona_id, 
                codigo_barras, 
                descripcion, 
                cantidad,
                usuario_id
            ))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al guardar producto ({codigo_barras}): {e}")
        return False
    finally:
        conn.close()


def obtener_lecturas_zona(zona_id):
    """Recupera los conteos de la zona."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM lecturas_inventario WHERE zona_id = %s ORDER BY lectura_id DESC;"
            cursor.execute(sql, (zona_id,))
            rows = cursor.fetchall()

            for r in rows:
                if "codigo_barras" not in r or not r["codigo_barras"]:
                    r["codigo_barras"] = "S/C"
                if "descripcion" not in r or not r["descripcion"]:
                    r["descripcion"] = "Artículo Registrado"
                if "cantidad" not in r:
                    r["cantidad"] = 0.0
            return rows
    except Exception as e:
        st.error(f"Error al obtener lecturas: {e}")
        return []
    finally:
        conn.close()


def eliminar_lectura(lectura_id):
    """Cancela o borra un escaneo previo."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            sql = "DELETE FROM lecturas_inventario WHERE lectura_id = %s;"
            cursor.execute(sql, (lectura_id,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al eliminar lectura: {e}")
        return False
    finally:
        conn.close()


# ==========================================
# INTERFAZ OPTIMIZADA PARA CAPTURA (TABLETA / PISTOLA LÁSER)
# ==========================================

def render_modulo_captura_inventario():
    st.title("⚡ Captura Dinámica de Inventario")

    # 1. OBTENER ALMACENES PERMITIDOS Y FILTRAR SESIONES
    dict_almacenes = obtener_almacenes_permitidos()
    if not dict_almacenes:
        st.warning("⚠️ No tienes almacenes permitidos asignados a tu usuario.")
        return

    almacenes_ids = list(dict_almacenes.values())
    sesiones = obtener_sesiones_activas(almacenes_ids)

    if not sesiones:
        st.warning("⚠️ No hay auditorías ABIERTAS en tus almacenes autorizados.")
        return

    col_ses, col_zon = st.columns(2)
    with col_ses:
        # Muestra el almacén correspondiente a la sesión
        id_a_nombre = {v: k for k, v in dict_almacenes.items()}
        
        mapa_sesiones = {
            f"Sesión #{s['sesion_id']} - {id_a_nombre.get(s['almacen_id'], f'Almacén #{s['almacen_id']}')} ({s.get('observaciones', 'Sin obs')})": s
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
        zona_sel = st.selectbox("2. Zona / Pasillo / Estante:", list(mapa_zonas.keys()))
        zona_id_activa = mapa_zonas[zona_sel]

    st.markdown("---")

    user_info = st.session_state.get("user_info", {})
    user_id = user_info.get("usuario_id", 1)

    if "producto_seleccionado" not in st.session_state:
        st.session_state["producto_seleccionado"] = None

    # -----------------------------------------------------------------
    # ESTADO 1: BÚSQUEDA DEL PRODUCTO (Pistola Láser / Nombre + ENTER)
    # -----------------------------------------------------------------
    if st.session_state["producto_seleccionado"] is None:
        st.subheader("🔍 Paso 1: Escanear o Buscar Producto")
        
        with st.form("form_busqueda_rapida", clear_on_submit=True):
            codigo_escaneado = st.text_input(
                "📷 Código de Barras / Nombre:", 
                key="input_codigo_escaneado",
                placeholder="Escanee clave o escriba nombre y presione ENTER...",
                help="Presione ENTER tras escanear"
            )
            submit_busqueda = st.form_submit_button("🔎 Buscar Producto", use_container_width=True)

        if submit_busqueda and codigo_escaneado.strip():
            termino = codigo_escaneado.strip()
            resultados = buscar_producto_catalogo(termino, almacen_id_activo)

            if not resultados:
                st.error(f"❌ No se encontró ningún producto con: '{termino}' en el almacén activo.")
            elif len(resultados) == 1:
                st.session_state["producto_seleccionado"] = resultados[0]
                st.rerun()
            else:
                st.session_state["scanner_coincidencias"] = resultados

        if "scanner_coincidencias" in st.session_state and st.session_state["scanner_coincidencias"]:
            st.info("💡 Haz clic en el producto que deseas registrar:")
            for idx, prod in enumerate(st.session_state["scanner_coincidencias"]):
                p_barras = prod.get("codigo_barras", "S/C")
                p_desc = prod.get("descripcion", "Artículo")

                col_det, col_acc = st.columns([3, 1])
                with col_det:
                    st.write(f"🔹 **{p_barras}** — {p_desc}")
                with col_acc:
                    if st.button("👉 Seleccionar", key=f"sel_match_{idx}"):
                        st.session_state["producto_seleccionado"] = prod
                        del st.session_state["scanner_coincidencias"]
                        st.rerun()

    # -----------------------------------------------------------------
    # ESTADO 2: CAPTURA ULTRA-RÁPIDA DE CANTIDAD (Cantidad + ENTER)
    # -----------------------------------------------------------------
    else:
        prod = st.session_state["producto_seleccionado"]
        art_microsip = prod.get("articulo_id_microsip", 0)
        c_barras = prod.get("codigo_barras", "S/C")
        desc = prod.get("descripcion", "Artículo")

        st.success(f"📦 **PRODUCTO:** [{c_barras}] — {desc}")

        with st.form("form_captura_cantidad", clear_on_submit=True):
            cant_ingresada = st.number_input(
                "✏️ Paso 2: Ingresa Unidades y presiona ENTER:", 
                min_value=0.01, 
                value=1.0, 
                step=1.0, 
                key="cant_input_fast"
            )
            
            col_save, col_cancel = st.columns([2, 1])
            with col_save:
                submit_guardar = st.form_submit_button("⚡ Registrar y Siguiente (ENTER)", use_container_width=True)
            with col_cancel:
                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)

            if cancelar:
                st.session_state["producto_seleccionado"] = None
                st.rerun()

            if submit_guardar:
                if registrar_conteo(sesion_id_activa, zona_id_activa, art_microsip, c_barras, desc, cant_ingresada, user_id):
                    st.toast(f"✅ Registradas +{cant_ingresada:,.2f} piezas de {desc}", icon="📦")
                    st.session_state["producto_seleccionado"] = None
                    st.rerun()

    st.markdown("---")

    # 3. CONTEO EN TIEMPO REAL
    st.markdown("### 📋 Resumen de Capturas en esta Zona")
    lecturas = obtener_lecturas_zona(zona_id_activa)

    if not lecturas:
        st.info("Aún no hay escaneos registrados en esta zona.")
    else:
        total_piezas = sum([float(l.get("cantidad", 0)) for l in lecturas])
        
        m1, m2 = st.columns(2)
        m1.metric("📦 Piezas Contadas en la Zona", f"{total_piezas:,.2f}")
        m2.metric("🔢 Total Escaneos/Lecturas", f"{len(lecturas)}")

        for idx_l, l in enumerate(lecturas[:10]):
            l_id = l["lectura_id"]
            l_clave = l.get("codigo_barras", "S/C")
            l_desc = l.get("descripcion", "Artículo")
            l_cant = float(l.get("cantidad", 0))

            c_text, c_del = st.columns([5, 1])
            with c_text:
                st.write(f"✔️ **{l_clave}** — {l_desc} | **Cant:** `{l_cant:,.2f}`")
            with c_del:
                if st.button("🗑️", key=f"del_scan_{idx_l}_{l_id}", help="Eliminar escaneo"):
                    if eliminar_lectura(l_id):
                        st.toast("Escaneo eliminado", icon="🗑️")
                        st.rerun()