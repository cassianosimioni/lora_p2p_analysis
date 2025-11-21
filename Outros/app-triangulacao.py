import streamlit as st
import json
import math
import folium
from streamlit_folium import st_folium

# ==========================================
# 1. LÓGICA MATEMÁTICA
# ==========================================

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def process_triangulation(gateway_positions_raw):
    MAX_DISTANCE_KM = 5.0
    GATEWAY_COORDINATE_DIVISOR = 10000000.0

    valid_gateways = []
    sum_lat = 0.0
    sum_lon = 0.0

    # Extração de dados
    for data in gateway_positions_raw:
        try:
            if isinstance(data, str):
                data = json.loads(data)
            
            gateway_lat_raw = data['data']['gatewayPosition'][0]['latitude']
            gateway_lon_raw = data['data']['gatewayPosition'][0]['longitude']
            rssi = data['data']['loraRadio']['RSSI']
            fix_state = data['data']['gatewayGps']['fixState']
            
            lat = gateway_lat_raw / GATEWAY_COORDINATE_DIVISOR
            lon = gateway_lon_raw / GATEWAY_COORDINATE_DIVISOR

            if fix_state == 1:
                valid_gateways.append({'lat': lat, 'lon': lon, 'rssi': rssi})
                sum_lat += lat
                sum_lon += lon
            
        except Exception as e:
            continue

    if not valid_gateways:
        return None, "Nenhum gateway válido com GPS Fix encontrado."

    # Filtro de Outliers
    avg_lat = sum_lat / len(valid_gateways)
    avg_lon = sum_lon / len(valid_gateways)
    filtered_gateways = []
    
    for gateway in valid_gateways:
        dist = calculate_haversine_distance(gateway['lat'], gateway['lon'], avg_lat, avg_lon)
        if dist < MAX_DISTANCE_KM:
            filtered_gateways.append(gateway)

    if not filtered_gateways:
        return None, "Todos os gateways foram descartados (outliers)."

    # Cálculo Ponderado
    latitude_weighted = 0.0
    longitude_weighted = 0.0
    total_power_weight = 0.0
    max_rssi = -200

    for gateway in filtered_gateways:
        power_weight = 10**(gateway['rssi'] / 10.0)
        latitude_weighted += (gateway['lat'] * power_weight)
        longitude_weighted += (gateway['lon'] * power_weight)
        total_power_weight += power_weight
        if gateway['rssi'] > max_rssi:
            max_rssi = gateway['rssi']
            
    estimated_lat = latitude_weighted / total_power_weight
    estimated_lon = longitude_weighted / total_power_weight
    
    rssi_abs = abs(max_rssi)
    estimated_error = rssi_abs - int(rssi_abs * 0.15)
    
    return {
        "lat": estimated_lat,
        "lon": estimated_lon,
        "error_radius": estimated_error,
        "gateways_used": filtered_gateways,
        "max_rssi": max_rssi
    }, None

# ==========================================
# 2. INTERFACE WEB (CORRIGIDA)
# ==========================================

st.set_page_config(page_title="Triangulação LoRa Visual", layout="wide")

# Inicializa a memória de sessão para o resultado não sumir
if 'triangulation_result' not in st.session_state:
    st.session_state['triangulation_result'] = None
if 'error_message' not in st.session_state:
    st.session_state['error_message'] = None

st.title("📡 Visualizador de Triangulação LoRa")
st.markdown("""
Cole abaixo o JSON dos pacotes recebidos (lista `[...]` ou objetos).
O sistema aplicará o algoritmo de **Triangulação Ponderada**.
""")

input_text = st.text_area("Cole o JSON aqui:", height=150, placeholder='[{"data": {...}}, {"data":{...}}]')

# Botão apenas dispara o processamento e salva na sessão
if st.button("📍 Calcular e Plotar Mapa"):
    if not input_text.strip():
        st.session_state['error_message'] = "Por favor, insira os dados JSON."
        st.session_state['triangulation_result'] = None
    else:
        try:
            raw_data = input_text.strip()
            if not raw_data.startswith("["):
                raw_lines = raw_data.split('\n')
                parsed_data = [json.loads(line) for line in raw_lines if line.strip()]
            else:
                parsed_data = json.loads(raw_data)

            result, error_msg = process_triangulation(parsed_data)
            
            # Salva na sessão
            st.session_state['triangulation_result'] = result
            st.session_state['error_message'] = error_msg

        except json.JSONDecodeError:
            st.session_state['error_message'] = "Erro no formato JSON. Verifique aspas e vírgulas."
            st.session_state['triangulation_result'] = None
        except Exception as e:
            st.session_state['error_message'] = f"Erro inesperado: {e}"
            st.session_state['triangulation_result'] = None

# --- ÁREA DE EXIBIÇÃO (FORA DO BLOCO DO BOTÃO) ---

if st.session_state['error_message']:
    st.error(st.session_state['error_message'])

if st.session_state['triangulation_result']:
    result = st.session_state['triangulation_result']
    
    # Métricas
    col1, col2, col3 = st.columns(3)
    col1.metric("Latitude Estimada", f"{result['lat']:.6f}")
    col2.metric("Longitude Estimada", f"{result['lon']:.6f}")
    col3.metric("Raio de Erro", f"{result['error_radius']} m", delta_color="inverse")
    
    st.success(f"Cálculo realizado com sucesso usando {len(result['gateways_used'])} gateways.")

    # --- CRIAÇÃO DO MAPA ---
    # Criamos o mapa
    m = folium.Map(location=[result['lat'], result['lon']], zoom_start=16)

    # 1. Gateways (Pontos Azuis)
    for gw in result['gateways_used']:
        folium.Marker(
            [gw['lat'], gw['lon']],
            tooltip=f"Gateway (RSSI: {gw['rssi']}dBm)",
            # Usando ícone padrão (info-sign) para garantir compatibilidade
            icon=folium.Icon(color="blue", icon="info-sign") 
        ).add_to(m)

    # 2. Raio de Erro (Círculo Vermelho)
    folium.Circle(
        location=[result['lat'], result['lon']],
        radius=float(result['error_radius']),
        color="red",
        weight=2,
        fill=True,
        fill_color="red",
        fill_opacity=0.2,
        tooltip=f"Margem de Erro: {result['error_radius']}m"
    ).add_to(m)

    # 3. Alvo (Ponto Vermelho)
    folium.Marker(
        [result['lat'], result['lon']],
        tooltip="Posição Estimada",
        icon=folium.Icon(color="red", icon="star")
    ).add_to(m)

    # --- EXIBIÇÃO DO MAPA ---
    # use_container_width=True: Ajusta à tela
    # key="mapa_resultado": Impede que o mapa suma ou pisque
    st.subheader("🗺️ Mapa de Localização")
    st_folium(m, height=500, use_container_width=True, key="mapa_resultado")
    
    # JSON de Saída
    st.subheader("📤 JSON para Super-Posição")
    output_json = {
        "lat": result['lat'],
        "lon": result['lon'],
        "error": result['error_radius']
    }
    st.code(json.dumps(output_json, indent=4), language="json")