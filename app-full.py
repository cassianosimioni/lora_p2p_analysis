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
    MAX_DISTANCE_KM = 1.5
    GATEWAY_COORDINATE_DIVISOR = 10000000.0

    valid_gateways = []

    # 1. Extração e Validação Inicial
    for data in gateway_positions_raw:
        try:
            if isinstance(data, str): data = json.loads(data)
            
            # Garante acesso seguro aos dicionários
            data_payload = data.get('data', {})
            gw_pos = data_payload.get('gatewayPosition', [{}])[0]
            gw_gps = data_payload.get('gatewayGps', {})
            
            if not gw_pos: continue
            
            lat_raw = gw_pos.get('latitude')
            lon_raw = gw_pos.get('longitude')

            # --- 1. VALIDAÇÃO ESTRITA DE RSSI ---
            # Se não tiver dados de rádio, ignoramos o gateway para não sujar a média
            lora_radio = data_payload.get('loraRadio', {})
            if 'RSSI' not in lora_radio:
                # Gateway descartado: Sem medição de sinal
                continue
            
            rssi = lora_radio['RSSI']
            # ------------------------------------
            
            # --- 2. CORREÇÃO DO FIX STATE (TEXTO OU NÚMERO) ---
            FIX_MAP = {
                "FS_FIX_NOT_AVAILABLE": 0,
                "FS_FIX_TIME_ONLY": 1,
                "FS_FIX_2D": 2,
                "FS_FIX_3D": 3
            }

            raw_fix = gw_gps.get('fixState', 0)
            
            if isinstance(raw_fix, int):
                fix_state = raw_fix
            else:
                # Converte string para int usando o mapa. Se não achar, assume 0.
                fix_state = FIX_MAP.get(str(raw_fix), 0)
            # ------------------------------------------------

            if lat_raw is None or lon_raw is None: continue

            lat = lat_raw / GATEWAY_COORDINATE_DIVISOR
            lon = lon_raw / GATEWAY_COORDINATE_DIVISOR

            # Aceita apenas Fix 2D (2) ou 3D (3)
            if fix_state in [2, 3]:
                valid_gateways.append({'lat': lat, 'lon': lon, 'rssi': rssi})
                
        except Exception as e:
            # Se o JSON estiver muito quebrado, pula para o próximo
            continue

    if not valid_gateways: return None, "Nenhum gateway válido com GPS Fix (2D/3D) e RSSI encontrado."

    # ---------------------------------------------------------
    # 2. NOVO MÉTODO DE FILTRAGEM (O LÍDER DO GRUPO)
    # Em vez de média simples, achamos o gateway mais central.
    # ---------------------------------------------------------
    
    if len(valid_gateways) > 1:
        best_center_gateway = None
        min_total_dist = float('inf')

        # Compara cada gateway contra todos os outros
        for g1 in valid_gateways:
            current_dist_sum = 0.0
            for g2 in valid_gateways:
                if g1 == g2: continue
                current_dist_sum += calculate_haversine_distance(g1['lat'], g1['lon'], g2['lat'], g2['lon'])

            # O gateway com a MENOR soma de distâncias é o que está mais no "meio" do cluster real
            if current_dist_sum < min_total_dist:
                min_total_dist = current_dist_sum
                best_center_gateway = g1
        
        ref_lat = best_center_gateway['lat']
        ref_lon = best_center_gateway['lon']
    else:
        # Se só tem 1 gateway, ele é o centro
        ref_lat = valid_gateways[0]['lat']
        ref_lon = valid_gateways[0]['lon']

    # 3. Aplica o filtro usando o "Líder" como referência
    filtered_gateways = []
    for gateway in valid_gateways:
        dist = calculate_haversine_distance(gateway['lat'], gateway['lon'], ref_lat, ref_lon)
        
        if dist < MAX_DISTANCE_KM:
            filtered_gateways.append(gateway)

    if not filtered_gateways: return None, "Todos os gateways foram descartados (Erro Crítico de Dispersão)."

    # 4. Cálculo Ponderado Final (só com os aprovados)
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
            
    if total_power_weight == 0: return None, "Erro matemático: Peso total zero."

    estimated_lat = latitude_weighted / total_power_weight
    estimated_lon = longitude_weighted / total_power_weight
    
    rssi_abs = abs(max_rssi)
    estimated_error = rssi_abs - int(rssi_abs * 0.15)
    
    return {
        "lat": estimated_lat,
        "lon": estimated_lon,
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

st.title("🛰️ Sistema Integrado: Triangulação & Super-Posição")

tab1, tab2 = st.tabs(["📡 1. Triangulação (Passo a Passo)", "🎯 2. Super-Posição (Consolidado)"])

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
                # Tenta transformar objetos colados ("}{") em uma lista válida
                if not raw_data.startswith("["):
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
        c1.metric("Lat", f"{res['lat']:.6f}")
        c2.metric("Lon", f"{res['lon']:.6f}")
        c3.metric("Erro", f"{res['error']} m")

        # Feedback visual de quantos gateways foram descartados
        discarded_count = res['total_raw_gateways'] - len(res['gateways_used'])
        if discarded_count > 0:
            st.warning(f"⚠️ Atenção: {discarded_count} gateway(s) descartado(s) (Longe do cluster ou sem RSSI/GPS Fix).")
        else:
            st.success("Todos os gateways válidos foram usados.")

        with c4:
            st.write("") 
            if st.button("➕ Enviar para Super-Posição"):
                st.session_state['stored_points'].append(res)
                st.success(f"Adicionado! Total acumulado: {len(st.session_state['stored_points'])}")
                st.session_state['last_triangulation'] = None
                st.rerun()

        m = folium.Map(location=[res['lat'], res['lon']], zoom_start=16)
        folium.Circle(
            location=[res['lat'], res['lon']], radius=float(res['error']),
            color="red", fill=True, fill_opacity=0.2
        ).add_to(m)
        
        # Plota os gateways usados
        for gw in res['gateways_used']:
            folium.Marker(
                [gw['lat'], gw['lon']],
                tooltip=f"Gateway (RSSI: {gw['rssi']}dBm)",
                icon=folium.Icon(color="blue", icon="info-sign") 
            ).add_to(m)

        folium.Marker([res['lat'], res['lon']], icon=folium.Icon(color="red", icon="star")).add_to(m)
        
        st_folium(m, height=400, use_container_width=True, key="map_single")

# ==========================================
# ABA 2: SUPER-POSIÇÃO (FINAL)
# ==========================================
with tab2:
    st.markdown("### 2. Consolidação de Múltiplas Estimativas")
    
    points = st.session_state['stored_points']
    count = len(points)
    
    if count == 0:
        st.info("👈 Nenhum ponto acumulado ainda. Vá na aba 'Triangulação', calcule e adicione.")
    else:
        st.write(f"Você tem **{count}** pontos prontos para processamento.")
        
        df = pd.DataFrame(points)[['lat', 'lon', 'error']]
        with st.expander("Ver dados brutos acumulados (Alta Precisão)"):
            st.dataframe(df.style.format({"lat": "{:.8f}", "lon": "{:.8f}", "error": "{:.2f}"}))
            
            if st.button("🗑️ Limpar Lista e Recomeçar"):
                st.session_state['stored_points'] = []
                st.session_state['super_position_result'] = None
                st.session_state['trigger_balloons'] = False
                st.rerun()

        st.divider()
        
        if st.button("🎯 EXECUTAR SUPER-POSIÇÃO", type="primary"):
            final_res = consolidate_super_position(points)
            
            if final_res:
                st.session_state['super_position_result'] = final_res
                st.session_state['trigger_balloons'] = True
            else:
                st.error("Erro ao consolidar. Verifique se os dados possuem erro > 0.")

        if st.session_state['super_position_result']:
            final_res = st.session_state['super_position_result']
            
            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("Latitude Final", f"{final_res['final_latitude']:.8f}")
            fc2.metric("Longitude Final", f"{final_res['final_longitude']:.8f}")
            fc3.metric("Erro Consolidado", f"{final_res['final_error_radius_m']:.2f} m", delta_color="inverse")
            
            lats = [p['lat'] for p in points] + [final_res['final_latitude']]
            lons = [p['lon'] for p in points] + [final_res['final_longitude']]
            sw = [min(lats), min(lons)]
            ne = [max(lats), max(lons)]

            m_super = folium.Map(location=[final_res['final_latitude'], final_res['final_longitude']])
            m_super.fit_bounds([sw, ne])

            for p in points:
                folium.CircleMarker(
                    location=[float(p['lat']), float(p['lon'])],
                    radius=3, color="gray", fill=True, fill_opacity=0.5,
                    tooltip=f"Lat: {p['lat']:.6f}, Lon: {p['lon']:.6f}"
                ).add_to(m_super)

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

            st_folium(m_super, height=600, use_container_width=True, key="map_super_persist")

if st.session_state['trigger_balloons']:
    st.balloons()
    st.session_state['trigger_balloons'] = False