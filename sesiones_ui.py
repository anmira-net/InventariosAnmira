import openpyxl
import streamlit as st
from database import get_db_connection

# ==========================================
# CONSULTAS DE ALMACENES AUTORIZADOS
# ==========================================

def obtener_almacenes_permitidos():
    """Obtiene únicamente los almacenes permitidos para el usuario logueado en la sesión."""
    user_info = st.session_state.get("user_info")
    if not user_info or "usuario_id" not in user_info:
        st.error("No se encontró la información del usuario en sesión.")
        return {}

    usuario_id = user_info["usuario_id"]
    conn = get_db_connection()
    if not conn:
        return {}

    try:
        with conn.cursor() as cursor:
            # Si es Admin ve todos los almacenes; si no, solo sus asignados
            if user_info.get("rol") in ["Admin", "Administrador"]:
                sql = "SELECT almacen_id, nombre_almacen FROM almacenes ORDER BY nombre_almacen ASC"
                cursor.execute(sql)
            else:
                sql = """
                    SELECT a.almacen_id, a.nombre_almacen 
                    FROM almacenes a
                    INNER JOIN usuario_almacenes ua ON a.almacen_id = ua.almacen_id
                    WHERE ua.usuario_id = %s
                    ORDER BY a.nombre_almacen ASC
                """
                cursor.execute(sql, (usuario_id,))

            res = cursor.fetchall()
            return {r["nombre_almacen"]: r["almacen_id"] for r in res}
    except Exception as e:
        st.error(f"Error al obtener almacenes permitidos: {e}")
        return {}
    finally:
        conn.close()


def obtener_usuarios_activos():
    """Obtiene la lista de usuarios activos para asignar como auditores."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = "SELECT usuario_id, nombre_completo, usuario FROM usuarios WHERE activo = 1 ORDER BY nombre_completo ASC;"
            cursor.execute(sql)
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al cargar usuarios: {e}")
        return []
    finally:
        conn.close()

# ==========================================
# CRUD DE SESIONES DE INVENTARIO
# ==========================================

def obtener_id_usuario_valido(user_id):
    """Verifica si el ID existe en la BD o toma el primer usuario activo disponible."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cursor:
            # 1. Verificar si el ID enviado desde la sesión existe en MySQL
            cursor.execute("SELECT usuario_id FROM usuarios WHERE usuario_id = %s;", (user_id,))
            res = cursor.fetchone()
            if res:
                return res["usuario_id"]
            
            # 2. Si no existe, tomar el primer usuario registrado/activo para evitar el error 1452
            cursor.execute("SELECT usuario_id FROM usuarios LIMIT 1;")
            first_user = cursor.fetchone()
            if first_user:
                return first_user["usuario_id"]
            return None
    except Exception as e:
        st.error(f"Error al verificar usuario: {e}")
        return None
    finally:
        conn.close()


def crear_sesion(almacen_id, observaciones, usuario_creador_id):
    """Crea una nueva sesión usando la columna 'creado_por' y un usuario válido."""
    conn = get_db_connection()
    if not conn:
        return False

    # Validar que el usuario exista en la tabla usuarios para no romper la FK
    user_id_valido = obtener_id_usuario_valido(usuario_creador_id)
    if not user_id_valido:
        st.error("No se encontró ningún usuario registrado en la base de datos para asociar la sesión.")
        return False

    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO sesiones_inventario (almacen_id, estado, observaciones, creado_por)
                VALUES (%s, 'ABIERTA', %s, %s);
            """
            cursor.execute(sql, (almacen_id, observaciones, user_id_valido))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al crear la sesión: {e}")
        return False
    finally:
        conn.close()

        
def obtener_sesiones_permitidas(almacenes_ids):
    """Recupera únicamente las sesiones pertenecientes a los almacenes permitidos."""
    if not almacenes_ids:
        return []
        
    conn = get_db_connection()
    if not conn:
        return []
    try:
        format_strings = ','.join(['%s'] * len(almacenes_ids))
        with conn.cursor() as cursor:
            sql = f"""
                SELECT s.sesion_id, s.almacen_id, a.nombre_almacen, s.fecha_inicio, s.fecha_cierre, 
                       s.estado, s.observaciones, u.nombre_completo AS creador
                FROM sesiones_inventario s
                INNER JOIN almacenes a ON s.almacen_id = a.almacen_id
                LEFT JOIN usuarios u ON s.usuario_creador_id = u.usuario_id
                WHERE s.almacen_id IN ({format_strings})
                ORDER BY s.sesion_id DESC;
            """
            cursor.execute(sql, list(almacenes_ids))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al obtener sesiones: {e}")
        return []
    finally:
        conn.close()


def actualizar_sesion(sesion_id, observaciones, estado):
    """Actualiza observaciones y estado de una sesión."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            if estado == 'CERRADA':
                sql = "UPDATE sesiones_inventario SET observaciones = %s, estado = %s, fecha_cierre = CURRENT_TIMESTAMP WHERE sesion_id = %s;"
            else:
                sql = "UPDATE sesiones_inventario SET observaciones = %s, estado = %s WHERE sesion_id = %s;"
            cursor.execute(sql, (observaciones, estado, sesion_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al actualizar la sesión: {e}")
        return False
    finally:
        conn.close()


def eliminar_sesion(sesion_id):
    """Elimina la sesión, sus zonas y conteos asociados."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cursor.execute("DELETE c FROM lecturas_inventario c INNER JOIN zonas_inventario z ON c.zona_id = z.zona_id WHERE z.sesion_id = %s;", (sesion_id,))
            cursor.execute("DELETE FROM zonas_inventario WHERE sesion_id = %s;", (sesion_id,))
            cursor.execute("DELETE FROM sesiones_inventario WHERE sesion_id = %s;", (sesion_id,))
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al eliminar la sesión: {e}")
        return False
    finally:
        conn.close()

# ==========================================
# CRUD DE ZONAS / PASILLOS
# ==========================================

def crear_zona(sesion_id, codigo_zona, nombre_zona, usuario_asignado_id):
    """Crea una zona asociada a la sesión de inventario."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO zonas_inventario (sesion_id, codigo_zona, nombre_zona, usuario_asignado_id, estado)
                VALUES (%s, %s, %s, %s, 'PENDIENTE');
            """
            cursor.execute(sql, (sesion_id, codigo_zona, nombre_zona, usuario_asignado_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al crear la zona: {e}")
        return False
    finally:
        conn.close()


def obtener_zonas_por_sesion(sesion_id):
    """Recupera las zonas de una sesión con el auditor asignado."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT z.zona_id, z.sesion_id, z.codigo_zona, z.nombre_zona, z.usuario_asignado_id, z.estado, u.nombre_completo AS auditor
                FROM zonas_inventario z
                LEFT JOIN usuarios u ON z.usuario_asignado_id = u.usuario_id
                WHERE z.sesion_id = %s
                ORDER BY z.codigo_zona ASC;
            """
            cursor.execute(sql, (sesion_id,))
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error al obtener zonas: {e}")
        return []
    finally:
        conn.close()


def actualizar_zona(zona_id, codigo_zona, nombre_zona, usuario_asignado_id, estado):
    """Actualiza la información de una zona."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE zonas_inventario 
                SET codigo_zona = %s, nombre_zona = %s, usuario_asignado_id = %s, estado = %s 
                WHERE zona_id = %s;
            """
            cursor.execute(sql, (codigo_zona, nombre_zona, usuario_asignado_id, estado, zona_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al actualizar la zona: {e}")
        return False
    finally:
        conn.close()


def eliminar_zona(zona_id):
    """Elimina una zona específica."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM zonas_inventario WHERE zona_id = %s;", (zona_id,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error al eliminar la zona: {e}")
        return False
    finally:
        conn.close()


def importar_zonas_desde_excel(file_buffer, sesion_id):
    """Importa zonas masivamente desde Excel."""
    try:
        wb = openpyxl.load_workbook(file_buffer, data_only=True)
        sheet = wb.active
    except Exception as e:
        st.error(f"Error al abrir el archivo Excel: {e}")
        return 0

    nombres_zonas = set()

    for rng in sheet.merged_cells.ranges:
        val = sheet.cell(row=rng.min_row, column=rng.min_col).value
        if val and str(val).strip():
            nombres_zonas.add(str(val).strip().upper())

    for row in sheet.iter_rows(values_only=True):
        for val in row:
            if val and str(val).strip():
                nombres_zonas.add(str(val).strip().upper())

    if not nombres_zonas:
        st.warning("No se encontraron zonas válidas en el archivo Excel.")
        return 0

    conn = get_db_connection()
    if not conn:
        return 0

    registros = 0
    sql = "INSERT INTO zonas_inventario (sesion_id, codigo_zona, nombre_zona, estado) VALUES (%s, %s, %s, 'PENDIENTE');"

    try:
        with conn.cursor() as cursor:
            for nombre in sorted(nombres_zonas):
                codigo = nombre.replace(" ", "_")
                try:
                    cursor.execute(sql, (sesion_id, codigo, nombre))
                    registros += 1
                except Exception:
                    pass
        conn.commit()
    except Exception as e:
        st.error(f"Error al importar zonas: {e}")
    finally:
        conn.close()

    return registros

# ==========================================
# INTERFAZ PRINCIPAL EN STREAMLIT
# ==========================================

def render_modulo_sesiones_zonas():
    st.title("📍 Gestión de Sesiones y Zonas de Inventario")

    dict_almacenes = obtener_almacenes_permitidos()
    if not dict_almacenes:
        st.warning("⚠️ No tienes almacenes permitidos asignados.")
        return

    almacenes_ids = list(dict_almacenes.values())

    tab1, tab2 = st.tabs(["📋 Auditorías / Sesiones", "🗺️ Asignación de Zonas"])

    # ----------------------------------------------------
    # TAB 1: GESTIÓN DE SESIONES
    # ----------------------------------------------------
    with tab1:
        col_crear, col_lista = st.columns([1, 1.6])

        with col_crear:
            st.subheader("➕ Nueva Auditoría")

            with st.form("form_nueva_sesion", clear_on_submit=True):
                nombre_almacen_sel = st.selectbox(
                    "Selecciona el Almacén a Auditar:",
                    options=list(dict_almacenes.keys())
                )
                almacen_id = dict_almacenes[nombre_almacen_sel]

                observaciones = st.text_area(
                    "Notas / Observaciones:",
                    placeholder="Ej. Inventario Anual Cierre de Mes"
                )
                btn_crear = st.form_submit_button("🚀 Abrir Sesión", use_container_width=True)

                if btn_crear:
                    user_info = st.session_state.get("user_info", {})
                    user_id = user_info.get("usuario_id", 1)

                    if crear_sesion(almacen_id, observaciones, user_id):
                        st.success(f"¡Auditoría abierta para {nombre_almacen_sel}!")
                        st.rerun()

        with col_lista:
            st.subheader("📜 Auditorías Registradas")
            sesiones = obtener_sesiones_permitidas(almacenes_ids)

            if not sesiones:
                st.info("No hay sesiones de inventario registradas en tus almacenes autorizados.")
            else:
                for s in sesiones:
                    s_id = s["sesion_id"]
                    s_alm_nombre = s.get("nombre_almacen", f"Almacén #{s['almacen_id']}")
                    s_obs = s.get("observaciones", "") or "Sin observaciones"
                    s_est = s.get("estado", "ABIERTA")
                    s_creador = s.get("creador", "Admin")

                    with st.expander(f"📌 Sesión #{s_id} - {s_alm_nombre} [{s_est}]"):
                        st.write(f"**Creado por:** {s_creador}")
                        st.write(f"**Notas:** {s_obs}")

                        with st.form(f"form_edit_sesion_{s_id}"):
                            nueva_obs = st.text_area("Modificar Notas:", value=s_obs)
                            estados_list = ["ABIERTA", "EN_PROCESO", "CERRADA", "CANCELADA"]
                            idx_est = estados_list.index(s_est) if s_est in estados_list else 0
                            nuevo_estado = st.selectbox("Estado de la Sesión:", estados_list, index=idx_est)

                            if st.form_submit_button("💾 Guardar Cambios"):
                                if actualizar_sesion(s_id, nueva_obs, nuevo_estado):
                                    st.success("Sesión actualizada.")
                                    st.rerun()

                        st.markdown("---")
                        if st.checkbox(f"⚠️ Confirmar eliminación de Sesión #{s_id}", key=f"chk_del_s_{s_id}"):
                            if st.button(f"🗑️ Eliminar Sesión #{s_id}", type="primary", key=f"btn_del_s_{s_id}"):
                                if eliminar_sesion(s_id):
                                    st.success("Sesión eliminada.")
                                    st.rerun()

    # ----------------------------------------------------
    # TAB 2: GESTIÓN DE ZONAS
    # ----------------------------------------------------
    with tab2:
        sesiones = obtener_sesiones_permitidas(almacenes_ids)
        if not sesiones:
            st.warning("Primero debes abrir una Sesión de Inventario en tus almacenes autorizados.")
        else:
            opciones_sesiones = {}
            for s in sesiones:
                nom_alm = s.get("nombre_almacen", f"Almacén #{s['almacen_id']}")
                opciones_sesiones[f"Sesión #{s['sesion_id']} - {nom_alm} ({s.get('estado')})"] = s['sesion_id']

            sesion_sel_label = st.selectbox("Selecciona la Auditoría activa:", list(opciones_sesiones.keys()))
            sesion_id_activa = opciones_sesiones[sesion_sel_label]

            # IMPORTACIÓN MASIVA DESDE EXCEL
            st.markdown("---")
            with st.expander("📥 Importación Masiva de Zonas desde Excel", expanded=False):
                st.caption("Sube un archivo Excel (.xlsx) con los nombres de tus zonas/pasillos para crearlas automáticamente.")
                archivo_excel = st.file_uploader("Selecciona el archivo Excel:", type=["xlsx"], key="excel_zonas_uploader")
                
                if archivo_excel and st.button("🚀 Importar Zonas", type="primary"):
                    total = importar_zonas_desde_excel(archivo_excel, sesion_id_activa)
                    if total > 0:
                        st.success(f"¡Éxito! Se registraron **{total} zonas** para esta auditoría.")
                        st.rerun()

            st.markdown("---")

            usuarios = obtener_usuarios_activos()
            mapa_usuarios = {f"{u['nombre_completo']} ({u['usuario']})": u['usuario_id'] for u in usuarios}
            mapa_usuarios["-- Sin Asignar --"] = None

            col_z_crear, col_z_lista = st.columns([1, 1.6])

            with col_z_crear:
                st.subheader("➕ Agregar Zona Manual")
                with st.form("form_nueva_zona", clear_on_submit=True):
                    cod_zona = st.text_input("Código de Zona / Pasillo:", placeholder="Ej. PASILLO-01, BODEGA-A")
                    nom_zona = st.text_input("Nombre / Descripción Corta:", placeholder="Ej. Rack Estantería Alta")
                    auditor_sel = st.selectbox("Auditor Asignado:", list(mapa_usuarios.keys()))
                    auditor_id = mapa_usuarios[auditor_sel]

                    if st.form_submit_button("➕ Registrar Zona", use_container_width=True):
                        if not cod_zona.strip():
                            st.warning("El código de zona es obligatorio.")
                        else:
                            if crear_zona(sesion_id_activa, cod_zona.strip().upper(), nom_zona.strip(), auditor_id):
                                st.success(f"¡Zona '{cod_zona}' registrada!")
                                st.rerun()

            with col_z_lista:
                st.subheader("🗺️ Zonas de la Auditoría")
                zonas = obtener_zonas_por_sesion(sesion_id_activa)

                if not zonas:
                    st.info("No hay zonas asignadas a esta sesión de inventario.")
                else:
                    for z in zonas:
                        z_id = z["zona_id"]
                        z_cod = z["codigo_zona"]
                        z_nom = z.get("nombre_zona", "")
                        z_usr_id = z.get("usuario_asignado_id")
                        z_est = z.get("estado", "PENDIENTE")
                        z_auditor = z.get("auditor", "Sin Asignar")

                        with st.expander(f"📍 {z_cod} - {z_nom} [{z_est}] (Auditor: {z_auditor})"):
                            with st.form(f"form_edit_zona_{z_id}"):
                                edit_cod = st.text_input("Código Zona:", value=z_cod)
                                edit_nom = st.text_input("Nombre/Descripción:", value=z_nom)

                                idx_usr = 0
                                list_keys = list(mapa_usuarios.keys())
                                for idx, k in enumerate(list_keys):
                                    if mapa_usuarios[k] == z_usr_id:
                                        idx_usr = idx
                                        break

                                edit_auditor = st.selectbox("Reasignar Auditor:", list_keys, index=idx_usr)
                                edit_auditor_id = mapa_usuarios[edit_auditor]

                                estados_z = ["PENDIENTE", "EN_PROCESO", "COMPLETADO"]
                                idx_z_est = estados_z.index(z_est) if z_est in estados_z else 0
                                edit_estado = st.selectbox("Estado de la Zona:", estados_z, index=idx_z_est)

                                if st.form_submit_button("💾 Actualizar Zona"):
                                    if actualizar_zona(z_id, edit_cod.upper(), edit_nom, edit_auditor_id, edit_estado):
                                        st.success("Zona actualizada.")
                                        st.rerun()

                            st.markdown("---")
                            if st.checkbox(f"⚠️ Confirmar eliminación de Zona '{z_cod}'", key=f"chk_del_z_{z_id}"):
                                if st.button(f"🗑️ Eliminar Zona '{z_cod}'", type="primary", key=f"btn_del_z_{z_id}"):
                                    if eliminar_zona(z_id):
                                        st.success("Zona eliminada.")
                                        st.rerun()