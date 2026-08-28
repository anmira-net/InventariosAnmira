import datetime
import bcrypt
import streamlit as st
from database import get_db_connection

def hash_password(password: str) -> str:
    """Genera un hash seguro utilizando bcrypt a partir de una contraseña en texto plano."""
    if not password:
        return ""
    # Convierte la contraseña a bytes, genera el salt y la encripta
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    if not password or not hashed:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def verify_password(password: str, hashed: str) -> bool:
    if not password or not hashed:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def registrar_bitacora(usuario_id: int, exitoso: bool, detalles: str, ip: str = "127.0.0.1"):
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
    conn = get_db_connection()
    if not conn:
        st.error("No se pudo conectar a la base de datos.")
        return False

    try:
        with conn.cursor() as cursor:
            # JOIN con la tabla empresas para obtener el contexto del tenant
            sql = """
                SELECT u.usuario_id, u.nombre_completo, u.usuario, u.password_hash, u.activo, 
                       u.empresa_id, e.nombre_empresa, r.nombre AS rol
                FROM usuarios u
                INNER JOIN roles r ON u.rol_id = r.rol_id
                INNER JOIN empresas e ON u.empresa_id = e.empresa_id
                WHERE u.usuario = %s AND e.activo = 1
            """
            cursor.execute(sql, (usuario_input.strip(),))
            user = cursor.fetchone()

            if not user:
                st.error("Usuario/contraseña incorrectos o empresa inactiva.")
                return False

            if not user["activo"]:
                st.error("Este usuario se encuentra inactivo.")
                registrar_bitacora(user["usuario_id"], False, "Intento en cuenta inactiva")
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
                    "nombre": user["nombre_completo"],
                    "usuario": user["usuario"],
                    "rol": user["rol"],
                    "empresa_id": user["empresa_id"],
                    "nombre_empresa": user["nombre_empresa"]
                }
                registrar_bitacora(user["usuario_id"], True, "Inicio de sesión exitoso")
                return True
            else:
                st.error("Usuario o contraseña incorrectos.")
                registrar_bitacora(user["usuario_id"], False, "Contraseña incorrecta")
                return False
    finally:
        conn.close()