import io
import pandas as pd
import streamlit as st
from database import get_db_connection

# ==========================================
# OBTENCIÓN DE DATOS (CATÁLOGO COMPLETO)
# ==========================================

def obtener_comparativa_completa(sesion_id):
    """
    Realiza un LEFT JOIN tolerante a nombres de columna para traer
    TODOS los artículos del catálogo local (contados y no contados).
    """
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            # 1. Identificar dinámicamente la columna de stock en catalogo_local
            cursor.execute("SHOW COLUMNS FROM catalogo_local;")
            columnas = [row['Field'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
            
            col_stock = "0"
            for col in ["existencia", "stock", "stock_teorico", "existencias", "cantidad", "cant_inv"]:
                if col in columnas:
                    col_stock = f"COALESCE(c.{col}, 0)"
                    break

            # 2. Consulta comparativa dinámica con LEFT JOIN
            sql = f"""
                SELECT 
                    c.codigo_barras,
                    c.descripcion,
                    COALESCE(SUM(l.cantidad), 0) AS conteo_fisico,
                    {col_stock} AS stock_teorico,
                    (COALESCE(SUM(l.cantidad), 0) - {col_stock}) AS diferencia,
                    CASE 
                        WHEN SUM(l.cantidad) IS NULL OR SUM(l.cantidad) = 0 THEN 'NO CONTADO'
                        ELSE 'CONTADO'
                    END AS estado_conteo
                FROM catalogo_local c
                LEFT JOIN lecturas_inventario l 
                       ON c.codigo_barras = l.codigo_barras 
                      AND l.sesion_id = %s
                GROUP BY c.codigo_barras, c.descripcion, {col_stock}
                ORDER BY c.descripcion ASC;
            """
            cursor.execute(sql, (sesion_id,))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al obtener comparativa: {e}")
        return []
    finally:
        conn.close()
        

# ==========================================
# GENERADOR DE EXCEL CON ESTILOS
# ==========================================

def generar_excel_comparativa(df):
    """
    Genera un archivo Excel con colores en las celdas para los artículos no contados.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Comparativa')
        workbook = writer.book
        worksheet = writer.sheets['Comparativa']

        # Importar herramientas de formato openpyxl
        from openpyxl.styles import PatternFill, Font

        # Relleno amarillo claro para filas no contadas
        fill_no_contado = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
        font_no_contado = Font(color="7F6000", bold=True)

        # Recorrer filas del DataFrame (openpyxl es base-1, fila 1 es encabezado)
        for row_idx, row_data in enumerate(df.itertuples(), start=2):
            if row_data.estado_conteo == 'NO CONTADO':
                for col_idx in range(1, len(df.columns) + 1):
                    cell = worksheet.cell(row=row_idx, column=col_idx)
                    cell.fill = fill_no_contado
                    if df.columns[col_idx - 1] in ['conteo_fisico', 'estado_conteo']:
                        cell.font = font_no_contado

        # Auto-ajustar ancho de columnas
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output.seek(0)
    return output


# ==========================================
# INTERFAZ STREAMLIT
# ==========================================

def render_modulo_comparativa():
    st.title("📊 Reporte de Comparativa de Inventario")
    st.caption("Visualiza todos los artículos del catálogo. Los productos sin conteo físico aparecen resaltados.")

    # 1. Selección de Sesión (usar función existente o query directa)
    conn = get_db_connection()
    if not conn:
        st.error("Sin conexión a la base de datos.")
        return
    
    with conn.cursor() as cursor:
        cursor.execute("SELECT sesion_id, almacen_id FROM sesiones_inventario ORDER BY sesion_id DESC;")
        sesiones = cursor.fetchall()
    conn.close()

    if not sesiones:
        st.warning("No hay sesiones de inventario.")
        return

    mapa_ses = {f"Sesión #{s['sesion_id']} (Almacén #{s['almacen_id']})": s['sesion_id'] for s in sesiones}
    sesion_sel = st.selectbox("Seleccionar Auditoría/Sesión:", list(mapa_ses.keys()))
    sesion_id = mapa_ses[sesion_sel]

    # 2. Cargar Datos
    datos = obtener_comparativa_completa(sesion_id)
    if not datos:
        st.info("No se encontraron registros.")
        return

    df = pd.DataFrame(datos)

    # 3. Métricas Rápidas
    total_skus = len(df)
    contados = len(df[df['estado_conteo'] == 'CONTADO'])
    no_contados = len(df[df['estado_conteo'] == 'NO CONTADO'])

    m1, m2, m3 = st.columns(3)
    m1.metric("🏷️ SKUs Totales", f"{total_skus}")
    m2.metric("✅ Contados", f"{contados}")
    m3.metric("⚠️ No Contados", f"{no_contados}", delta_color="inverse")

    st.markdown("---")

    # 4. Función de Estilo en Pantalla para Streamlit
    def resaltar_filas_no_contadas(row):
        if row['estado_conteo'] == 'NO CONTADO':
            return ['background-color: #FFF2CC; color: #7F6000; font-weight: bold;'] * len(row)
        return [''] * len(row)

    # Renombrar columnas para la vista
    df_display = df.rename(columns={
        'codigo_barras': 'Código de Barras',
        'descripcion': 'Descripción',
        'conteo_fisico': 'Conteo Físico',
        'stock_teorico': 'Stock Teórico',
        'diferencia': 'Diferencia',
        'estado_conteo': 'Estado'
    })

    # Mostrar en pantalla con formato condicional
    st.dataframe(
        df_display.style.apply(
            lambda row: ['background-color: #FFF2CC; color: #7F6000;' if row['Estado'] == 'NO CONTADO' else '' for _ in row],
            axis=1
        ),
        use_container_width=True,
        height=450
    )

    # 5. Botón de Exportación a Excel con colores
    excel_file = generar_excel_comparativa(df)
    
    st.download_button(
        label="📥 Exportar Reporte a Excel (con resaltado)",
        data=excel_file,
        file_name=f"Comparativa_Sesion_{sesion_id}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )