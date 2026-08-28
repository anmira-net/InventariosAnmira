import pymysql
import pymysql.cursors
import streamlit as st

DB_CONFIG = {
    "host": "svgr348.serverneubox.com.mx",
    "user": "anmirane_admin",
    "password": "AndreaMiaAnmira",
    "database": "anmirane_inventariosanmira",
    "port": 3306,
    "charset": "utf8mb4",
    "connect_timeout": 10,
    "cursorclass": pymysql.cursors.DictCursor,
}

def get_db_connection():
    """Retorna una conexión activa a la base de datos."""
    try:
        return pymysql.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Error conectando a MySQL: {e}")
        return None

def obtener_almacenes_empresa(empresa_id: int):
    """Obtiene dinámicamente los almacenes de la empresa activa como un diccionario."""
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn.cursor() as cursor:
            sql = "SELECT almacen_id, nombre_almacen FROM almacenes WHERE empresa_id = %s ORDER BY nombre_almacen ASC;"
            cursor.execute(sql, (empresa_id,))
            rows = cursor.fetchall()
            return {r['nombre_almacen']: r['almacen_id'] for r in rows}
    except Exception as e:
        st.error(f"Error al cargar almacenes de la empresa: {e}")
        return {}
    finally:
        conn.close()

def inicializar_sistema_inventario(empresa_id: int):
    """Limpia todo el inventario, catálogo local, sesiones y lecturas ÚNICAMENTE de la empresa activa."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            # Borrado en cascada filtrado por empresa
            cursor.execute("""
                DELETE l FROM lecturas_inventario l
                INNER JOIN sesiones_inventario s ON l.sesion_id = s.sesion_id
                WHERE s.empresa_id = %s;
            """, (empresa_id,))
            
            cursor.execute("""
                DELETE z FROM zonas_inventario z
                INNER JOIN sesiones_inventario s ON z.sesion_id = s.sesion_id
                WHERE s.empresa_id = %s;
            """, (empresa_id,))
            
            cursor.execute("DELETE FROM sesiones_inventario WHERE empresa_id = %s;", (empresa_id,))
            cursor.execute("DELETE FROM catalogo_local WHERE empresa_id = %s;", (empresa_id,))
            
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al inicializar el sistema: {e}")
        return False
    finally:
        conn.close()