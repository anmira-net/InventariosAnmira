import streamlit as st
import pandas as pd
from database import get_db_connection

# ==========================================
# CONSULTAS DE MONITOREO Y MÉTRICAS
# ==========================================

def obtener_resumen_sesion(sesion_id):
    """Obtiene métricas generales de piezas y zonas para la sesión activa."""
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn.cursor() as cursor:
            # Métricas de lectura
            sql_lecturas = """
                SELECT 
                    COUNT(*) AS total_lecturas,
                    COALESCE(SUM(cantidad), 0) AS total_piezas,
                    COUNT(DISTINCT codigo_barras) AS productos_distintos
                FROM lecturas_inventario
                WHERE sesion_id = %s;
            """
            cursor.execute(sql_lecturas, (sesion_id,))
            res_m = cursor.fetchone() or {}

            # Métricas de zonas
            sql_zonas = """
                SELECT 
                    COUNT(*) AS total_zonas,
                    COUNT(CASE WHEN estado = 'COMPLETADO' THEN 1 END) AS zonas_completadas
                FROM zonas_inventario
                WHERE sesion_id = %s;
            """
            cursor.execute(sql_zonas, (sesion_id,))
            res_z = cursor.fetchone() or {}

            return {**res_m, **res_z}
    except Exception as e:
        st.error(f"Error al obtener métricas: {e}")
        return {}
    finally:
        conn.close()

def obtener_avance_por_zona(sesion_id):
    """Devuelve el desglose de piezas contadas por cada zona registrada."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    z.codigo_zona,
                    z.nombre_zona,
                    z.estado,
                    COALESCE(SUM(l.cantidad), 0) AS piezas_contadas,
                    COUNT(l.lectura_id) AS total_escaneos
                FROM zonas_inventario z
                LEFT JOIN lecturas_inventario l ON z.zona_id = l.zona_id
                WHERE z.sesion_id = %s
                GROUP BY z.zona_id, z.codigo_zona, z.nombre_zona, z.estado
                ORDER BY z.codigo_zona ASC;
            """
            cursor.execute(sql, (sesion_id,))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al obtener avance por zona: {e}")
        return []
    finally:
        conn.close()

def obtener_top_productos(sesion_id, limit=10):
    """Recupera los productos con mayor volumen contado."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    codigo_barras,
                    descripcion,
                    SUM(cantidad) AS total_contado,
                    COUNT(*) AS num_escaneos
                FROM lecturas_inventario
                WHERE sesion_id = %s
                GROUP BY codigo_barras, descripcion
                ORDER BY total_contado DESC
                LIMIT %s;
            """
            cursor.execute(sql, (sesion_id, limit))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al obtener top productos: {e}")
        return []
    finally:
        conn.close()

# ==========================================
# INTERFAZ PRINCIPAL DE MONITOREO
# ==========================================

def render_modulo_monitoreo():
    st.title("📊 Monitoreo de Inventario en Tiempo Real")

    # 1. SELECTOR DE AUDITORÍA ACTIVA
    conn = get_db_connection()
    if not conn:
        st.error("Sin conexión a la base de datos.")
        return
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT sesion_id, estado FROM sesiones_inventario ORDER BY sesion_id DESC;")
            sesiones = cursor.fetchall()
    finally:
        conn.close()

    if not sesiones:
        st.info("No hay sesiones de inventario para monitorear.")
        return

    mapa_s = {f"Auditoría #{s['sesion_id']} ({s.get('estado', 'ABIERTA')})": s['sesion_id'] for s in sesiones}
    
    c_sel, c_ref = st.columns([3, 1])
    with c_sel:
        sesion_label = st.selectbox("Selecciona la Auditoría:", list(mapa_s.keys()))
        sesion_id = mapa_s[sesion_label]
    with c_ref:
        st.write("")
        st.write("")
        if st.button("🔄 Actualizar Datos", use_container_width=True):
            st.rerun()

    st.markdown("---")

    # 2. TARJETAS DE MÉTRICAS CLAVE (KPIs)
    resumen = obtener_resumen_sesion(sesion_id)
    
    tot_piezas = float(resumen.get("total_piezas", 0))
    tot_escaneos = resumen.get("total_lecturas", 0)
    prod_unicos = resumen.get("productos_distintos", 0)
    tot_zonas = resumen.get("total_zonas", 0)
    zonas_comp = resumen.get("zonas_completadas", 0)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("📦 Piezas Contadas", f"{tot_piezas:,.2f}")
    kpi2.metric("🏷️ Productos Únicos", f"{prod_unicos:,}")
    kpi3.metric("📲 Escaneos Totales", f"{tot_escaneos:,}")
    kpi4.metric("🗺️ Cobertura de Zonas", f"{zonas_comp} / {tot_zonas}")

    st.markdown("---")

    # 3. TABLAS Y DESGLOSE EN TIEMPO REAL
    col_izq, col_der = st.columns([1.2, 1])

    with col_izq:
        st.subheader("📍 Avance por Zona / Pasillo")
        zonas_data = obtener_avance_por_zona(sesion_id)
        
        if not zonas_data:
            st.info("No hay zonas registradas para esta auditoría.")
        else:
            df_zonas = pd.DataFrame(zonas_data)
            df_zonas.rename(columns={
                "codigo_zona": "Código",
                "nombre_zona": "Descripción",
                "estado": "Estado",
                "piezas_contadas": "Piezas",
                "total_escaneos": "Escaneos"
            }, inplace=True)
            
            st.dataframe(
                df_zonas, 
                use_container_width=True, 
                hide_index=True
            )

    with col_der:
        st.subheader("🔥 Top 10 Productos Más Contados")
        top_data = obtener_top_productos(sesion_id, limit=10)
        
        if not top_data:
            st.info("Aún no se registran conteos en esta auditoría.")
        else:
            df_top = pd.DataFrame(top_data)
            df_top.rename(columns={
                "codigo_barras": "Código",
                "descripcion": "Producto",
                "total_contado": "Total Piezas",
                "num_escaneos": "Lecturas"
            }, inplace=True)
            
            st.dataframe(
                df_top, 
                use_container_width=True, 
                hide_index=True
            )