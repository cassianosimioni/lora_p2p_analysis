import streamlit as st

# 1. Mudei para layout="wide" para dar espaço aos botões ficarem em uma linha
st.set_page_config(
    page_title="Portal de Ferramentas",
    page_icon="🛠️",
    layout="wide" 
)

st.title("🛠️ Portal de Ferramentas")
st.markdown("Selecione a ferramenta que deseja utilizar:")

st.divider()

# Criando 3 colunas
col1, col2, col3 = st.columns(3)

# --- Coluna 1: Triangulação V1 ---
with col1:
    # Substituí st.info por HTML para poder CENTRALIZAR o texto e manter a cor azul
    st.markdown("""
        <div style="background-color: #e7f5ff; color: #004a77; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 10px;">
            Triangulação (Legacy)
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("Algoritmo Triangulação P2P v1", use_container_width=True):
        st.switch_page("pages/1_Versao_1.py")
    
    # Caption centralizada e sem ponto final
    st.markdown("<p style='text-align: center; font-size: 0.9em; color: gray;'>Algoritmo original com cálculo inteiro</p>", unsafe_allow_html=True)

# --- Coluna 2: Triangulação V2 ---
with col2:
    # Estilo verde para simular o st.success
    st.markdown("""
        <div style="background-color: #d4edda; color: #155724; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 10px;">
            Triangulação (Estável)
        </div>
    """, unsafe_allow_html=True)

    if st.button("Algoritmo Triangulação P2P v2", type="primary", use_container_width=True):
        st.switch_page("pages/2_Versao_2.py")
        
    # Caption centralizada e sem ponto final
    st.markdown("<p style='text-align: center; font-size: 0.9em; color: gray;'>Algoritmo otimizado com precisão float</p>", unsafe_allow_html=True)

# --- Coluna 3: Diagnóstico Bateria ---
with col3:
    # Estilo amarelo para simular o st.warning/Life
    st.markdown("""
        <div style="background-color: #fff3cd; color: #856404; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 10px;">
            Diagnóstico Vida Útil
        </div>
    """, unsafe_allow_html=True)

    if st.button("Diagnóstico Bateria A40B v3", use_container_width=True):
        st.switch_page("pages/bateriaA40.py")
        
    # Caption centralizada e sem ponto final
    st.markdown("<p style='text-align: center; font-size: 0.9em; color: gray;'>Análise específica para device A40B</p>", unsafe_allow_html=True)

st.divider()
st.caption("Desenvolvido para análise de pacotes LoRa P2P e diagnósticos de hardware - Devices Maxtrack")