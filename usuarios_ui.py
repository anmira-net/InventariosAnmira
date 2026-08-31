import streamlit as st
from auth import hash_password
from database import get_db_connection

# ==========================================
# FUNCIONES AUXILIARES DE CONSULTA
# ==========================================

def obtener_roles():
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT rol_id, nombre FROM roles ORDER BY rol_id ASC")
            res = cursor.fetchall()
            return {r["nombre"]: r["rol_id"] for r in res}
    finally:
        conn.close()

def obtener_usuarios():
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT u.usuario_id, u.nombre_completo, u.usuario, u.correo, u.activo, u.rol_id, r.nombre AS rol_nombre
                FROM usuarios u
                INNER JOIN roles r ON u.rol_id = r.rol_id
                ORDER BY u.usuario_id DESC
            """
            cursor.execute(sql)
            return cursor.fetchall()
    finally:
        conn.close()

# ==========================================
# CONSULTAS DE ALMACENES ADAPTADAS A TU BD
# ==========================================

def obtener_almacenes_totales():
    """Obtiene todos los almacenes usando los nombres exactos de tus columnas."""
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn.cursor() as cursor:
            # Usamos nombre_almacen de tu DDL
            sql = "SELECT almacen_id, nombre_almacen FROM almacenes ORDER BY nombre_almacen ASC"
            cursor.execute(sql)
            res = cursor.fetchall()
            # Retorna {"Nombre del Almacén": almacen_id}
            return {r["nombre_almacen"]: r["almacen_id"] for r in res}
    except Exception as e:
        st.error(f"Error al cargar almacenes: {e}")
        return {}
    finally:
        conn.close()

def obtener_almacenes_de_usuario(usuario_id):
    """Devuelve la lista de IDs de almacenes asignados a un usuario."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT almacen_id FROM usuario_almacenes WHERE usuario_id = %s", (usuario_id,))
            res = cursor.fetchall()
            return [r["almacen_id"] for r in res]
    except Exception as e:
        st.error(f"Error al obtener almacenes del usuario: {e}")
        return []
    finally:
        conn.close()

def guardar_relacion_usuario_almacenes(cursor, usuario_id, lista_almacenes_ids):
    """Sincroniza los permisos en la tabla usuario_almacenes."""
    cursor.execute("DELETE FROM usuario_almacenes WHERE usuario_id = %s", (usuario_id,))
    if lista_almacenes_ids:
        sql = "INSERT INTO usuario_almacenes (usuario_id, almacen_id) VALUES (%s, %s)"
        cursor.executemany(sql, [(usuario_id, alm_id) for alm_id in lista_almacenes_ids])

        
# ==========================================
# INTERFAZ GRÁFICA PRINCIPAL (ABC USUARIOS)
# ==========================================

def render_abc_usuarios():
    st.title("👤 Administración (ABC) de Usuarios")

    tab_cat, tab_crear = st.tabs(
        ["📋 Catálogo de Usuarios", "➕ Registrar Nuevo Usuario"]
    )
    roles = obtener_roles()
    roles_nombres = list(roles.keys())

    dict_almacenes = obtener_almacenes_totales()
    almacenes_nombres = list(dict_almacenes.keys())

    # TAB 1: CATÁLOGO Y EDICIÓN
    with tab_cat:
        usuarios = obtener_usuarios()
        st.subheader(f"Usuarios Registrados ({len(usuarios)})")

        for u in usuarios:
            badge = "🟢 Activo" if u["activo"] else "🔴 Inactivo"
            
            ids_asignados = obtener_almacenes_de_usuario(u["usuario_id"])
            nombres_preseleccionados = [
                nombre for nombre, alm_id in dict_almacenes.items() if alm_id in ids_asignados
            ]

            with st.expander(
                f"{u['nombre_completo']} (@{u['usuario']}) — [{u['rol_nombre']}] [{badge}]"
            ):
                with st.form(f"form_edit_{u['usuario_id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        nombre = st.text_input("Nombre Completo", value=u["nombre_completo"], key=f"nom_{u['usuario_id']}")
                        correo = st.text_input("Correo Electrónico", value=u["correo"] or "", key=f"cor_{u['usuario_id']}")
                    with c2:
                        idx_rol = roles_nombres.index(u["rol_nombre"]) if u["rol_nombre"] in roles_nombres else 0
                        rol_sel = st.selectbox("Rol", roles_nombres, index=idx_rol, key=f"rol_{u['usuario_id']}")
                        activo = st.checkbox("Cuenta Activa", value=bool(u["activo"]), key=f"act_{u['usuario_id']}")

                    new_pass = st.text_input("Nueva Contraseña (dejar vacío si no cambia)", type="password", key=f"pass_{u['usuario_id']}")

                    almacenes_sel_edit = st.multiselect(
                        "🏢 Almacenes Permitidos:",
                        options=almacenes_nombres,
                        default=nombres_preseleccionados,
                        key=f"alm_{u['usuario_id']}"
                    )

                    if st.form_submit_button("💾 Guardar Cambios"):
                        conn = get_db_connection()
                        try:
                            with conn.cursor() as cursor:
                                if new_pass.strip():
                                    pwd_hash = hash_password(new_pass.strip())
                                    sql = "UPDATE usuarios SET nombre_completo=%s, correo=%s, rol_id=%s, activo=%s, password_hash=%s WHERE usuario_id=%s"
                                    cursor.execute(sql, (nombre, correo, roles[rol_sel], 1 if activo else 0, pwd_hash, u["usuario_id"]))
                                else:
                                    sql = "UPDATE usuarios SET nombre_completo=%s, correo=%s, rol_id=%s, activo=%s WHERE usuario_id=%s"
                                    cursor.execute(sql, (nombre, correo, roles[rol_sel], 1 if activo else 0, u["usuario_id"]))
                                
                                ids_almacenes_nuevos = [dict_almacenes[nom] for nom in almacenes_sel_edit]
                                guardar_relacion_usuario_almacenes(cursor, u["usuario_id"], ids_almacenes_nuevos)

                                conn.commit()
                            st.success("¡Usuario y permisos actualizados!")
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error al actualizar: {e}")
                        finally:
                            conn.close()

    # TAB 2: CREACIÓN DE USUARIO
    with tab_crear:
        st.subheader("➕ Crear Usuario")
        with st.form("form_crear_usuario", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                nom = st.text_input("Nombre Completo:")
                usr = st.text_input("Usuario (Login):")
                cor = st.text_input("Correo Electrónico:")
            with col_b:
                pwd = st.text_input("Contraseña:", type="password")
                rol = st.selectbox("Rol:", roles_nombres)

            almacenes_sel_crear = st.multiselect("🏢 Asignar Almacenes Permitidos:", options=almacenes_nombres)

            if st.form_submit_button("🚀 Registrar Usuario", type="primary"):
                if not nom or not usr or not pwd:
                    st.warning("Nombre, usuario y contraseña son obligatorios.")
                else:
                    pwd_h = hash_password(pwd)
                    conn = get_db_connection()
                    try:
                        with conn.cursor() as cursor:
                            sql = "INSERT INTO usuarios (rol_id, nombre_completo, usuario, password_hash, correo, activo) VALUES (%s, %s, %s, %s, %s, 1)"
                            cursor.execute(sql, (roles[rol], nom, usr, pwd_h, cor))
                            new_id = cursor.lastrowid
                            
                            ids_almacenes_crear = [dict_almacenes[nom] for nom in almacenes_sel_crear]
                            guardar_relacion_usuario_almacenes(cursor, new_id, ids_almacenes_crear)

                        conn.commit()
                        st.success(f"¡Usuario @{usr} registrado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error registrando usuario: {e}")
                    finally:
                        conn.close()