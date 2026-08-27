import streamlit as st
from auth import hash_password
from database import get_db_connection


def obtener_roles():
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT rol_id, nombre FROM roles ORDER BY rol_id ASC"
            )
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


def render_abc_usuarios():
    st.title("👤 Administración (ABC) de Usuarios")

    tab_cat, tab_crear = st.tabs(
        ["📋 Catálogo de Usuarios", "➕ Registrar Nuevo Usuario"]
    )
    roles = obtener_roles()
    roles_nombres = list(roles.keys())

    # TAB 1: CATÁLOGO Y EDICIÓN
    with tab_cat:
        usuarios = obtener_usuarios()
        st.subheader(f"Usuarios Registrados ({len(usuarios)})")

        for u in usuarios:
            badge = "🟢 Activo" if u["activo"] else "🔴 Inactivo"
            with st.expander(
                f"{u['nombre_completo']} (@{u['usuario']}) — [{u['rol_nombre']}] [{badge}]"
            ):
                with st.form(f"form_edit_{u['usuario_id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        nombre = st.text_input(
                            "Nombre Completo",
                            value=u["nombre_completo"],
                            key=f"nom_{u['usuario_id']}",
                        )
                        correo = st.text_input(
                            "Correo Electrónico",
                            value=u["correo"] or "",
                            key=f"cor_{u['usuario_id']}",
                        )
                    with c2:
                        idx_rol = (
                            roles_nombres.index(u["rol_nombre"])
                            if u["rol_nombre"] in roles_nombres
                            else 0
                        )
                        rol_sel = st.selectbox(
                            "Rol",
                            roles_nombres,
                            index=idx_rol,
                            key=f"rol_{u['usuario_id']}",
                        )
                        activo = st.checkbox(
                            "Cuenta Activa",
                            value=bool(u["activo"]),
                            key=f"act_{u['usuario_id']}",
                        )

                    new_pass = st.text_input(
                        "Nueva Contraseña (dejar vacío si no cambia)",
                        type="password",
                        key=f"pass_{u['usuario_id']}",
                    )

                    if st.form_submit_button("💾 Guardar Cambios"):
                        conn = get_db_connection()
                        with conn.cursor() as cursor:
                            if new_pass.strip():
                                pwd_hash = hash_password(new_pass.strip())
                                sql = """
                                    UPDATE usuarios 
                                    SET nombre_completo=%s, correo=%s, rol_id=%s, activo=%s, password_hash=%s
                                    WHERE usuario_id=%s
                                """
                                cursor.execute(
                                    sql,
                                    (
                                        nombre,
                                        correo,
                                        roles[rol_sel],
                                        1 if activo else 0,
                                        pwd_hash,
                                        u["usuario_id"],
                                    ),
                                )
                            else:
                                sql = """
                                    UPDATE usuarios 
                                    SET nombre_completo=%s, correo=%s, rol_id=%s, activo=%s
                                    WHERE usuario_id=%s
                                """
                                cursor.execute(
                                    sql,
                                    (
                                        nombre,
                                        correo,
                                        roles[rol_sel],
                                        1 if activo else 0,
                                        u["usuario_id"],
                                    ),
                                )
                            conn.commit()
                            conn.close()
                        st.success("¡Usuario actualizado!")
                        st.rerun()

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

            if st.form_submit_button("🚀 Registrar Usuario", type="primary"):
                if not nom or not usr or not pwd:
                    st.warning("Nombre, usuario y contraseña son obligatorios.")
                else:
                    pwd_h = hash_password(pwd)
                    conn = get_db_connection()
                    try:
                        with conn.cursor() as cursor:
                            sql = """
                                INSERT INTO usuarios (rol_id, nombre_completo, usuario, password_hash, correo, activo)
                                VALUES (%s, %s, %s, %s, %s, 1)
                            """
                            cursor.execute(
                                sql, (roles[rol], nom, usr, pwd_h, cor)
                            )
                        conn.commit()
                        st.success(f"¡Usuario @{usr} registrado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error registrando usuario: {e}")
                    finally:
                        conn.close()