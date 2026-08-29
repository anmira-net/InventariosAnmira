import zipfile
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
from database import get_db_connection
from database import inicializar_sistema_inventario

# Mapeo de almacenes por defecto[cite: 2]
almacenes_map = {
    "INDEPENDENCIA": 1,
    "DIAGONAL": 2,
    "PINTUMEX": 3
}

# ==========================================
# CONSULTAS DE CATÁLOGO EXISTENTE
# ==========================================

def obtener_catalogo_existente_lineas():
    """Recupera los datos guardados en la tabla catalogo_local incluyendo la columna línea."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    articulo_id_microsip AS id,
                    codigo_barras AS `Código / Clave`,
                    descripcion AS `Descripción`,
                    linea AS `Línea / Categoría`,
                    almacen_id AS `Almacén ID`,
                    existencia AS `Existencia`,
                    costo AS `Costo Unitario`,
                    (existencia * costo) AS `Valor Total`,
                    ultima_sincronizacion AS `Última Sincro`
                FROM catalogo_local
                ORDER BY linea ASC, descripcion ASC;
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Error al consultar el catálogo local: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# ==========================================
# PROCESAMIENTO DE EXCEL POR LÍNEAS (XML)
# ==========================================



def procesar_excel_microsip_lineas(uploaded_file, nombre_almacen_seleccionado):
    """Parsea las estructuras XML del XLSX agrupando productos por su Línea correspondiente."""
    try:
        almacen_id_seleccionado = almacenes_map.get(nombre_almacen_seleccionado, 1)

        with zipfile.ZipFile(uploaded_file) as z:
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for si in tree.findall('.//main:si', ns):
                    t_elems = si.findall('.//main:t', ns)
                    text = "".join([t.text for t in t_elems if t.text])
                    shared_strings.append(text)
            
            sheet_tree = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
            ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            
            datos = []
            current_linea = "GENERAL"
            
            for row in sheet_tree.findall('.//main:row', ns):
                row_cells = {}
                for c in row.findall('./main:c', ns):
                    r_ref = c.attrib.get('r', '')
                    col_letter = "".join([char for char in r_ref if char.isalpha()])
                    cell_type = c.attrib.get('t')
                    v_elem = c.find('./main:v', ns)
                    val = v_elem.text if v_elem is not None else None
                    
                    if cell_type == 's' and val is not None:
                        val = shared_strings[int(val)]
                    
                    row_cells[col_letter] = val
                
                if not row_cells:
                    continue
                
                col_a = str(row_cells.get('A', '')).strip() if row_cells.get('A') else ""
                
                # Detectar cambio de Línea
                if col_a.startswith('Línea:'):
                    current_linea = col_a.replace('Línea:', '').strip()
                    continue

                # Omitir encabezados de reporte y totales
                encabezados_omitir = [
                    "ALBERCAS LAGUNA S.A. DE C.V.", 
                    "Existencia y valor del inventario", 
                    "INDEPENDENCIA",
                    "Valuación: Costo promedio",
                    "Artículo", 
                    "Total de la línea", 
                    "Total general",
                    ""
                ]

                if col_a in encabezados_omitir or col_a.startswith("Al ") or col_a.startswith("Valuación:"):
                    continue
                
                clave = col_a
                
                # -----------------------------------------------------------
                # CORRECCIÓN DE COLUMNAS SEGÚN EL REPORTE
                # -----------------------------------------------------------
                # La descripción viene en la Columna C
                descripcion = str(row_cells.get('C', '')).strip() if row_cells.get('C') else "SIN DESCRIPCIÓN"
                
                # La existencia viene en la Columna L
                try:
                    existencia = float(row_cells.get('L')) if row_cells.get('L') is not None else 0.0
                except (ValueError, TypeError):
                    existencia = 0.0
                    
                # El costo viene en la Columna N
                try:
                    costo = float(row_cells.get('N')) if row_cells.get('N') is not None else 0.0
                except (ValueError, TypeError):
                    costo = 0.0

                if clave:
                    datos.append({
                        "Importar": True,
                        "articulo_id_microsip": 0,
                        "codigo_barras": clave,
                        "descripcion": descripcion, # Ahora sí captura el texto correcto
                        "linea": current_linea,
                        "almacen_id": almacen_id_seleccionado,
                        "nombre_almacen": nombre_almacen_seleccionado,
                        "existencia": existencia,
                        "costo": costo
                    })

        return pd.DataFrame(datos)
    except Exception as e:
        st.error(f"Error al procesar el archivo por líneas: {e}")
        return None

def guardar_en_db_lineas(df):
    """Inserta o actualiza únicamente los renglones seleccionados incluyendo la columna línea."""
    conn = get_db_connection()
    if not conn:
        st.error("No hay conexión con la base de datos.")
        return 0
        
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO catalogo_local 
                    (articulo_id_microsip, codigo_barras, descripcion, linea, almacen_id, existencia, costo)
                VALUES 
                    (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    descripcion = VALUES(descripcion),
                    linea = VALUES(linea),
                    existencia = VALUES(existencia),
                    costo = VALUES(costo),
                    ultima_sincronizacion = CURRENT_TIMESTAMP;
            """
            
            valores = [
                (
                    int(row['articulo_id_microsip']),
                    str(row['codigo_barras']),
                    str(row['descripcion']),
                    str(row['linea']),
                    int(row['almacen_id']),
                    float(row['existencia']),
                    float(row['costo'])
                )
                for _, row in df.iterrows()
            ]
            
            cursor.executemany(sql, valores)
            
        conn.commit()
        return len(df)
    except Exception as e:
        st.error(f"Error al guardar en MySQL: {e}")
        return 0
    finally:
        conn.close()

# ==========================================
# INTERFAZ GRÁFICA PRINCIPAL
# ==========================================

def render_importador_inventario_lineas():
    st.title("📥 Importación de Inventario por Líneas")
    
    if "mensaje_exito" in st.session_state:
        st.balloons()
        st.success(st.session_state["mensaje_exito"])
        del st.session_state["mensaje_exito"]

    tab_actual, tab_importar, tab_inicializar = st.tabs([
        "📦 Catálogo Actual en BD", 
        "⬆️ Cargar y Filtrar Excel por Líneas", 
        "⚠️ Inicializar Catálogo"
    ])

    # ----------------------------------------------------
    # TAB 1: VER CATÁLOGO ACTUAL REGISTRADO
    # ----------------------------------------------------
    with tab_actual:
        df_existente = obtener_catalogo_existente_lineas()

        if df_existente.empty:
            st.info("ℹ️ La tabla `catalogo_local` se encuentra vacía.")
        else:
            total_articulos = len(df_existente)
            total_piezas = df_existente["Existencia"].sum()
            valor_total = df_existente["Valor Total"].sum()
            total_lineas = df_existente["Línea / Categoría"].nunique() if "Línea / Categoría" in df_existente else 0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📦 Productos Registrados", f"{total_articulos:,}")
            m2.metric("🏷️ Líneas / Categorías", f"{total_lineas}")
            m3.metric("🔢 Total de Piezas", f"{total_piezas:,.2f}")
            m4.metric("💰 Valor Total Teórico", f"${valor_total:,.2f}")

            st.markdown("---")
            st.subheader("🔍 Buscador de Productos en BD")
            busqueda = st.text_input("Filtrar por código, descripción o línea:", placeholder="Escribe aquí para buscar...")

            if busqueda.strip():
                df_filtrado = df_existente[
                    df_existente["Código / Clave"].astype(str).str.contains(busqueda, case=False, na=False) |
                    df_existente["Descripción"].astype(str).str.contains(busqueda, case=False, na=False) |
                    df_existente["Línea / Categoría"].astype(str).str.contains(busqueda, case=False, na=False)
                ]
            else:
                df_filtrado = df_existente

            st.dataframe(
                df_filtrado,
                use_container_width=True,
                column_config={
                    "Costo Unitario": st.column_config.NumberColumn(format="$%.2f"),
                    "Valor Total": st.column_config.NumberColumn(format="$%.2f"),
                    "Existencia": st.column_config.NumberColumn(format="%.2f"),
                }
            )

    # ----------------------------------------------------
    # TAB 2: SUBIR, FILTRAR RENGLONES E IMPORTAR EXCEL
    # ----------------------------------------------------
    with tab_importar:
        st.markdown("Selecciona el almacén de destino y carga el archivo Excel agrupado por **Líneas**.")
        
        col_select, col_file = st.columns([1, 2])
        
        with col_select:
            almacen_destino = st.selectbox(
                "📍 Selecciona el almacén de destino:",
                options=list(almacenes_map.keys()),
                index=0,
                key="sb_almacen_lineas"
            )

        with col_file:
            uploaded_file = st.file_uploader("Seleccionar archivo Excel por Líneas (.xlsx)", type=["xlsx", "xls"], key="up_lineas")
        
        if uploaded_file is not None:
            cache_key = f"{uploaded_file.name}_{almacen_destino}_lineas"
            
            if "df_raw_loaded_lineas" not in st.session_state or st.session_state.get("file_cache_key_lineas") != cache_key:
                with st.spinner("Procesando datos y clasificando líneas del archivo..."):
                    st.session_state["df_raw_loaded_lineas"] = procesar_excel_microsip_lineas(uploaded_file, almacen_destino)
                    st.session_state["file_cache_key_lineas"] = cache_key

            df_raw = st.session_state.get("df_raw_loaded_lineas")

            if df_raw is not None and not df_raw.empty:
                st.subheader(f"🛠️ Editar y Seleccionar Renglones por Líneas (Almacén: {almacen_destino})")
                st.caption("Marca o desmarca la casilla **'Importar'**, o edita directamente los campos si es necesario.")

                df_edited = st.data_editor(
                    df_raw,
                    use_container_width=True,
                    num_rows="dynamic",
                    key=f"editor_{cache_key}",
                    column_config={
                        "Importar": st.column_config.CheckboxColumn(
                            "Importar",
                            help="Marca para incluir este artículo en la base de datos",
                            default=True
                        ),
                        "codigo_barras": st.column_config.TextColumn("Código / Clave"),
                        "descripcion": st.column_config.TextColumn("Descripción"),
                        "linea": st.column_config.TextColumn("Línea / Categoría"),
                        "nombre_almacen": st.column_config.TextColumn("Almacén Destino"),
                        "existencia": st.column_config.NumberColumn("Existencia", format="%.2f"),
                        "costo": st.column_config.NumberColumn("Costo Unitario", format="$%.2f"),
                        "articulo_id_microsip": None,
                        "almacen_id": None
                    },
                    hide_index=True
                )

                df_a_guardar = df_edited[df_edited["Importar"] == True].copy()

                st.markdown("---")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Filas Seleccionadas", f"{len(df_a_guardar):,} de {len(df_edited):,}")
                
                if not df_a_guardar.empty:
                    lineas_contadas = df_a_guardar['linea'].nunique()
                    unidades = df_a_guardar['existencia'].sum()
                    costo_total = (df_a_guardar['existencia'] * df_a_guardar['costo']).sum()
                    
                    c2.metric("Líneas Seleccionadas", f"{lineas_contadas}")
                    c3.metric("Unidades a Importar", f"{unidades:,.2f}")
                    c4.metric("Valor Total Seleccionado", f"${costo_total:,.2f}")
                    
                    if st.button(f"🚀 Importar por Líneas a {almacen_destino}", type="primary", use_container_width=True):
                        with st.spinner("Guardando registros en MySQL..."):
                            total = guardar_en_db_lineas(df_a_guardar)
                            if total > 0:
                                st.session_state["mensaje_exito"] = f"¡Éxito! Se registraron {total} productos pertenecientes a {lineas_contadas} líneas en el almacén {almacen_destino}."
                                if "df_raw_loaded_lineas" in st.session_state:
                                    del st.session_state["df_raw_loaded_lineas"]
                                st.rerun()
                else:
                    st.warning("⚠️ No hay ningún renglón marcado con la casilla 'Importar'. Marca al menos uno para continuar.")
            else:
                st.warning("No se encontraron registros válidos en el archivo proporcionado.")

    # ----------------------------------------------------
    # TAB 3: INICIALIZAR / VACIAR CATÁLOGO LOCAL
    # ----------------------------------------------------
    with tab_inicializar:
        st.subheader("⚠️ Inicialización / Cero Absoluto del Sistema")
        st.warning("Esta acción eliminará permanentemente:")
        st.markdown("""
        * 📦 Todo el **Catálogo Local** de artículos cargados.
        * 📋 Todas las **Sesiones / Auditorías** abiertas o cerradas.
        * 🗺️ Todas las **Zonas y Pasillos** creados.
        * 🔢 Todos los **Conteos y Lecturas** realizados.
            
        *Nota: Tu catálogo de **Usuarios** NO se borrará.*
        """)
        
        st.markdown("---")
            
        confirmar_chk = st.checkbox("Entiendo que esta acción es irreversible y borrará la información de conteo y productos.", key="chk_init_lineas")
            
        if confirmar_chk:
            if st.button("🔥 Reiniciar Sistema por Completo", type="primary", key="btn_init_lineas"):
                if inicializar_sistema_inventario():
                    st.success("¡Sistema inicializado con éxito! El catálogo, sesiones, zonas y conteos han sido borrados. Puedes comenzar la carga desde cero.")
                    st.rerun()