import pymysql
import pymysql.cursors

# Ajusta credenciales de Neubox / cPanel
DB_CONFIG = {
    "host": "svgr348.serverneubox.com.mx",
    "user": "anmirane_admin",  # Usuario por defecto
    "password": "AndreaMiaAnmira",  # Contraseña vacía por defecto en XAMPP
    "database": "anmirane_inventariosanmira",
    "port": 3306,
    "cursorclass": pymysql.cursors.DictCursor,
}

def get_db_connection():
    """Retorna una conexión activa a la base de datos."""
    try:
        return pymysql.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Error conectando a MySQL: {e}")
        return None

def inicializar_sistema_inventario():
    """Limpia todo el inventario, catálogo local, sesiones y lecturas, conservando únicamente usuarios."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            # Desactivar restricciones de llaves foráneas para poder vaciar en cualquier orden
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            cursor.execute("TRUNCATE TABLE lecturas_inventario;")
            cursor.execute("TRUNCATE TABLE zonas_inventario;")
            cursor.execute("TRUNCATE TABLE sesiones_inventario;")
            cursor.execute("TRUNCATE TABLE catalogo_local;")
            
            # Reactivar restricciones
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al inicializar el sistema: {e}")
        return False
    finally:
        conn.close()
