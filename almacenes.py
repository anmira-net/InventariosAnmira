import streamlit as st
from database import get_db_connection


def obtener_almacenes_lista():
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT almacen_id, nombre_almacen, ubicacion FROM almacenes ORDER BY almacen_id DESC"
            )
            return cursor.fetchall()
    finally:
        conn.close()


def render_abc_almacenes():
    st.title("🏢 Administración (ABC) de Almacenes")

    tab_cat, tab_crear = st.tabs(
        ["📋 Catálogo de Almacenes", "➕ Registrar Nuevo Almacén"]
    )

    # TAB 1: CATÁLOGO Y EDICIÓN DE ALMACENES
    with tab_cat:
        almacenes = obtener_almacenes_lista()
        st.subheader(f"Almacenes Registrados ({len(almacenes)})")

        for a in almacenes:
            with st.expander(f"📍 {a['nombre_almacen']} (ID: {a['almacen_id']})"):
                with st.form(f"form_edit_alm_{a['almacen_id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        nombre = st.text_input(
                            "Nombre del Almacén",
                            value=a["nombre_almacen"],
                            key=f"nom_{a['almacen_id']}",
                        )
                    with c2:
                        ubicacion = st.text_input(
                            "Ubicación",
                            value=a["ubicacion"] or "",
                            key=f"ubi_{a['almacen_id']}",
                        )

                    if st.form_submit_button("💾 Guardar Cambios"):
                        conn = get_db_connection()
                        try:
                            with conn.cursor() as cursor:
                                sql = """
                                    UPDATE almacenes 
                                    SET nombre_almacen=%s, ubicacion=%s
                                    WHERE almacen_id=%s
                                """
                                cursor.execute(
                                    sql,
                                    (
                                        nombre.strip(),
                                        ubicacion.strip(),
                                        a["almacen_id"],
                                    ),
                                )
                            conn.commit()
                            st.success("¡Almacén actualizado con éxito!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar almacén: {e}")
                        finally:
                            conn.close()

    # TAB 2: CREACIÓN DE ALMACÉN
    with tab_crear:
        st.subheader("➕ Crear Almacén")
        with st.form("form_crear_almacen", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nom_nuevo = st.text_input("Nombre del Almacén:")
            with col2:
                ubi_nueva = st.text_input("Ubicación:")

            if st.form_submit_button("🚀 Registrar Almacén", type="primary"):
                if not nom_nuevo.strip():
                    st.warning("El nombre del almacén es obligatorio.")
                else:
                    conn = get_db_connection()
                    try:
                        with conn.cursor() as cursor:
                            sql = """
                                INSERT INTO almacenes (nombre_almacen, ubicacion)
                                VALUES (%s, %s)
                            """
                            cursor.execute(
                                sql, (nom_nuevo.strip(), ubi_nueva.strip())
                            )
                        conn.commit()
                        st.success(
                            f"¡Almacén '{nom_nuevo}' registrado exitosamente!"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear almacén: {e}")
                    finally:
                        conn.close()
