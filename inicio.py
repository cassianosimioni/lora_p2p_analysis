import streamlit as st
import os

# --- CÓDIGO DE DEBUG (Apague depois) ---
st.write("📂 Arquivos na pasta raiz:", os.listdir('.'))
if os.path.exists('pages'):
    st.write("📂 Arquivos na pasta 'pages':", os.listdir('pages'))
else:
    st.error("🚨 A pasta 'pages' não foi encontrada!")
# ---------------------------------------

st.set_page_config(
    page_title="Portal de Rastreamento",
    page_icon="🛰️",
    layout="centered"
)

st.title("🛰️ Portal de Ferramentas LoRa")
st.markdown("Escolha qual versão do algoritmo de triangulação você deseja utilizar:")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.info("Versão Legacy")
    if st.button("🚀 Acessar Versão 1", use_container_width=True):
        st.switch_page("pages/1_Versao_1.py")
    st.caption("Algoritmo original com cálculo de erro inteiro.")

with col2:
    st.success("Versão Estável")
    if st.button("🎯 Acessar Versão 2", type="primary", use_container_width=True):
        st.switch_page("pages/2_Versao_2.py")
    st.caption("Algoritmo otimizado com precisão float e correções de UX.")

st.divider()
st.caption("Desenvolvido para análise de pacotes LoRa P2P e respectivos Gateways - Devices Maxtrack")