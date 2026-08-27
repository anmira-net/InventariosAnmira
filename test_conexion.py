import sys
import pymysql
import pymysql.cursors

#DB_CONFIG = {
#    "host": "localhost",
#    "user": "anmirane_admin",
#    "password": "AndreaMia290913",
#    "database": "inventariosanmira",
#    "port": 3306,
#}
DB_CONFIG = {
    "host": "localhost",
    "user": "root",  # Usuario por defecto
    "password": "",  # Contraseña vacía por defecto en XAMPP
    "database": "inventariosanmira",
    "port": 3306,
    "cursorclass": pymysql.cursors.DictCursor,
}

def probar_conexion():
    print("🔌 Intentando conectar a la base de datos MySQL en Neubox...")
    try:
        connection = pymysql.connect(**DB_CONFIG)
        print("✅ ¡Conexión establecida con éxito!")

        with connection.cursor() as cursor:
            # 1. Verificar versión de MySQL
            cursor.execute("SELECT VERSION() AS version;")
            version = cursor.fetchone()
            print(f"📌 Versión MySQL Servidor: {version['version']}")

            # 2. Verificar tablas existentes
            cursor.execute("SHOW TABLES;")
            tablas = cursor.fetchall()
            print(f"📋 Tablas encontradas ({len(tablas)}):")
            for t in tablas:
                nombre_tabla = list(t.values())[0]
                print(f"   - {nombre_tabla}")

        connection.close()
        print("\n🎉 La prueba fue 100% exitosa. Tu base de datos está lista.")

    except pymysql.err.OperationalError as e:
        code, msg = e.args
        print(f"\n❌ Error de Conexión ({code}): {msg}")
        if code == 2003 or code == 1045:
            print("\n💡 Diagnóstico de fallos:")
            print(
                "1. Asegúrate de haber agregado tu IP en cPanel -> 'MySQL Remote'."
            )
            print("2. Revisa que el usuario y la contraseña sean correctos.")
            print(
                "3. Verifica que el puerto 3306 no esté bloqueado por un Firewall."
            )
    except Exception as e:
        print(f"\n❌ Ocurrió un error inesperado: {e}")


if __name__ == "__main__":
    probar_conexion()