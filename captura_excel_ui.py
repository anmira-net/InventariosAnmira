import streamlit as st
import pandas as pd
from database import get_db_connection

def obtener_sesiones_activas(empresa_id: int):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT sesion_id, almacen_id, estado, observaciones 
                FROM sesiones_inventario 
                WHERE empresa_id = %s 
                  AND (UPPER(estado) IN ('ABIERTA', 'EN_PROCESO', 'ACTIVA') OR estado IS NULL OR TRIM(estado) = '')
                ORDER BY sesion_id DESC;
            """
            cursor.execute(sql, (empresa_id,))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al cargar sesiones: {e}")
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

def obtener_matriz_conteo(sesion_id: int, zona_id: int, empresa_id: int):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    c.codigo_barras,
                    c.descripcion,
                    COALESCE(c.linea, 'GENERAL') AS linea,
                    COALESCE(SUM(l.cantidad), 0.00) AS cantidad_contada
                FROM catalogo_local c
                LEFT JOIN lecturas_inventario l 
                       ON c.codigo_barras = l.codigo_barras 
                      AND l.zona_id = %s 
                      AND l.sesion_id = %s
                WHERE c.empresa_id = %s
                GROUP BY c.codigo_barras, c.descripcion, c.linea
                ORDER BY c.linea ASC, c.descripcion ASC;
            """
            cursor.execute(sql, (zona_id, sesion_id, empresa_id))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al cargar matriz de conteo: {e}")
        return []
    finally:
        conn.close()

def guardar_conteo_masivo(sesion_id: int, zona_id: int, df_modificado, usuario_id: int):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            sql_clean = "DELETE FROM lecturas_inventario WHERE sesion_id = %s AND zona_id = %s;"
            cursor.execute(sql_clean, (sesion_id, zona_id))

            df_a_guardar = df_modificado[df_modificado["cantidad_contada"] > 0]

            if not df_a_guardar.empty:
                sql_insert = """
                    INSERT INTO lecturas_inventario 
                        (sesion_id, zona_id, codigo_barras, descripcion, cantidad, usuario_id)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """
                registros = [
                    (
                        sesion_id, 
                        zona_id, 
                        row["codigo_barras"], 
                        row["descripcion"], 
                        float(row["cantidad_contada"]), 
                        usuario_id
                    )
                    for _, row in df_a_guardar.iterrows()
                ]
                cursor.executemany(sql_insert, registros)

        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al guardar los conteos masivos: {e}")
        return False
    finally:
        conn.close()

def render_modulo_captura_excel():
    user_info = st.session_state.get("user_info", {})
    empresa_id = user_info.get("empresa_id")
    user_id = user_info.get("id", 1)

    st.title("📑 Captura de Inventario (Hoja estilo Excel)")

    sesiones = obtener_sesiones_activas(empresa_id)
    if not sesiones:
        st.warning("⚠️ No hay auditorías ABIERTAS registradas para tu empresa.")
        return

    col_s, col_z = st.columns(2)
    with col_s:
        mapa_s = {f"Auditoría #{s['sesion_id']} (Almacén #{s['almacen_id']})": s['sesion_id'] for s in sesiones}
        sesion_sel = st.selectbox("1. Auditoría Activa:", list(mapa_s.keys()))
        sesion_id = mapa_s[sesion_sel]

    zonas = obtener_zonas_por_sesion(sesion_id)
    if not zonas:
        st.warning(f"⚠️ La sesión #{sesion_id} no tiene zonas asociadas.")
        return

    with col_z:
        mapa_z = {f"📍 {z['codigo_zona']} - {z['nombre_zona']}": z['zona_id'] for z in zonas}
        zona_sel = st.selectbox("2. Zona / Pasillo a Capturar:", list(mapa_z.keys()))
        zona_id = mapa_z[zona_sel]

    st.markdown("---")

    datos = obtener_matriz_conteo(sesion_id, zona_id, empresa_id)
    if not datos:
        st.info("No hay productos en el catálogo de tu empresa.")
        return

    df_original = pd.DataFrame(datos)
    df_original["cantidad_contada"] = df_original["cantidad_contada"].astype(float)

    st.subheader("🔍 Filtros de Búsqueda Rápida")
    col_busq, col_linea, col_solo_contados = st.columns([2, 1.5, 1])
    
    with col_busq:
        filtro_texto = st.text_input("Filtrar por Clave o Descripción:", placeholder="Escriba texto para filtrar...")
        
    with col_linea:
        lineas_unicas = ["TODAS LAS LÍNEAS"] + sorted(list(df_original["linea"].dropna().unique()))
        linea_sel = st.selectbox("Filtrar por Línea:", lineas_unicas)

    with col_solo_contados:
        st.write("")
        st.write("")
        solo_contados = st.checkbox("Ver solo contados (> 0)")

    df_filtrado = df_original.copy()
    
    if filtro_texto.strip():
        term = filtro_texto.strip().lower()
        df_filtrado = df_filtrado[
            df_filtrado["codigo_barras"].str.lower().str.contains(term, na=False) |
            df_filtrado["descripcion"].str.lower().str.contains(term, na=False)
        ]

    if linea_sel != "TODAS LAS LÍNEAS":
        df_filtrado = df_filtrado[df_filtrado["linea"] == linea_sel]

    if solo_contados:
        df_filtrado = df_filtrado[df_filtrado["cantidad_contada"] > 0]

    st.markdown("### ✏️ Hoja de Captura")
    df_edited = st.data_editor(
        df_filtrado,
        column_config={
            "codigo_barras": st.column_config.TextColumn("Código / Clave", disabled=True),
            "descripcion": st.column_config.TextColumn("Descripción del Producto", disabled=True),
            "linea": st.column_config.TextColumn("Línea / Categoría", disabled=True),
            "cantidad_contada": st.column_config.NumberColumn(
                "Cantidad Contada",
                min_value=0.0,
                step=1.0,
                format="%.2f"
            )
        },
        disabled=["codigo_barras", "descripcion", "linea"],
        hide_index=True,
        use_container_width=True,
        key=f"editor_grid_{sesion_id}_{zona_id}"
    )

    st.markdown("---")

    c_save, c_info = st.columns([1, 2])
    with c_save:
        if st.button("💾 Guardar Cambios de la Zona", type="primary", use_container_width=True):
            df_original.set_index("codigo_barras", inplace=True)
            df_edited_idx = df_edited.set_index("codigo_barras")
            
            df_original.update(df_edited_idx)
            df_final = df_original.reset_index()

            if guardar_conteo_masivo(sesion_id, zona_id, df_final, user_id):
                st.toast("✅ Conteos guardados correctamente", icon="💾")
                st.rerun()

    with c_info:
        total_pzs = df_edited["cantidad_contada"].sum()
        total_items = (df_edited["cantidad_contada"] > 0).sum()
        st.metric("Total Piezas en la Vista Actual", f"{total_pzs:,.2f}", f"{total_items} prod. capturados")