import streamlit as st
import json
import math
import folium
from streamlit_folium import st_folium
import pandas as pd

# ==========================================
# 1. FUNÇÕES MATEMÁTICAS (CORE BLINDADO)
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
    """
    Processa a lista de gateways, filtra outliers por distância (Cluster)
    e calcula a posição ponderada pelo RSSI (mW).
    Assume hardware GPS de alta precisão (erro ~3m).
    """
    MAX_DISTANCE_KM = 1.5
    GATEWAY_COORDINATE_DIVISOR = 10000000.0
    
    # Mapa para normalizar o Fix State (aceita int ou string)
    FIX_MAP = {
        "FS_FIX_NOT_AVAILABLE": 0, "FS_FIX_TIME_ONLY": 1,
        "FS_FIX_2D": 2, "FS_FIX_3D": 3,
        "0": 0, "1": 1, "2": 2, "3": 3
    }

    valid_gateways = []

    # --- 1. Extração e Validação ---
    for data in gateway_positions_raw:
        try:
            # Flexibilidade: aceita string JSON ou dict direto
            if isinstance(data, str): data = json.loads(data)
            
            # Acesso direto assumindo estrutura garantida do hardware
            payload = data.get('data', {})
            
            # Verifica se existe posição
            pos_list = payload.get('gatewayPosition')
            if not pos_list: continue
            gw_pos = pos_list[0]
            
            gw_gps = payload.get('gatewayGps', {})
            
            # Tratamento do Fix State
            raw_fix = gw_gps.get('fixState', 0)
            fix_state = raw_fix if isinstance(raw_fix, int) else FIX_MAP.get(str(raw_fix), 0)
            
            # Filtro Básico: Só aceita 2D ou 3D fix
            if fix_state < 2: continue

            # RSSI é obrigatório para o cálculo de peso
            lora_radio = payload.get('loraRadio', {})
            if 'RSSI' not in lora_radio: continue
            rssi = lora_radio['RSSI']

            lat = gw_pos['latitude'] / GATEWAY_COORDINATE_DIVISOR
            lon = gw_pos['longitude'] / GATEWAY_COORDINATE_DIVISOR

            valid_gateways.append({'lat': lat, 'lon': lon, 'rssi': rssi})

        except (KeyError, IndexError, ValueError, TypeError):
            # Ignora pacotes corrompidos sem quebrar o loop
            continue

    if not valid_gateways: 
        return None, "Nenhum gateway válido (Fix 2D/3D + RSSI) encontrado."

    # --- 2. Filtragem de Cluster (Centróide) ---
    # Identifica o "Líder" (quem está mais no centro da massa de gateways)
    ref_lat, ref_lon = valid_gateways[0]['lat'], valid_gateways[0]['lon']
    
    if len(valid_gateways) > 1:
        min_total_dist = float('inf')
        best_gw = None
        
        for g1 in valid_gateways:
            # Soma a distância deste gateway para todos os outros
            dist_sum = sum(calculate_haversine_distance(g1['lat'], g1['lon'], g2['lat'], g2['lon']) for g2 in valid_gateways)
            if dist_sum < min_total_dist:
                min_total_dist = dist_sum
                best_gw = g1
        
        if best_gw:
            ref_lat, ref_lon = best_gw['lat'], best_gw['lon']

    # Filtra gateways que estão muito longe do "Líder" (> 1.5km - possível reflexão atmosférica)
    filtered_gateways = [
        g for g in valid_gateways 
        if calculate_haversine_distance(g['lat'], g['lon'], ref_lat, ref_lon) < MAX_DISTANCE_KM
    ]

    if not filtered_gateways: 
        return None, "Erro de dispersão: Gateways muito distantes entre si."

    # --- 3. Cálculo Ponderado (RSSI em mW) ---
    lat_w = 0.0
    lon_w = 0.0
    total_w = 0.0
    max_rssi = -999

    for gw in filtered_gateways:
        # Transforma dBm (log) em mW (linear) para usar como peso real
        # Ex: -100dBm = 1e-10 mW / -80dBm = 1e-8 mW (peso 100x maior)
        weight = 10**(gw['rssi'] / 10.0)
        
        lat_w += gw['lat'] * weight
        lon_w += gw['lon'] * weight
        total_w += weight
        
        if gw['rssi'] > max_rssi: max_rssi = gw['rssi']

    if total_w == 0: return None, "Erro matemático: Peso zero."

    final_lat = lat_w / total_w
    final_lon = lon_w / total_w
    
    # --- 4. Cálculo da Incerteza (Raio de Erro) ---
    # RSSI mais forte = Menor erro. 
    # Fórmula baseada na física de propagação, não na imprecisão do GPS.
    rssi_abs = abs(max_rssi)
    estimated_error = rssi_abs - (rssi_abs * 0.15)
    
    # Trava de segurança: Erro nunca menor que 3m (precisão do hardware GPS)
    if estimated_error < 3.0: estimated_error = 3.0

    return {
        "lat": final_lat,
        "lon": final_lon,
        "error": estimated_error,
        "gateways_used": filtered_gateways,
        "max_rssi": max_rssi,
        "total_raw_gateways": len(valid_gateways)
    }, None

def consolidate_super_position(position_series):
    latitude_weighted = 0.0
    longitude_weighted = 0.0
    error_weighted = 0.0
    total_weight = 0.0
    
    for pos in position_series:
        lat = pos.get('lat')
        lon = pos.get('lon')
        error_radius = pos.get('error')
        
        if error_radius is None or error_radius <= 0 or lat is None or lon is None:
            continue 

        # O peso é o inverso do quadrado do erro (Estatística Bayesiana simples)
        weight = 1.0 / (error_radius ** 2)
        
        latitude_weighted += (lat * weight)
        longitude_weighted += (lon * weight)
        error_weighted += (error_radius * weight)
        total_weight += weight
        
    if total_weight == 0: return None
        
    final_lat = latitude_weighted / total_weight
    final_lon = longitude_weighted / total_weight
    final_error = error_weighted / total_weight

    return {
        "final_latitude": final_lat,
        "final_longitude": final_lon,
        "final_error_radius_m": final_error,
        "total_positions_used": len(position_series)
    }

# ==========================================
# 2. CONFIGURAÇÃO DA PÁGINA E ESTADO
# ==========================================

st.set_page_config(page_title="Sistema de Rastreamento LoRa", layout="wide", page_icon="🛰️")

if 'stored_points' not in st.session_state:
    st.session_state['stored_points'] = [] 
if 'last_triangulation' not in st.session_state:
    st.session_state['last_triangulation'] = None
if 'super_position_result' not in st.session_state:
    st.session_state['super_position_result'] = None
if 'trigger_balloons' not in st.session_state:
    st.session_state['trigger_balloons'] = False

st.title("🛰️ Normalização de Sequência & Otimização de Cluster")

tab1, tab2 = st.tabs(["📡 1. Triangulação", "🎯 2. Otimização de Cluster"])

# ==========================================
# ABA 1: TRIANGULAÇÃO
# ==========================================
with tab1:
    st.markdown("### 1. Cole o JSON do Pacote e Calcule")
    input_text = st.text_area("JSON Raw dos Gateways:", height=150, placeholder='[{"data": {...}}, ...]')

    col_btn_1, col_btn_2 = st.columns([1, 4])
    with col_btn_1:
        calc_pressed = st.button("📍 Calcular Localização", type="primary")

    if calc_pressed:
        if not input_text.strip():
            st.warning("Cole o JSON primeiro.")
        else:
            try:
                raw_data = input_text.strip()
                # Lógica robusta para aceitar JSONs quebrados ou concatenados
                if not raw_data.startswith("["):
                    # Tenta corrigir objetos colados (ex: logs de terminal)
                    raw_lines = raw_data.replace('}{', '}\n{').split('\n')
                    parsed_data = [json.loads(line) for line in raw_lines if line.strip()]
                else:
                    parsed_data = json.loads(raw_data)

                result, error_msg = process_triangulation(parsed_data)
                
                if error_msg:
                    st.error(error_msg)
                    st.session_state['last_triangulation'] = None
                else:
                    st.session_state['last_triangulation'] = result
                    st.toast('Cálculo realizado!', icon='✅')
            except Exception as e:
                st.error(f"Erro no JSON ou Processamento: {e}")

    if st.session_state['last_triangulation']:
        res = st.session_state['last_triangulation']
        
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Lat", f"{res['lat']:.8f}")
        c2.metric("Lon", f"{res['lon']:.8f}")
        c3.metric("Erro (Raio)", f"{res['error']:.2f} m")

        # Feedback visual de descarte
        discarded_count = res['total_raw_gateways'] - len(res['gateways_used'])
        if discarded_count > 0:
            st.warning(f"⚠️ Nota: {discarded_count} gateway(s) ignorado(s) (Distância ou Fix inválido).")
        else:
            st.success("Todos os gateways válidos foram utilizados.")

        with c4:
            st.write("") 
            if st.button("➕ Enviar para Clustering"):
                st.session_state['stored_points'].append(res)
                st.success(f"Adicionado! Total acumulado: {len(st.session_state['stored_points'])}")
                st.session_state['last_triangulation'] = None
                st.rerun()

        # Mapa
        m = folium.Map(location=[res['lat'], res['lon']], zoom_start=16)
        
        # Círculo de incerteza
        folium.Circle(
            location=[res['lat'], res['lon']], radius=float(res['error']),
            color="red", fill=True, fill_opacity=0.2
        ).add_to(m)
        
        # Gateways usados (Azul)
        for gw in res['gateways_used']:
            folium.Marker(
                [gw['lat'], gw['lon']],
                tooltip=f"Gateway (RSSI: {gw['rssi']}dBm)",
                icon=folium.Icon(color="blue", icon="wifi", prefix='fa') 
            ).add_to(m)

        # Posição Estimada (Vermelho)
        folium.Marker(
            [res['lat'], res['lon']], 
            tooltip="Posição Estimada",
            icon=folium.Icon(color="red", icon="star")
        ).add_to(m)
        
        st_folium(m, height=400, use_container_width=True, key="map_single")

# ==========================================
# ABA 2: OTIMIZAÇÃO DE CLUSTER (FINAL)
# ==========================================
with tab2:
    st.markdown("### 2. Consolidação de Múltiplas Estimativas")
    
    points = st.session_state['stored_points']
    count = len(points)
    
    if count == 0:
        st.info("👈 Nenhum ponto acumulado. Vá na aba 'Triangulação', calcule e adicione.")
    else:
        st.write(f"Você tem **{count}** pontos prontos para processamento.")
        
        df = pd.DataFrame(points)[['lat', 'lon', 'error']]
        with st.expander("Ver dados brutos acumulados"):
            st.dataframe(df.style.format({"lat": "{:.8f}", "lon": "{:.8f}", "error": "{:.2f}"}))
            
            if st.button("🗑️ Limpar Lista"):
                st.session_state['stored_points'] = []
                st.session_state['super_position_result'] = None
                st.session_state['trigger_balloons'] = False
                st.rerun()

        st.divider()
        
        if st.button("🎯 EXECUTAR SUPER POSIÇÃO", type="primary"):
            final_res = consolidate_super_position(points)
            
            if final_res:
                st.session_state['super_position_result'] = final_res
                st.session_state['trigger_balloons'] = True
            else:
                st.error("Erro ao consolidar dados.")

        if st.session_state['super_position_result']:
            final_res = st.session_state['super_position_result']
            
            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("Latitude Final", f"{final_res['final_latitude']:.8f}")
            fc2.metric("Longitude Final", f"{final_res['final_longitude']:.8f}")
            fc3.metric("Erro Consolidado", f"{final_res['final_error_radius_m']:.2f} m", delta_color="inverse")
            
            # Ajuste de zoom
            lats = [p['lat'] for p in points] + [final_res['final_latitude']]
            lons = [p['lon'] for p in points] + [final_res['final_longitude']]
            sw = [min(lats), min(lons)]
            ne = [max(lats), max(lons)]

            m_super = folium.Map(location=[final_res['final_latitude'], final_res['final_longitude']])
            m_super.fit_bounds([sw, ne])

            # Pontos individuais (Cinza)
            for p in points:
                folium.CircleMarker(
                    location=[float(p['lat']), float(p['lon'])],
                    radius=3, color="gray", fill=True, fill_opacity=0.5,
                    tooltip=f"Amostra (Erro: {p['error']:.1f}m)"
                ).add_to(m_super)

            # Área Final (Verde)
            folium.Circle(
                location=[float(final_res['final_latitude']), float(final_res['final_longitude'])],
                radius=float(final_res['final_error_radius_m']),
                color="green", weight=3, fill=True, fill_color="green", fill_opacity=0.3,
                tooltip="Área de Confiança Final"
            ).add_to(m_super)

            folium.Marker(
                [float(final_res['final_latitude']), float(final_res['final_longitude'])],
                tooltip="SUPER POSIÇÃO",
                icon=folium.Icon(color="green", icon="flag")
            ).add_to(m_super)

            # Key dinâmica: garante que o mapa atualize o zoom/centro se a quantidade de pontos mudar
            st_folium(m_super, height=600, use_container_width=True, key=f"map_super_{len(points)}")

if st.session_state['trigger_balloons']:
    st.balloons()
    st.session_state['trigger_balloons'] = False