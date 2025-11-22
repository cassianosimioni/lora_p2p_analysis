import streamlit as st

st.set_page_config(
    page_title="Portal de Ferramentas",
    page_icon="🛠️",
    layout="centered"
)

st.title("🛠️ Portal de Ferramentas")
st.markdown("Selecione a ferramenta que deseja utilizar:")

st.divider()

# Criando 3 colunas para os botões
col1, col2, col3 = st.columns(3)

# --- Coluna 1: Triangulação V1 ---
with col1:
    st.info("Triangulação (Legacy)")
    # Botão renomeado
    if st.button("Algoritmo Triangulação P2P v1", use_container_width=True):
        st.switch_page("pages/1_Versao_1.py")
    st.caption("Algoritmo original (Cálculo Inteiro).")

# --- Coluna 2: Triangulação V2 ---
with col2:
    st.success("Triangulação (Estável)")
    # Botão renomeado e mantido como primary para destaque
    if st.button("Algoritmo Triangulação P2P v2", type="primary", use_container_width=True):
        st.switch_page("pages/2_Versao_2.py")
    st.caption("Algoritmo otimizado (Precisão Float).")

# --- Coluna 3: Diagnóstico Bateria ---
with col3:
    st.warning("Diagnóstico Vida Útil") # Usei warning para dar uma cor diferente (amarelo/laranja)
    # Novo botão solicitado
    if st.button("Diagnóstico Bateria A40B v3", use_container_width=True):
        st.switch_page("pages/bateriaA40.py")
    st.caption("Análise específica para device A40B v3.")

st.divider()
st.caption("Desenvolvido para análise de pacotes LoRa P2P e diagnósticos de hardware - Devices Maxtrack")