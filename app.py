import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Monitor de Producción", page_icon="🏭", layout="wide")

# --- CONEXIÓN A BASE DE DATOS ---
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Error de conexión a la base de datos: {e}")
    st.stop()

# --- BARRA LATERAL (MENÚ Y CONFIGURACIÓN) ---
st.sidebar.title("⚙️ Controles")
planta_seleccionada = st.sidebar.radio("Sede:", ["Sopó"]) # Solo se mostrara Sopó
# planta_seleccionada = st.sidebar.radio("Sede:", ["Sopó", "Entrerríos"])


# --- METAS ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Configurar Metas por Hora")
with st.sidebar.expander("Ajustar metas actuales", expanded=False):
    st.caption("Modifica estos valores para recalcular las métricas y gráficas.")
    meta_atlanta1 = st.number_input("Atlanta 1", value=100, step=10)
    meta_atlanta2 = st.number_input("Atlanta 2", value=100, step=10)
    meta_litro = st.number_input("Litro", value=100, step=10)
    meta_vertical1 = st.number_input("Vertical 1", value=100, step=10)
    meta_vertical2 = st.number_input("Vertical 2", value=100, step=10)
    meta_vertical3 = st.number_input("Vertical 3", value=100, step=10)

# --- 5 LINEAS DEFINIDAS PARA PRUEBAS ---
METAS_POR_LINEA = {
    "Atlanta 1": meta_atlanta1,
    "Atlanta 2": meta_atlanta2,
    "Litro": meta_litro,
    "Vertical 1": meta_vertical1,
    "Vertical 2": meta_vertical2,
    "Vertical 3": meta_vertical3
}

# --- FUNCIÓN PARA OBTENER DATOS ---
@st.cache_data(ttl=0)
def obtener_datos_crudos(planta):
    query = f"SELECT * FROM prod.v_dashboard_hoy WHERE planta = '{planta}';"
    df = conn.query(query, ttl=0)
    return df

df_crudo = obtener_datos_crudos(planta_seleccionada)

# --- PROCESAMIENTO BASE ---
if df_crudo.empty:
    df_completo = pd.DataFrame(columns=[
        "Hora", "Proceso", "Operador", "Turno", "Operarios", 
        "Producción Real", "Tiempo Perdido (min)", "Observaciones"
    ])
else:
    df_completo = df_crudo.copy()
    df_completo["Meta por Hora"] = df_completo["Proceso"].map(METAS_POR_LINEA).fillna(0)
    df_completo["Tiempo Perdido (min)"] = pd.to_numeric(df_completo["Tiempo Perdido (min)"], errors='coerce').fillna(0)

# --- FILTROS ADICIONALES (LÍNEA Y TURNO) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Filtros de Visualización")

# 1. Filtro por Línea
lineas_disponibles = ["Todas"] + list(METAS_POR_LINEA.keys())
linea_seleccionada = st.sidebar.selectbox("Seleccione la línea:", lineas_disponibles)

# 2. Filtro por Turno
turnos_disponibles = {
    "Todos": "Todos",
    "Turno 1 (06:00 - 14:00)": "Turno 1",
    "Turno 2 (14:00 - 22:00)": "Turno 2",
    "Turno 3 (22:00 - 06:00)": "Turno 3"
}
turno_seleccionado = st.sidebar.selectbox("Seleccione el turno:", list(turnos_disponibles.keys()))
turno_real = turnos_disponibles[turno_seleccionado]

# Aplicar los filtros al DataFrame
df = df_completo.copy()

if not df.empty:
    if linea_seleccionada != "Todas":
        df = df[df["Proceso"] == linea_seleccionada]
    if turno_real != "Todos":
        df = df[df["Turno"] == turno_real]
    
# --- CONTROL DE HORAS FALTANTES (HUECOS EN BLANCO) ---
    if not df.empty:
        df["Hora_Num"] = pd.to_numeric(df["Hora"].astype(str).str.split(':').str[0], errors='coerce')
        
        # sin nulos
        horas_validas = df["Hora_Num"].dropna()
        
        if not horas_validas.empty:
            # Hora mínima y máxima
            hora_min = int(horas_validas.min())
            hora_max = int(horas_validas.max())
            
            # Generamos las horas esperadas
            horas_esperadas = list(range(hora_min, hora_max + 1))
            horas_registradas = horas_validas.astype(int).unique().tolist()
            horas_faltantes = [h for h in horas_esperadas if h not in horas_registradas]
            
            if horas_faltantes:
                st.warning(f"⚠️ **ALERTA DE DATOS FALTANTES:** No hay registros de producción para las horas: **{horas_faltantes}**. Las gráficas mostrarán espacios en vacíos.")
                
            # df para incluir las horas faltantes (NaN)
            df_horas = pd.DataFrame({"Hora_Num": horas_esperadas})
            df = pd.merge(df_horas, df, on="Hora_Num", how="left")
            
            df["Hora"] = df["Hora_Num"]
            
            if linea_seleccionada != "Todas":
                 df["Meta por Hora"] = df["Meta por Hora"].fillna(METAS_POR_LINEA[linea_seleccionada])
    
    # Recalcular
    df["Acumulado Real"] = df["Producción Real"].fillna(0).cumsum()
    df["Acumulado Meta"] = df["Meta por Hora"].fillna(0).cumsum()

# --- ENCABEZADO ---
st.title(f"Monitor de Producción - {planta_seleccionada}")

subtitulos = []
if linea_seleccionada != "Todas":
    subtitulos.append(f"Línea: {linea_seleccionada}")
if turno_real != "Todos":
    subtitulos.append(f"Horario: {turno_seleccionado}")

if subtitulos:
    st.subheader(" | ".join(subtitulos))
else:
    st.markdown("Visualización en tiempo real con detección de alertas y tiempos de paro.")

if df.empty or df["Producción Real"].dropna().empty:
    st.info(f"No hay registros de producción válidos para los filtros seleccionados en el día de hoy.")
    st.stop()

# --- SISTEMA DE ALERTAS CATEGORIZADAS ---
df_alertas = df.dropna(subset=['Turno']).copy()
df_alertas = df_alertas[(df_alertas["Tiempo Perdido (min)"] > 0) | (df_alertas["Observaciones"].str.strip() != "")]

if not df_alertas.empty:
    st.error(f"⚠️ **ATENCIÓN: Se han reportado {len(df_alertas)} incidencias o paros.**")
    
    for index, fila in df_alertas.iterrows():
        minutos = fila['Tiempo Perdido (min)']
        
        # Clasificación
        if pd.isna(minutos) or minutos == 0:
            nivel, icono = "Observación", "ℹ️"
        elif minutos <= 15:
            nivel, icono = "Leve", "🟡"
        elif minutos <= 45:
            nivel, icono = "Moderado", "🟠"
        else:
            nivel, icono = "Crítico", "🔴"
            
# la hora a número sin decimales para el título
        hora_limpia = f"{float(fila['Hora']):.0f}"
        
        with st.expander(f"{icono} Paro {nivel} a las {hora_limpia} - {fila['Proceso']} ({fila['Turno']})"):
            if nivel == "Crítico":
                st.error(f"**Impacto {nivel}:** {minutos:,.0f} minutos perdidos.")
            elif nivel in ["Moderado", "Leve"]:
                st.warning(f"**Impacto {nivel}:** {minutos:,.0f} minutos perdidos.")
            else:
                st.info(f"**Nota:** Sin pérdida de tiempo registrada.")
                
            st.write(f"**Operador a cargo:** {fila['Operador']}")
            st.write(f"**Detalle del problema:** {fila['Observaciones']}")

# --- MÉTRICAS ---
st.markdown("### Resumen")
col1, col2, col3, col4 = st.columns(4)

total_real = df["Producción Real"].sum()
total_meta = df["Meta por Hora"].sum()
total_perdida = df["Tiempo Perdido (min)"].sum()

eficiencia = (total_real / total_meta * 100) if total_meta > 0 else 0

col1.metric("Producción Total", f"{total_real:,.0f} uds")
col2.metric("Meta Acumulada", f"{total_meta:,.0f} uds")
col3.metric("Tiempo Total de Paro", f"{total_perdida:,.0f} min", delta="- Inactividad", delta_color="inverse")
col4.metric("Eficiencia (OEE aprox)", f"{eficiencia:.1f}%", f"{eficiencia - 100:.1f}%")

st.markdown("---")

# --- GRÁFICAS PRINCIPALES ---
col_grafica1, col_grafica2 = st.columns(2)

with col_grafica1:
    st.subheader("📊 Producción vs Meta")
    fig_hora = go.Figure()
    
    fig_hora.add_trace(go.Bar(
        x=df["Hora"], y=df["Producción Real"],
        name="Producción Real", marker_color="#3b82f6"
    ))
    fig_hora.add_trace(go.Scatter(
        x=df["Hora"], y=df["Meta por Hora"],
        name="Meta por Hora", mode="lines+markers",
        line=dict(color="#10b981", width=3, dash="dash"),
        connectgaps=False
    ))
    
    fig_hora.update_layout(margin=dict(t=20, b=20, l=20, r=20), hovermode="x unified", barmode='group')
    st.plotly_chart(fig_hora, use_container_width=True)

with col_grafica2:
    st.subheader("⏱️ Control de Tiempos de Paro")
    
    fig_averias = px.area(
        df, x="Hora", y="Tiempo Perdido (min)",
        color_discrete_sequence=["#ef4444"], 
        labels={"Tiempo Perdido (min)": "Minutos Inactivos"}
    )
    fig_averias.update_traces(connectgaps=False) # Vacio si no hay datos
    fig_averias.update_layout(margin=dict(t=20, b=20, l=20, r=20), hovermode="x unified")
    st.plotly_chart(fig_averias, use_container_width=True)

# --- TABLA DE DETALLES ---
with st.expander("Ver tabla de registros detallada", expanded=True):
    df_tabla = df.dropna(subset=['Turno']).copy()
    
    def resaltar_alertas(row):
        minutos = pd.to_numeric(row['Tiempo Perdido (min)'], errors='coerce')
        obs = str(row['Observaciones']).strip()
        
        if minutos > 45:
            return ['background-color: #fee2e2; color: #991b1b'] * len(row) # Rojo
        elif minutos > 15:
            return ['background-color: #ffedd5; color: #c2410c'] * len(row) # Naranja
        elif minutos > 0:
            return ['background-color: #fef08a; color: #854d0e'] * len(row) # Amarillo
        elif obs != "" and obs != "None" and obs != "nan":
            return ['background-color: #e0f2fe; color: #075985'] * len(row) # Azul claro
            
        return [''] * len(row)
    
    # --- DICCIONARIO DE FORMATO ---
    formato_columnas = {
        "Hora": "{:.0f}",
        "Operarios": "{:.0f}",
        "Producción Real": "{:,.0f}",
        "Meta por Hora": "{:,.0f}",
        "Tiempo Perdido (min)": "{:,.0f}",
        "Acumulado Real": "{:,.0f}",
        "Acumulado Meta": "{:,.0f}"
    }
    
    # Colores y formato de números
    tabla_formateada = (
        df_tabla.style
        .apply(resaltar_alertas, axis=1)
        .format(formato_columnas, na_rep="") # oculta textos como 'NaN'
    )
    
    st.dataframe(tabla_formateada, use_container_width=True)

# --- BOTÓN DE DESCARGA EXCEL ---
st.sidebar.markdown("---")
st.sidebar.subheader("📥 Exportar Datos")
@st.cache_data
def convertir_df(df_export):
    # Exportamos solo los datos reales
    return df_export.dropna(subset=['Turno']).to_csv(index=False).encode('utf-8')

csv = convertir_df(df)
st.sidebar.download_button(
    label="Descargar CSV",
    data=csv,
    file_name=f"reporte_{planta_seleccionada}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
    mime="text/csv",
)
