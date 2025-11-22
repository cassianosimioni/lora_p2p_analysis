import streamlit as st
import json
from datetime import datetime, timedelta
import time

# --- Configuração da Página ---
st.set_page_config(
    page_title="Diagnóstico de Vida Útil - Rastreador A40",
    page_icon="🔋",
    layout="wide"
)

# --- Constantes do Hardware (Modelo A40 Primário) ---
BATTERY_CAPACITY_NOMINAL = 1850  # mAh
EFFICIENCY_FACTOR = 0.85         # 85% (Margem para picos e autodescarga)
BATTERY_CAPACITY_REAL = BATTERY_CAPACITY_NOMINAL * EFFICIENCY_FACTOR # 1572.5 mAh

# --- Funções Auxiliares ---

def format_duration(seconds: int) -> str:
    """Formata segundos em H:M:S legível."""
    if seconds < 0: seconds = 0
    return str(timedelta(seconds=int(seconds))).split('.')[0]

def process_packet_data(packet: dict):
    """Extrai e calcula os dados cruciais do JSON com tratamento de tipos."""
    try:
        data = packet.get('data', {})
        diag = data['accessories'][0]['diagnostic']
        
        # --- ÁREA DE CORREÇÃO (Blindagem contra Strings) ---
        # Converte explicitamente para float/int caso venha como texto "12345" no JSON
        
        # 1. Timestamp e Serial
        raw_ts = data.get('deviceDateTime', time.time())
        device_ts = float(raw_ts) 
        serial = packet.get('serial', 'Desconhecido')
        
        # 2. Dados Operacionais (Forçando conversão para evitar o erro 'str object')
        interval_total_use_mas = float(diag['battery']['intervalTotalUse'])
        uptime_seconds = float(data['flags']['deviceInfo']['uptime'])
        sleep_ms = float(diag['core']['intervalSleep'])
        
        # --- FIM DA ÁREA DE CORREÇÃO ---

        # Cálculos
        sleep_seconds = sleep_ms / 1000.0
        active_seconds = uptime_seconds - sleep_seconds

        # 2. Cálculos da Bateria (Matemática do Coulomb Counting)
        used_mah = interval_total_use_mas / 3600.0
        remaining_mah = BATTERY_CAPACITY_REAL - used_mah
        
        # Travas de segurança
        remaining_mah = max(0.0, remaining_mah)
        
        pct_used = (used_mah / BATTERY_CAPACITY_REAL) * 100.0
        pct_remaining = (remaining_mah / BATTERY_CAPACITY_REAL) * 100.0

        # 3. Cálculo de Predição (Data de Esgotamento)
        uptime_hours = uptime_seconds / 3600.0
        prediction_data = None

        if uptime_hours > 0.1 and used_mah > 0:
            # mAh consumidos por hora de operação
            hourly_rate_mah = used_mah / uptime_hours
            
            # Quantas horas restam nesse ritmo?
            hours_left = remaining_mah / hourly_rate_mah
            
            # Data atual do dispositivo + horas restantes
            device_dt = datetime.fromtimestamp(device_ts)
            estimated_end_date = device_dt + timedelta(hours=hours_left)
            
            prediction_data = {
                'hourly_rate': hourly_rate_mah,
                'hours_left': hours_left,
                'end_date': estimated_end_date.strftime("%d/%m/%Y às %H:%M"),
                'days_left': hours_left / 24.0
            }
            
        return {
            'serial': serial,
            'device_ts': datetime.fromtimestamp(device_ts).strftime("%d/%m/%Y %H:%M:%S"),
            'uptime_str': format_duration(uptime_seconds),
            'sleep_str': format_duration(sleep_seconds),
            'active_str': format_duration(active_seconds),
            'sleep_pct': (sleep_seconds / uptime_seconds) * 100 if uptime_seconds > 0 else 0,
            'used_mah': used_mah,
            'remaining_mah': remaining_mah,
            'pct_used': pct_used,
            'pct_remaining': pct_remaining,
            'prediction': prediction_data
        }

    except (KeyError, IndexError, TypeError, ValueError) as e:
        st.error(f"Erro ao processar estrutura do JSON: {e}")
        st.caption(f"Dica de Debug: O erro ocorreu ao tentar ler o campo que causou {type(e).__name__}")
        return None

# --- Interface do Streamlit ---

st.title("🔋 Diagnóstico Avançado de Bateria (Li-MnO2 P2P)")

# 1. O Visual Rico do Expander (Mantido)
with st.expander("ℹ️ Parâmetros da Análise (A40)", expanded=False):
    st.info(f"""
    - **Capacidade Nominal:** {BATTERY_CAPACITY_NOMINAL} mAh
    - **Fator de Eficiência:** {int(EFFICIENCY_FACTOR*100)}% (Considerando autodescarga e picos de corrente)
    - **Capacidade Real Considerada:** {BATTERY_CAPACITY_REAL:.1f} mAh
    - **Método:** Contagem de Cargas (Coulomb Counting) usando o contador persistente `intervalTotalUse`.
    """)

# 2. Formulário com Botão (Funcionalidade Nova)
with st.form("input_form"):
    st.markdown("Cole o pacote JSON do rastreador abaixo e clique em **Verificar**.")
    json_input = st.text_area("Payload JSON:", height=200, help="Cole o objeto JSON completo iniciado por {")
    
    # O botão que impede o refresh automático
    submitted = st.form_submit_button("🔍 Verificar Bateria e Vida Útil")

# 3. Exibição dos Resultados (Visual Rico Restaurado)
if submitted and json_input:
    try:
        packet_raw = json.loads(json_input)
        results = process_packet_data(packet_raw)

        if results:
            st.divider()
            
            # Cabeçalho com dados básicos
            col_head1, col_head2, col_head3 = st.columns(3)
            col_head1.metric("Serial do Dispositivo", results['serial'])
            col_head2.metric("Data do Pacote (Device)", results['device_ts'])
            col_head3.metric("Tempo Total Ligado (Uptime)", results['uptime_str'])
            
            st.divider()

            # Seção 1: Perfil Operacional (Sleep vs Ativo)
            st.subheader("1. Perfil Operacional")
            c1, c2, c3 = st.columns(3)
            c1.metric("Tempo em Sleep (Dormindo)", results['sleep_str'], delta=f"{results['sleep_pct']:.1f}% do tempo")
            c2.metric("Tempo Ativo (Acordado)", results['active_str'])
            c3.info("Dispositivos descartáveis devem passar a maior parte do tempo em Sleep para durar anos.")

            # Seção 2: Análise Profunda da Bateria
            st.subheader(f"2. Saúde da Bateria (Base: {BATTERY_CAPACITY_REAL:.1f} mAh Reais)")
            
            # Barra de progresso visual
            st.progress(int(results['pct_remaining']), text=f"Bateria Restante Estimada: {results['pct_remaining']:.2f}%")

            b1, b2, b3 = st.columns(3)
            
            b1.metric(
                label="Já Consumido (Gasto)",
                value=f"{results['used_mah']:.2f} mAh",
                delta=f"-{results['pct_used']:.2f}%",
                delta_color="inverse"
            )
            
            b2.metric(
                label="Disponível para Uso",
                value=f"{results['remaining_mah']:.2f} mAh",
                value_help="Capacidade Real - Consumido"
            )
            
            # Seção 3: Predição de Término (Com o visual de alerta original)
            st.subheader("3. Predição de Esgotamento")
            
            pred = results['prediction']
            if pred:
                p1, p2 = st.columns([2, 1])
                
                with p1:
                    st.error(f"### Data Estimada do Fim: {pred['end_date']}")
                    st.caption(f"Faltam aproximadamente **{pred['days_left']:.1f} dias** ({int(pred['hours_left'])} horas).")
                
                with p2:
                    st.metric(
                        "Ritmo de Consumo Atual", 
                        f"{pred['hourly_rate']:.4f} mAh/h",
                        help="Média de consumo por hora baseada no uptime atual."
                    )
            else:
                st.warning("Não há dados suficientes de tempo/consumo para gerar uma predição confiável ainda.")

    except json.JSONDecodeError:
        st.error("Erro: O texto colado não é um JSON válido. Verifique a formatação.")

elif not json_input and submitted:
    st.warning("Por favor, cole o JSON antes de clicar em verificar.")