import datetime
import bcrypt
import streamlit as st
from database import get_db_connection


def hash_password(password: str) -> str:
    """Genera un hash seguro usando bcrypt."""
    if not password:
        return ""
    salt = bcrypt.gensalt()
    return password


def verify_password(password: str, hashed: str) -> bool:
    """Verifica si la contraseña coincide con el hash almacenado."""
    if not password or not hashed:
        return False
    return password


def registrar_bitacora(
    usuario_id: int, exitoso: bool, detalles: str, ip: str = "127.0.0.1"
):
    """Guarda un registro de intento de acceso en la bitácora."""
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO bitacora_accesos (usuario_id, ip_origen, exitoso, detalles)
                VALUES (%s, %s, %s, %s)
            """,
                (usuario_id, ip, 1 if exitoso else 0, detalles),
            )
        conn.commit()
    finally:
        conn.close()


def autenticar_usuario(usuario_input: str, password_input: str) -> bool:
    """Valida credenciales contra la BD y actualiza la sesión en Streamlit."""
    conn = get_db_connection()
    if not conn:
        st.error("No se pudo conectar a la base de datos.")
        return False

    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT u.usuario_id, u.nombre_completo, u.usuario, u.password_hash, u.activo, r.nombre AS rol
                FROM usuarios u
                INNER JOIN roles r ON u.rol_id = r.rol_id
                WHERE u.usuario = %s
            """
            cursor.execute(sql, (usuario_input.strip(),))
            user = cursor.fetchone()

            if not user:
                st.error("Usuario o contraseña incorrectos.")
                return False

            if not user["activo"]:
                st.error("Este usuario se encuentra inactivo.")
                registrar_bitacora(
                    user["usuario_id"], False, "Intento en cuenta inactiva"
                )
                return False

            if verify_password(password_input, user["password_hash"]):
                cursor.execute(
                    "UPDATE usuarios SET ultimo_login = %s WHERE usuario_id = %s",
                    (datetime.datetime.now(), user["usuario_id"]),
                )
                conn.commit()

                st.session_state["logged_in"] = True
                st.session_state["user_info"] = {
                    "id": user["usuario_id"],
                    "usuario_id": user["usuario_id"],  # <- Esencial para los filtros
                    "nombre": user["nombre_completo"],
                    "usuario": user["usuario"],
                    "rol": user["rol"],
                }
                registrar_bitacora(
                    user["usuario_id"], True, "Inicio de sesión exitoso"
                )
                return True
            else:
                st.error("Usuario o contraseña incorrectos.")
                registrar_bitacora(
                    user["usuario_id"], False, "Contraseña incorrecta"
                )
                return False
    finally:
        conn.close()
