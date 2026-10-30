import datetime
import bcrypt
import streamlit as st
from database import get_db_connection


def hash_password(password: str) -> str:
    """Genera un hash seguro usando bcrypt."""
    if not password:
        return ""
    # Genera la sal y codifica el hash a cadena utf-8
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')




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
def verify_password(password: str, hashed: str) -> bool:
    """Verifica si la contraseña coincide con hash bcrypt o con texto plano."""
    if not password or not hashed:
        return False
    
    # 1. Intentar validar con bcrypt
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        # 2. Fallback: Comparación directa si está en texto plano
        return password == hashed


def autenticar_usuario(usuario_input: str, password_input: str) -> bool:
    """Valida credenciales contra la BD y encripta el hash si estaba en texto plano."""
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
                registrar_bitacora(user["usuario_id"], False, "Intento en cuenta inactiva")
                return False

            # Validar contraseña
            if verify_password(password_input, user["password_hash"]):
                # AUTO-MIGRACIÓN: Si la contraseña estaba en texto plano, guardarla como bcrypt
                if not user["password_hash"].startswith("$2b$") and not user["password_hash"].startswith("$2a$"):
                    nuevo_hash = hash_password(password_input)
                    cursor.execute(
                        "UPDATE usuarios SET password_hash = %s WHERE usuario_id = %s",
                        (nuevo_hash, user["usuario_id"])
                    )

                # Registrar último login
                cursor.execute(
                    "UPDATE usuarios SET ultimo_login = %s WHERE usuario_id = %s",
                    (datetime.datetime.now(), user["usuario_id"]),
                )
                conn.commit()

                st.session_state["logged_in"] = True
                st.session_state["user_info"] = {
                    "id": user["usuario_id"],
                    "usuario_id": user["usuario_id"],
                    "nombre": user["nombre_completo"],
                    "usuario": user["usuario"],
                    "rol": user["rol"],
                }
                registrar_bitacora(user["usuario_id"], True, "Inicio de sesión exitoso")
                return True
            else:
                st.error("Usuario o contraseña incorrectos.")
                registrar_bitacora(user["usuario_id"], False, "Contraseña incorrecta")
                return False
    finally:
        conn.close()