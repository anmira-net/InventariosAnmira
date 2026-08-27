from auth import hash_password
from database import get_db_connection


def reset_usuario_admin():
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a MySQL local.")
        return

    usuario = "admin"
    password_plana = "admin123"
    password_enc = hash_password(password_plana)

    try:
        with conn.cursor() as cursor:
            # 1. Asegurar que existe el rol Admin
            cursor.execute(
                "INSERT IGNORE INTO roles (rol_id, nombre, descripcion) VALUES (1, 'Admin', 'Administrador General')"
            )

            # 2. Insertar o actualizar el usuario admin
            sql = """
                INSERT INTO usuarios (usuario_id, rol_id, nombre_completo, usuario, password_hash, activo)
                VALUES (1, 1, 'Administrador del Sistema', %s, %s, 1)
                ON DUPLICATE KEY UPDATE password_hash = %s, activo = 1
            """
            cursor.execute(sql, (usuario, password_enc, password_enc))

        conn.commit()
        print(
            f"✅ ¡Usuario '{usuario}' restablecido correctamente con la contraseña '{password_plana}'!"
        )
    except Exception as e:
        print(f"❌ Error al crear usuario: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    reset_usuario_admin()