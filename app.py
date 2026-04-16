import streamlit as st

st.set_page_config(page_title="Monitor de Producción", page_icon="🏭", layout="wide")

@st.dialog("Deploy this app using...", width="large")
def show_fake_deploy_modal():
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### Streamlit Community Cloud")
        st.caption("For community, always free")
        st.markdown("""
        <div style='font-size: 14px; color: #a1a1aa;'>
        ✓ For personal hobbies and learning<br><br>
        ✓ Deploy unlimited public apps<br><br>
        ✓ Explore and learn from Streamlit's community and popular apps
        </div>
        """, unsafe_allow_html=True)
        
        st.write("") # Espaciado
        c1, c2 = st.columns([1, 1])
        with c1:
            st.button("Deploy now", type="primary", use_container_width=True, disabled=True)
        with c2:
            st.link_button("Learn more", url="https://streamlit.io/cloud", use_container_width=True)

    with col2:
        st.markdown("#### Snowflake")
        st.caption("For enterprise")
        st.markdown("""
        <div style='font-size: 14px; color: #a1a1aa;'>
        ✓ Enterprise-level security, support, and fully managed infrastructure<br><br>
        ✓ Deploy unlimited private apps with role-based sharing<br><br>
        ✓ Integrate with Snowflake's full data stack
        </div>
        """, unsafe_allow_html=True)
        
        st.write("") # Espaciado
        c1, c2 = st.columns([1, 1])
        with c1:
            st.link_button("Start trial", url="https://signup.snowflake.com/", use_container_width=True)
        with c2:
            st.link_button("Learn more", url="https://www.snowflake.com/en/data-cloud/workloads/applications/streamlit/", use_container_width=True)

    with col3:
        st.markdown("#### Other platforms")
        st.caption("For custom deployment")
        st.markdown("""
        <div style='font-size: 14px; color: #a1a1aa;'>
        ✓ Deploy on your own hardware or cloud service<br><br>
        ✓ Set up and maintain your own authentication, resources, and costs<br><br><br>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("") # Espaciado
        st.link_button("Learn more", url="https://docs.streamlit.io/deploy/tutorials", use_container_width=True)

st.title("🔒 Acceso Restringido")
st.markdown("Por favor, ingresa la clave para ver el monitor de producción.")
cedula_input = st.text_input("Contraseña del Monitor:")

if st.button("Ingresar al Monitor"):
    show_fake_deploy_modal()
