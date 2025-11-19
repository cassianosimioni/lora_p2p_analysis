import json
import math

# --- 1. FUNÇÕES AUXILIARES ---

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calcula a distância Haversine entre dois pontos de GPS.
    Retorna a distância em quilômetros (km).
    """
    R = 6371.0  # Raio da Terra em quilômetros

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def process_data(gateway_positions_raw):
    """
    Processa os dados JSON e executa a triangulação ponderada.
    """
    MAX_DISTANCE_KM = 5.0
    GATEWAY_COORDINATE_DIVISOR = 10000000.0

    # 1. PRIMEIRA PASSAGEM: EXTRAIR DADOS VÁLIDOS E CALCULAR CENTRO GEOMÉTRICO
    valid_gateways = []
    sum_lat = 0.0
    sum_lon = 0.0

    for data in gateway_positions_raw:
        try:
            # Assumimos que a posição do gateway é válida se houver GPS fix (fixState=1)
            gateway_lat_raw = data['data']['gatewayPosition'][0]['latitude']
            gateway_lon_raw = data['data']['gatewayPosition'][0]['longitude']
            rssi = data['data']['loraRadio']['RSSI']
            fix_state = data['data']['gatewayGps']['fixState']
            
            # Converter coordenadas para formato decimal (ex: -80143938 -> -8.0143938)
            lat = gateway_lat_raw / GATEWAY_COORDINATE_DIVISOR
            lon = gateway_lon_raw / GATEWAY_COORDINATE_DIVISOR

            if fix_state == 1:
                valid_gateways.append({'lat': lat, 'lon': lon, 'rssi': rssi})
                sum_lat += lat
                sum_lon += lon
            
        except (KeyError, IndexError, TypeError) as e:
            # Ignora pacotes incompletos ou malformados
            print(f"Aviso: Pacote ignorado devido a dados ausentes ou inválidos. Erro: {e}")
            continue

    if not valid_gateways:
        return "ERRO: Nenhuma posição de Gateway válida encontrada com GPS fix.", 0

    # Cálculo do Centróide Simples (Centro de Massa)
    avg_lat = sum_lat / len(valid_gateways)
    avg_lon = sum_lon / len(valid_gateways)

    # 2. SEGUNDA PASSAGEM: FILTRAR OUTLIERS (5KM DE DISTÂNCIA DA MAIORIA)
    filtered_gateways = []
    
    for gateway in valid_gateways:
        distance_to_center = calculate_haversine_distance(
            gateway['lat'], gateway['lon'], avg_lat, avg_lon
        )
        
        # Descartar se o gateway estiver muito longe do centro da maioria
        if distance_to_center < MAX_DISTANCE_KM:
            filtered_gateways.append(gateway)

    print(f"--- FASE 2: FILTRAGEM ---")
    print(f"Total de gateways válidos (com GPS fix): {len(valid_gateways)}")
    print(f"Gateways filtrados e usados no cálculo (dentro de {MAX_DISTANCE_KM}km): {len(filtered_gateways)}")

    if len(filtered_gateways) == 0:
        return "ERRO: Todos os gateways foram descartados por estarem a mais de 5km um do outro.", 0
        
    # 3. TERCEIRA PASSAGEM: CÁLCULO DA POSIÇÃO ESTIMADA (PESO PELA POTÊNCIA)
    
    latitude_weighted = 0.0
    longitude_weighted = 0.0
    total_power_weight = 0.0
    max_rssi = -200 # Valor inicial para encontrar o RSSI mais forte

    for gateway in filtered_gateways:
        # Ponderação por Potência (mW): W = 10^(RSSI / 10)
        power_weight = 10**(gateway['rssi'] / 10.0)
        
        latitude_weighted += (gateway['lat'] * power_weight)
        longitude_weighted += (gateway['lon'] * power_weight)
        total_power_weight += power_weight
        
        if gateway['rssi'] > max_rssi:
            max_rssi = gateway['rssi']
            
    # Posição Estimada Final
    estimated_lat = latitude_weighted / total_power_weight
    estimated_lon = longitude_weighted / total_power_weight
    
    # 4. CÁLCULO FINAL DO RAIO DE ERRO (Heurística do Parceiro)
    # Erro (m) = ABS(RSSI) - (ABS(RSSI) * 0.15)
    rssi_abs = abs(max_rssi)
    estimated_error = rssi_abs - int(rssi_abs * 0.15)
    
    return (
        f"Latitude Estimada: {estimated_lat:.8f}\n"
        f"Longitude Estimada: {estimated_lon:.8f}\n"
        f"RSSI Mais Forte Usado: {max_rssi} dBm\n"
        f"Raio de Erro Estimado: {estimated_error} metros", 
        estimated_error
    )

# --- 2. FUNÇÃO PRINCIPAL DE INTERAÇÃO ---

def main():
    print("===============================================")
    print("  ⭐ Triangulação LoRa P2P (MXT 130 V2) ⭐")
    print("===============================================")
    print("Cole os pacotes JSON (um de cada vez) do mesmo Sequence Number.")
    print("Para parar e processar, digite 'FIM' em uma nova linha.")
    print("-" * 45)

    input_strings = []
    
    while True:
        try:
            # Lê o JSON de entrada até encontrar a palavra-chave "FIM"
            json_block = []
            while True:
                line = input()
                if line.strip().upper() == 'FIM':
                    break
                json_block.append(line)
            
            if not json_block:
                break
                
            json_str = "".join(json_block)
            data = json.loads(json_str)
            input_strings.append(data)
            print("-" * 45)
            print(f"Pacote #{len(input_strings)} recebido. Cole o próximo ou digite FIM.")

        except json.JSONDecodeError:
            print("ERRO: JSON inválido. Tente colar novamente o bloco completo.")
        except EOFError:
            break
        except Exception as e:
            print(f"Um erro inesperado ocorreu: {e}")
            break

    if input_strings:
        print("\n=== INICIANDO O CÁLCULO DE LOCALIZAÇÃO ===")
        result, _ = process_data(input_strings)
        print("\n-------------------------------------------")
        print(result)
        print("-------------------------------------------")
    else:
        print("Nenhum dado fornecido. Encerrando.")

# Executar a função principal
if __name__ == "__main__":
    main()