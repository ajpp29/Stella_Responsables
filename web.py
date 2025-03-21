import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
import os
import time
from dotenv import load_dotenv

# Configuración de la página
st.set_page_config(page_title="Gestión de Responsables", layout="wide")

# Cargar variables de entorno
load_dotenv()

# Configuración de la conexión a SQL Server
server = os.getenv('DB_SERVER', '')
database = os.getenv('DB_DATABASE', '')
usuario = os.getenv('DB_USER', '')
password = os.getenv('DB_PASSWORD', '')

# Función para crear conexión a la base de datos
@st.cache_resource
def init_connection():
    connection_string = f"mssql+pyodbc://{usuario}:{password}@{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
    return create_engine(connection_string)

@st.cache_data(ttl=600)
def run_query(query):
    try:
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"Error al ejecutar la consulta: {e}")
        return pd.DataFrame()  # Retorna un DataFrame vacío en caso de error

# Función para actualizar un responsable
def update_responsable(id, usuario, nombre, apellido):
    with engine.connect() as conn:
        # Convertir el id a int nativo de Python
        id_python = int(id)
        query = text(f"""
            UPDATE dbo.Stella_Responsables 
            SET usuario = :usuario, nombre = :nombre, apellido = :apellido
            WHERE id = :id
        """)
        conn.execute(query, {"usuario": usuario, "nombre": nombre, "apellido": apellido, "id": id_python})
        conn.commit()
        st.success(f"Responsable actualizado correctamente (ID: {id})")

# Función para obtener valores únicos de una columna
@st.cache_data(ttl=600)
def get_unique_values(column):
    df = run_query(f"SELECT DISTINCT {column} FROM dbo.Stella_Responsables ORDER BY {column}")
    return ["Todos"] + df[column].tolist()

# Función para obtener usuarios de la tabla dbo.Stella_Usuarios
@st.cache_data(ttl=600)
def get_usuarios():
    query = "SELECT username, first_name, last_name FROM dbo.Stella_Usuarios WHERE is_active = 1"
    return run_query(query)

# Inicializar conexión a la base de datos
try:
    engine = init_connection()
    st.sidebar.success("Conexión a la base de datos establecida")
except Exception as e:
    st.sidebar.error(f"Error de conexión a la base de datos: {e}")
    st.stop()

# Título principal
st.title("Gestión de Responsables Académicos")

# Filtros en la barra lateral
st.sidebar.header("Filtros")

# Cargar opciones de filtros
sedes = get_unique_values("sede")
escuelas = get_unique_values("escuela")
carreras = get_unique_values("carrera")
niveles = get_unique_values("nivel")
jornadas = get_unique_values("jornada")
usuarios = get_unique_values("usuario")  # Nuevo filtro

# Agregar filtros en la barra lateral
sede_filter = st.sidebar.selectbox("Sede", sedes)
escuela_filter = st.sidebar.selectbox("Escuela", escuelas)
carrera_filter = st.sidebar.selectbox("Carrera", carreras)
nivel_filter = st.sidebar.selectbox("Nivel", niveles)
jornada_filter = st.sidebar.selectbox("Jornada", jornadas)
usuario_filter = st.sidebar.selectbox("Usuario", usuarios)  # Nuevo filtro

# Consulta base
query = "SELECT * FROM dbo.Stella_Responsables WHERE 1=1"

# Aplicar filtros seleccionados
if sede_filter != "Todos":
    query += f" AND sede = '{sede_filter}'"
if escuela_filter != "Todos":
    query += f" AND escuela = '{escuela_filter}'"
if carrera_filter != "Todos":
    query += f" AND carrera = '{carrera_filter}'"
if nivel_filter != "Todos":
    query += f" AND nivel = '{nivel_filter}'"
if jornada_filter != "Todos":
    query += f" AND jornada = '{jornada_filter}'"
if usuario_filter != "Todos":  # Nuevo filtro
    query += f" AND usuario = '{usuario_filter}'"

# Ejecutar la consulta filtrada
df = run_query(query)

# Mostrar resultados con estadísticas
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total de registros", len(df))
with col2:
    st.metric("Responsables únicos", df['usuario'].nunique())
with col3:
    if len(df) > 0:
        st.metric("Configuraciones por responsable (promedio)", round(len(df) / df['usuario'].nunique(), 1))

# Modo de visualización
view_mode = st.radio("Modo de visualización", ["Vista de tabla", "Edición individual", "Edición por grupo"])

if view_mode == "Vista de tabla":
    # Mostrar todos los datos en una tabla
    st.subheader("Lista de responsables")
    st.dataframe(df)
    
    # Exportar a Excel
    if st.button("Exportar a Excel"):
        df.to_excel("responsables_export.xlsx", index=False)
        st.success("Datos exportados a 'responsables_export.xlsx'")

elif view_mode == "Edición individual":
    # Seleccionar un registro para editar
    st.subheader("Editar responsable individual")
    
    if len(df) > 0:
        # Crear un índice para selección fácil
        selection_df = df.copy()
        selection_df['descripcion'] = selection_df.apply(lambda row: f"{row['sede']} - {row['escuela']} - {row['carrera']} (Nivel {row['nivel']}, Jornada {row['jornada']})", axis=1)
        
        selected_desc = st.selectbox("Seleccione una configuración para editar:", selection_df['descripcion'].tolist())
        selected_row = selection_df[selection_df['descripcion'] == selected_desc].iloc[0]
        
        # Obtener usuarios activos
        usuarios_df = get_usuarios()
        usuarios_list = usuarios_df['username'].tolist()
        
        # Selector de usuario (fuera del formulario para actualización en tiempo real)
        new_usuario = st.selectbox("Usuario", usuarios_list, index=usuarios_list.index(selected_row['usuario']) if selected_row['usuario'] in usuarios_list else 0, key="usuario_select")
        
        # Buscar información del usuario seleccionado
        selected_user_info = usuarios_df[usuarios_df['username'] == new_usuario]
        default_nombre = selected_user_info['first_name'].iloc[0] if not selected_user_info.empty else ""
        default_apellido = selected_user_info['last_name'].iloc[0] if not selected_user_info.empty else ""
        
        # Mostrar información del usuario seleccionado
        st.info(f"Información del usuario seleccionado: {new_usuario} - {default_nombre} {default_apellido}")
        
        # Formulario para la actualización
        with st.form("edicion_form"):
            st.write(f"Editando: {selected_desc}")
            
            # Campos de nombre y apellido con valores preestablecidos
            new_nombre = st.text_input("Nombre", value=default_nombre)
            new_apellido = st.text_input("Apellido", value=default_apellido)
            
            # Mostrar información de solo lectura
            st.write("**Información de configuración (no editable):**")
            st.write(f"Sede: {selected_row['sede']}")
            st.write(f"Escuela: {selected_row['escuela']}")
            st.write(f"Carrera: {selected_row['carrera']}")
            st.write(f"Nivel: {selected_row['nivel']}")
            st.write(f"Jornada: {selected_row['jornada']}")
            
            # Campo oculto para guardar el usuario seleccionado
            st.text_input("Usuario seleccionado", value=new_usuario, key="usuario_seleccionado", type="password", disabled=True)
            
            # Botón de actualización
            submit = st.form_submit_button("Actualizar responsable")
            
            if submit:
                update_responsable(selected_row['id'], new_usuario, new_nombre, new_apellido)
                # Dar tiempo para que el usuario vea el mensaje
                time.sleep(1)
                # Limpiar caché y recargar
                get_unique_values.clear()
                get_usuarios.clear()
                run_query.clear()
                st.rerun()
    else:
        st.warning("No hay registros para editar con los filtros actuales")

elif view_mode == "Edición por grupo":
    st.subheader("Edición por grupo")
    
    if len(df) > 0:
        # Mostrar resumen de los registros seleccionados
        st.write(f"Actualizará {len(df)} registros que coinciden con los criterios de filtro:")
        
        if sede_filter != "Todos": st.write(f"- Sede: {sede_filter}")
        if escuela_filter != "Todos": st.write(f"- Escuela: {escuela_filter}")
        if carrera_filter != "Todos": st.write(f"- Carrera: {carrera_filter}")
        if nivel_filter != "Todos": st.write(f"- Nivel: {nivel_filter}")
        if jornada_filter != "Todos": st.write(f"- Jornada: {jornada_filter}")
        
        # Obtener usuarios activos
        usuarios_df = get_usuarios()
        usuarios_list = usuarios_df['username'].tolist()
        
        # Selector de usuario
        new_usuario_batch = st.selectbox("Usuario", usuarios_list, key="usuario_batch_select")
        
        # Buscar información del usuario seleccionado
        selected_user_info = usuarios_df[usuarios_df['username'] == new_usuario_batch]
        default_nombre_batch = selected_user_info['first_name'].iloc[0] if not selected_user_info.empty else ""
        default_apellido_batch = selected_user_info['last_name'].iloc[0] if not selected_user_info.empty else ""
        
        # Mostrar información del usuario seleccionado
        st.info(f"Información del usuario seleccionado: {new_usuario_batch} - {default_nombre_batch} {default_apellido_batch}")
        
        # Formulario para actualización masiva
        with st.form("actualizacion_masiva"):
            st.write("Ingrese los datos del nuevo responsable:")
            
            # Campos de nombre y apellido con valores preestablecidos
            new_nombre_batch = st.text_input("Nombre", value=default_nombre_batch)
            new_apellido_batch = st.text_input("Apellido", value=default_apellido_batch)
            
            # Mostrar lista de IDs que se actualizarán
            with st.expander("Ver registros que se actualizarán"):
                st.dataframe(df)
            
            submit_batch = st.form_submit_button("Actualizar todos los registros seleccionados")
            
            if submit_batch:
                if not new_usuario_batch or not new_nombre_batch or not new_apellido_batch:
                    st.error("Por favor complete todos los campos")
                else:
                    # Actualizar cada registro
                    with st.spinner("Actualizando registros..."):
                        for idx, row in df.iterrows():
                            update_responsable(row['id'], new_usuario_batch, new_nombre_batch, new_apellido_batch)
                        st.success(f"Se actualizaron {len(df)} registros correctamente")

                # Dar tiempo para que el usuario vea el mensaje
                time.sleep(1)
                # Limpiar caché y recargar
                get_unique_values.clear()
                get_usuarios.clear()
                run_query.clear()
                st.rerun()
    else:
        st.warning("No hay registros para editar con los filtros actuales")

# Footer con ayuda
with st.expander("Ayuda"):
    st.write("""
    **Instrucciones de uso:**
    1. Use los filtros en el panel izquierdo para encontrar los registros deseados
    2. Elija el modo de visualización según lo que necesite hacer:
        - **Vista de tabla**: Solo visualización y exportación
        - **Edición individual**: Actualizar un responsable específico
        - **Edición por grupo**: Actualizar varios responsables que cumplan los criterios de filtro
    3. Complete los formularios y guarde los cambios
    """)