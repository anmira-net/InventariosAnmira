import streamlit as st
import pandas as pd
from database import get_db_connection

# ==========================================
# FUNCIONES AUXILIARES Y DE ALMACENES
# ==========================================

def obtener_almacenes_permitidos():
    """Obtiene únicamente los almacenes permitidos para el usuario activo en sesión."""
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
    """Obtiene las sesiones activas asociadas únicamente a los almacenes del usuario."""
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
                if "almacen_id" not in r or not r["almacen_id"]:
                    r["almacen_id"] = 1
            return rows
    except Exception as e:
        st.error(f"Error al cargar sesiones: {e}")
        return []
    finally:
        conn.close()


def obtener_zonas_por_sesion(sesion_id):
    """Obtiene las zonas asociadas a una sesión."""
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


def obtener_matriz_conteo(sesion_id, zona_id, almacen_id):
    """
    Obtiene los artículos del catálogo local pertenecientes AL ALMACÉN ESPECÍFICO 
    y cruza las lecturas ya registradas en la zona.
    """
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
                WHERE c.almacen_id = %s
                GROUP BY c.codigo_barras, c.descripcion, c.linea
                ORDER BY c.linea ASC, c.descripcion ASC;
            """
            cursor.execute(sql, (zona_id, sesion_id, almacen_id))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al cargar matriz de conteo del almacén: {e}")
        return []
    finally:
        conn.close()


def guardar_conteo_masivo(sesion_id, zona_id, df_modificado, usuario_id):
    """
    Actualiza los conteos de la zona con los valores editados manualmente en la tabla.
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            # 1. Limpiar registros previos de esta zona en la sesión activa
            sql_clean = "DELETE FROM lecturas_inventario WHERE sesion_id = %s AND zona_id = %s;"
            cursor.execute(sql_clean, (sesion_id, zona_id))

            # 2. Reinsertar los productos cuya cantidad contada sea mayor a 0
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
        st.error(f"Error al guardar los conteos: {e}")
        return False
    finally:
        conn.close()


# ==========================================
# INTERFAZ TIPO HOJA DE CÁLCULO
# ==========================================

def render_modulo_captura_excel():
    st.title("📑 Captura de Inventario (Hoja estilo Excel)")

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

    # 2. SELECCIÓN DE AUDITORÍA Y ZONA
    col_s, col_z = st.columns(2)
    with col_s:
        id_a_nombre = {v: k for k, v in dict_almacenes.items()}
        mapa_s = {
            f"Sesión #{s['sesion_id']} - {id_a_nombre.get(s['almacen_id'], f'Almacén #{s['almacen_id']}')} ({s.get('observaciones', 'Activa')})": s
            for s in sesiones
        }
        sesion_sel = st.selectbox("1. Auditoría Activa:", list(mapa_s.keys()))
        sesion_activa = mapa_s[sesion_sel]
        sesion_id = sesion_activa['sesion_id']
        almacen_id_activo = sesion_activa['almacen_id']

    zonas = obtener_zonas_por_sesion(sesion_id)
    if not zonas:
        st.warning(f"⚠️ La sesión #{sesion_id} no tiene zonas asignadas. Registra pasillos/estantes primero.")
        return

    with col_z:
        mapa_z = {f"📍 {z['codigo_zona']} - {z['nombre_zona']}": z['zona_id'] for z in zonas}
        zona_sel = st.selectbox("2. Zona / Pasillo a Capturar:", list(mapa_z.keys()))
        zona_id = mapa_z[zona_sel]

    st.markdown("---")

    user_info = st.session_state.get("user_info", {})
    user_id = user_info.get("usuario_id", 1)

    # 3. CARGA Y FILTRADO DE DATOS (RESTRINGIDO AL ALMACÉN ACTIVO)
    datos = obtener_matriz_conteo(sesion_id, zona_id, almacen_id_activo)
    if not datos:
        st.info(f"No hay productos cargados en el catálogo local para el almacén seleccionado.")
        return

    df_original = pd.DataFrame(datos)
    df_original["cantidad_contada"] = df_original["cantidad_contada"].astype(float)

    # BUSCADOR Y FILTROS TIPO EXCEL
    st.subheader("🔍 Filtros de Búsqueda Rápida")
    
    col_busq, col_linea, col_solo_contados = st.columns([2, 1.5, 1])
    
    with col_busq:
        filtro_texto = st.text_input(
            "Filtrar por Clave / Código o Descripción:", 
            placeholder="Escriba texto para filtrar..."
        )
        
    with col_linea:
        lineas_unicas = ["TODAS LAS LÍNEAS"] + sorted(list(df_original["linea"].dropna().unique()))
        linea_sel = st.selectbox("Filtrar por Línea:", lineas_unicas)

    with col_solo_contados:
        st.write("")
        st.write("")
        solo_contados = st.checkbox("Ver solo contados (> 0)")

    # Aplicar filtros dinámicos al DataFrame
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

    # 4. HOJA DE CÁLCULO EDITABLE (st.data_editor)
    st.markdown("### ✏️ Hoja de Captura")
    st.caption("Usa las flechas del teclado o ENTER para desplazarte rápidamente entre filas de la columna **Cantidad Contada**.")

    df_edited = st.data_editor(
        df_filtrado,
        column_config={
            "codigo_barras": st.column_config.TextColumn("Código / Clave", disabled=True),
            "descripcion": st.column_config.TextColumn("Descripción del Producto", disabled=True),
            "linea": st.column_config.TextColumn("Línea / Categoría", disabled=True),
            "cantidad_contada": st.column_config.NumberColumn(
                "Cantidad Contada",
                help="Ingresa el valor total contado",
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

    # 5. GUARDADO MASIVO
    c_save, c_info = st.columns([1, 2])
    with c_save:
        if st.button("💾 Guardar Cambios de la Zona", type="primary", use_container_width=True):
            # Preservar registros globales aunque haya filtros de vista activos
            df_original.set_index("codigo_barras", inplace=True)
            df_edited_idx = df_edited.set_index("codigo_barras")
            
            df_original.update(df_edited_idx)
            df_final = df_original.reset_index()

            if guardar_conteo_masivo(sesion_id, zona_id, df_final, user_id):
                st.balloons()
                st.toast("✅ Conteos guardados correctamente", icon="💾")
                st.rerun()

    with c_info:
        total_pzs = df_edited["cantidad_contada"].sum()
        total_items = (df_edited["cantidad_contada"] > 0).sum()
        st.metric("Total Piezas en Vista Actual", f"{total_pzs:,.2f}", f"{total_items} prod. capturados")