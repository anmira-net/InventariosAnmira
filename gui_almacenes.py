import streamlit as st
import pandas as pd
from almacenes import crear_almacen_db, obtener_todos_almacenes

def render_gestion_almacenes():
    st.title("🏢 Gestión de Almacenes")
    
    tab_lista, tab_crear = st.tabs(["📋 Almacenes Registrados", "➕ Crear Nuevo Almacén"])
    
    with tab_lista:
        almacenes = obtener_todos_almacenes()
        if almacenes:
            df_alm = pd.DataFrame(almacenes)
            st.dataframe(df_alm, use_container_width=True)
        else:
            st.info("No hay almacenes registrados.")

    with tab_crear:
        with st.form("form_crear_almacen"):
            codigo = st.text_input("Código del Almacén (ej. ALM-01):")
            nombre = st.text_input("Nombre del Almacén:")
            descripcion = st.text_area("Descripción u Observaciones:")
            
            btn_guardar = st.form_submit_button("Guardar Almacén", type="primary")
            
            if btn_guardar:
                if not codigo or not nombre:
                    st.error("El código y el nombre son obligatorios.")
                else:
                    exito, msj = crear_almacen_db(nombre, codigo, descripcion)
                    if exito:
                        st.success(msj)
                        st.rerun()
                    else:
                        st.error(msj)