import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import time
import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Monitor de Producción", page_icon="🏭", layout="wide")

# --- 2. SISTEMA DE SEGURIDAD CON BOTÓN ---
def check_password():
    if st.session_state.get("password_correct", False):
        if "login_time" in st.session_state:
            tiempo_transcurrido = time.time() - st.session_state["login_time"]
            if tiempo_transcurrido <= 3600:
                return True 
            else:
                st.session_state["password_correct"] = False
                st.warning("⏱️ La sesión ha expirado por inactividad (1 hora). Por favor, ingresa de nuevo.")

    st.title("🔒 Acceso Restringido")
    st.markdown("Por favor, ingresa la clave para ver el monitor de producción.")
    
    with st.form("login_form"):
        pwd = st.text_input("Contraseña:", type="password")
        submitted = st.form_submit_button("Ingresar al Monitor")
        
        # Procesa la clave
        if submitted:
            if pwd == st.secrets["auth"]["password"]:
                st.session_state["password_correct"] = True
                st.session_state["login_time"] = time.time()
                st.rerun()
            else:
                st.error("😕 Contraseña incorrecta. Intenta de nuevo.")
                
    st.stop()

check_password()

# --- 3. AUTO-REFRESCO DE LA PÁGINA ---
st_autorefresh(interval=300000, limit=None, key="data_refresh")

# =====================================================================
# --- 4. DASHBOARD PRINCIPAL ---
# =====================================================================

# --- CONEXIÓN A BASE DE DATOS ---
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Error de conexión a la base de datos: {e}")
    st.stop()

# --- BARRA LATERAL (MENÚ Y CONFIGURACIÓN) ---
st.sidebar.title("⚙️ Controles")
planta_seleccionada = st.sidebar.radio("Sede:", ["Sopó"])

# --- METAS ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Configurar Metas por Hora")
with st.sidebar.expander("Ajustar metas actuales", expanded=False):
    st.caption("Modifica estos valores para recalcular las métricas y gráficas.")
    meta_atlanta1 = st.number_input("Atlanta 1", value=1200, step=10)
    meta_atlanta2 = st.number_input("Atlanta 2", value=1700, step=10)
    meta_litro = st.number_input("Litro", value=800, step=10)
    meta_vertical1 = st.number_input("Vertical 1", value=1400, step=10)
    meta_vertical2 = st.number_input("Vertical 2", value=1400, step=10)
    meta_vertical3 = st.number_input("Vertical 3", value=1400, step=10)

METAS_POR_LINEA = {
    "Atlanta 1": meta_atlanta1,
    "Atlanta 2": meta_atlanta2,
    "Litro": meta_litro,
    "Vertical 1": meta_vertical1,
    "Vertical 2": meta_vertical2,
    "Vertical 3": meta_vertical3
}

# --- FUNCIÓN PARA OBTENER DATOS (ÚLTIMOS 7 DÍAS REALES) ---
@st.cache_data(ttl=60) # Refresca el caché en 60 segundos
def obtener_datos_crudos(planta):
    query = f"""
    SELECT 
        proceso AS "Proceso",
        operador AS "Operador",
        turno AS "Turno",
        cantidad_operarios AS "Operarios",
        produccion_real AS "Producción Real",
        tiempo_perdida_min AS "Tiempo Perdido (min)",
        observaciones AS "Observaciones",
        fecha_registro,
        hora_inicio
    FROM prod.registro_produccion 
    WHERE planta = '{planta}'
      AND fecha_registro >= CURRENT_DATE - INTERVAL '7 days'
      AND deleted_at IS NULL
    ORDER BY fecha_registro ASC, hora_inicio ASC;
    """
    df = conn.query(query, ttl=0)
    return df

df_crudo = obtener_datos_crudos(planta_seleccionada)

# --- PROCESAMIENTO BASE ---
if df_crudo.empty:
    df_completo = pd.DataFrame(columns=[
        "Fecha_Hora", "Hora", "Proceso", "Operador", "Turno", "Operarios", 
        "Producción Real", "Tiempo Perdido (min)", "Observaciones"
    ])
else:
    df_completo = df_crudo.copy()
    # 1. Crear la columna de Fecha_Hora para que Plotly entienda la línea de tiempo
    df_completo["Fecha_Hora"] = pd.to_datetime(df_completo["fecha_registro"].astype(str) + " " + df_completo["hora_inicio"].astype(str), errors='coerce')
    # 2. Conservamos la hora numérica para las alertas de huecos
    df_completo["Hora"] = df_completo["Fecha_Hora"].dt.hour
    
    df_completo["Meta por Hora"] = df_completo["Proceso"].map(METAS_POR_LINEA).fillna(0)
    df_completo["Tiempo Perdido (min)"] = pd.to_numeric(df_completo["Tiempo Perdido (min)"], errors='coerce').fillna(0)

# --- FILTROS ADICIONALES (LÍNEA Y TURNO) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Filtros de Visualización")

lineas_disponibles = ["Todas"] + list(METAS_POR_LINEA.keys())
linea_seleccionada = st.sidebar.selectbox("Seleccione la línea:", lineas_disponibles)

turnos_disponibles = {
    "Todos": "Todos",
    "Turno 1 (06:00 - 14:00)": "Turno 1",
    "Turno 2 (14:00 - 22:00)": "Turno 2",
    "Turno 3 (22:00 - 06:00)": "Turno 3"
}
turno_seleccionado = st.sidebar.selectbox("Seleccione el turno:", list(turnos_disponibles.keys()))
turno_real = turnos_disponibles[turno_seleccionado]

# Aplicar filtros
df = df_completo.copy()
if not df.empty:
    if linea_seleccionada != "Todas":
        df = df[df["Proceso"] == linea_seleccionada]
    if turno_real != "Todos":
        df = df[df["Turno"] == turno_real]
    
    # Recalcular Acumulados
    df["Acumulado Real"] = df["Producción Real"].fillna(0).cumsum()
    df["Acumulado Meta"] = df["Meta por Hora"].fillna(0).cumsum()

# --- DEFINIR RANGO DE "HOY" Y "ÚLTIMAS 24H" ---
ahora = pd.Timestamp.now()
limite_24h = ahora - pd.Timedelta(hours=24)
hoy_str = str(datetime.date.today())
inicio_hoy = f"{hoy_str} 00:00:00"
fin_hoy = f"{hoy_str} 23:59:59"

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
    st.info("No hay registros de producción válidos en el sistema.")
    st.stop()

# --- ALERTAS Y HUECOS (SOLO ÚLTIMAS 24 HORAS) ---
# 1. Alerta de Huecos (Datos Faltantes solo en las últimas 24h)
df_24h = df[df["Fecha_Hora"] >= limite_24h].copy()

if not df_24h.empty:
    horas_validas = df_24h["Hora"].dropna()
    if not horas_validas.empty:
        hora_min = int(horas_validas.min())
        hora_max = int(horas_validas.max())
        horas_esperadas = list(range(hora_min, hora_max + 1))
        horas_registradas = horas_validas.astype(int).unique().tolist()
        horas_faltantes = [h for h in horas_esperadas if h not in horas_registradas]
        
        if horas_faltantes:
            st.warning(f"⚠️ **ALERTA DE DATOS FALTANTES (Últimas 24h):** No hay registros para las horas: **{horas_faltantes}**.")

# 2. Alerta de Paros (Solo paros en las últimas 24h)
df_alertas = df_24h.dropna(subset=['Turno']).copy()
df_alertas = df_alertas[df_alertas["Tiempo Perdido (min)"] > 0]

if not df_alertas.empty:
    st.error(f"⚠️ **ATENCIÓN: Se han reportado {len(df_alertas)} paros en las últimas 24 horas.**")
    
    for index, fila in df_alertas.iterrows():
        minutos = fila['Tiempo Perdido (min)']
        if minutos <= 15:
            nivel, icono, color_func = "Leve", "🟡", st.warning
        elif minutos <= 45:
            nivel, icono, color_func = "Moderado", "🟠", st.warning
        else:
            nivel, icono, color_func = "Crítico", "🔴", st.error

        hora_formateada = fila['Fecha_Hora'].strftime("%d/%m %H:%M")
        with st.expander(f"{icono} Paro {nivel} a las {hora_formateada} - {fila['Proceso']} ({fila['Turno']})"):
            color_func(f"**Impacto {nivel}:** {minutos:,.0f} minutos perdidos.")
            st.write(f"**Operador a cargo:** {fila['Operador']}")
            st.write(f"**Detalle:** {fila['Observaciones']}")

# --- MÉTRICAS (BASADAS EN LAS ÚLTIMAS 24 HORAS PARA NO DISTORSIONAR) ---
st.markdown("### Resumen (Últimas 24 Horas)")
col1, col2, col3, col4 = st.columns(4)

total_real = df_24h["Producción Real"].sum()
total_meta = df_24h["Meta por Hora"].sum()
total_perdida = df_24h["Tiempo Perdido (min)"].sum()
eficiencia = (total_real / total_meta * 100) if total_meta > 0 else 0

col1.metric("Producción Total", f"{total_real:,.0f} unid")
col2.metric("Meta Acumulada", f"{total_meta:,.0f} unid")
col3.metric("Tiempo Total de Paro", f"{total_perdida:,.0f} min", delta="- Inactividad", delta_color="inverse")
col4.metric("Eficiencia (OEE aprox)", f"{eficiencia:.1f}%", f"{eficiencia - 100:.1f}%")

st.markdown("---")

# --- GRÁFICAS PRINCIPALES (HISTÓRICO COMPLETO PERO ENFOCADO EN HOY) ---
col_grafica1, col_grafica2 = st.columns(2)

with col_grafica1:
    st.subheader("📊 Producción vs Meta")
    fig_hora = go.Figure()
    
    fig_hora.add_trace(go.Bar(
        x=df["Fecha_Hora"], y=df["Producción Real"],
        name="Producción Real", marker_color="#3b82f6"
    ))
    fig_hora.add_trace(go.Scatter(
        x=df["Fecha_Hora"], y=df["Meta por Hora"],
        name="Meta por Hora", mode="lines+markers",
        line=dict(color="#10b981", width=3, dash="dash"),
        connectgaps=False
    ))
    
    # Zoom en el rango de HOY, con barra inferior para explorar atrás
    fig_hora.update_layout(
        margin=dict(t=20, b=20, l=20, r=20), 
        hovermode="x unified", 
        barmode='group',
        xaxis=dict(
            range=[inicio_hoy, fin_hoy], 
            rangeslider=dict(visible=True),
            type="date",
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="Hoy", step="day", stepmode="todate"),
                    dict(count=3, label="3 Días", step="day", stepmode="backward"),
                    dict(step="all", label="Semana")
                ])
            )
        )
    )
    st.plotly_chart(fig_hora, use_container_width=True)

with col_grafica2:
    st.subheader("⏱️ Control de Tiempos de Paro")
    
    fig_averias = px.area(
        df, x="Fecha_Hora", y="Tiempo Perdido (min)",
        color_discrete_sequence=["#ef4444"], 
        labels={"Tiempo Perdido (min)": "Minutos Inactivos"}
    )
    
    # Mismo zoom para que ambas gráficas se vean alineadas
    fig_averias.update_traces(connectgaps=False) 
    fig_averias.update_layout(
        margin=dict(t=20, b=20, l=20, r=20), 
        hovermode="x unified",
        xaxis=dict(
            range=[inicio_hoy, fin_hoy],
            rangeslider=dict(visible=True),
            type="date"
        )
    )
    st.plotly_chart(fig_averias, use_container_width=True)

# --- TABLA DE DETALLES ---
with st.expander("Ver tabla de registros detallada (Todo el historial disponible)", expanded=False):
    df_tabla = df.dropna(subset=['Turno']).copy()
    
    # Formatear la fecha/hora visualmente en la tabla
    df_tabla['Fecha y Hora'] = df_tabla['Fecha_Hora'].dt.strftime('%d/%m/%Y %H:%M')
    
    # Reordenar para poner Fecha y Hora al inicio
    columnas_mostrar = ['Fecha y Hora', 'Proceso', 'Operador', 'Turno', 'Operarios', 
                       'Producción Real', 'Meta por Hora', 'Tiempo Perdido (min)', 'Observaciones']
    df_tabla = df_tabla[columnas_mostrar]
    
    def resaltar_alertas(row):
        minutos = pd.to_numeric(row['Tiempo Perdido (min)'], errors='coerce')
        obs = str(row['Observaciones']).strip()
        
        if minutos > 45: return ['background-color: #fee2e2; color: #991b1b'] * len(row)
        elif minutos > 15: return ['background-color: #ffedd5; color: #c2410c'] * len(row)
        elif minutos > 0: return ['background-color: #fef08a; color: #854d0e'] * len(row)
        elif obs != "" and obs != "None" and obs != "nan": return ['background-color: #e0f2fe; color: #075985'] * len(row)
        return [''] * len(row)
    
    formato_columnas = {
        "Operarios": "{:.0f}",
        "Producción Real": "{:,.0f}",
        "Meta por Hora": "{:,.0f}",
        "Tiempo Perdido (min)": "{:,.0f}"
    }
    
    tabla_formateada = (
        df_tabla.style
        .apply(resaltar_alertas, axis=1)
        .format(formato_columnas, na_rep="")
    )
    st.dataframe(tabla_formateada, use_container_width=True)

# --- BOTÓN DE DESCARGA EXCEL ---
st.sidebar.markdown("---")
st.sidebar.subheader("📥 Exportar Datos")
@st.cache_data
def convertir_df(df_export):
    return df_export.dropna(subset=['Turno']).to_csv(index=False).encode('utf-8')

csv = convertir_df(df)
st.sidebar.download_button(
    label="Descargar CSV (Histórico Total)",
    data=csv,
    file_name=f"reporte_produccion_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
    mime="text/csv",
)
