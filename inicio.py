import streamlit as st
import os

st.error("🔍 MODO DEBUG ATIVADO")

# 1. Verifica se a pasta pages existe (seja qual for o case)
pastas_raiz = os.listdir('.')
if 'pages' in pastas_raiz:
    st.success("✅ Pasta 'pages' encontrada!")
    
    # 2. Lista EXATAMENTE como os arquivos estão nomeados lá dentro
    arquivos = os.listdir('pages')
    st.write("📂 Arquivos encontrados dentro de 'pages':")
    st.code(arquivos) # Vai mostrar a lista exata, ex: ['2_versao_2.py', ...]
    
    # 3. Teste de string
    arquivo_alvo = "2_Versao_2.py" # Como está no seu switch_page
    if arquivo_alvo in arquivos:
        st.success(f"✅ O arquivo '{arquivo_alvo}' bate perfeitamente!")
    else:
        st.error(f"🚨 ERRO: Você está chamando '{arquivo_alvo}', mas o arquivo real tem outro nome (veja a lista acima)!")

else:
    st.error(f"🚨 A pasta 'pages' não foi encontrada. O que existe na raiz é: {pastas_raiz}")

st.divider()

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