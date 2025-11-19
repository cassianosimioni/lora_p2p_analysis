import json
import math
import sys

# --- FUNÇÃO DE CONSOLIDAÇÃO ---

def consolidate_series_positions(position_series):
    """
    Calcula a posição final consolidada (super-posição) a partir de 
    uma série de posições estimadas, ponderando pelo inverso do quadrado do erro.
    """
    
    # 🚨 CORREÇÃO: Inicialização das variáveis no topo da função 
    latitude_weighted = 0.0
    longitude_weighted = 0.0
    error_weighted = 0.0
    total_weight = 0.0
    
    print("\n--- DETALHES DA PONDERAÇÃO ---")
    
    for i, pos in enumerate(position_series):
        lat = pos.get('lat')
        lon = pos.get('lon')
        error_radius = pos.get('error') # Raio de erro em metros
        
        # Checagem de Validade (Ignora pontos com erro zero ou inválido)
        if error_radius is None or error_radius <= 0 or lat is None or lon is None:
            print(f"Aviso: Posição #{i+1} ignorada devido a erro <= 0 ou dados ausentes.")
            continue 

        # 1. Calcular o Peso (W) (Inverso do Quadrado do Erro)
        # O peso é a confiança: W = 1 / R_erro^2
        weight = 1.0 / (error_radius ** 2)
        
        print(f"Posição #{i+1} (Erro: {error_radius}m): Peso = {weight:.8f}")
        
        # 2. Somar os pesos para Lat/Lon e Erro
        latitude_weighted += (lat * weight)
        longitude_weighted += (lon * weight)
        error_weighted += (error_radius * weight)
        
        total_weight += weight
        
    if total_weight == 0:
        return None
        
    # 3. Calcular a Média Ponderada
    final_lat = latitude_weighted / total_weight
    final_lon = longitude_weighted / total_weight
    
    # 4. Calcular o Erro Consolidado (Média Ponderada dos Erros Individuais)
    final_error = error_weighted / total_weight

    return {
        "final_latitude": final_lat,
        "final_longitude": final_lon,
        "final_error_radius_m": final_error,
        "total_positions_used": len(position_series)
    }

# --- FUNÇÃO PRINCIPAL DE INTERAÇÃO (LEITURA DO ARQUIVO/PIPE) ---

def main():
    print("=========================================================")
    print("  ✨ Consolidação Temporal de Posições (Super-Posição) ✨")
    print("=========================================================")
    print("Modo de execução: Lendo dados JSON do stdin (pipe ou arquivo)...")
    
    # Lê todo o conteúdo do stdin de uma vez (ideal para redirecionamento < data.json)
    json_str = sys.stdin.read().strip()

    if not json_str:
        print("Nenhum dado fornecido via entrada. Encerrando.")
        return

    try:
        # Substitui aspas simples por duplas, garantindo validade JSON
        json_str = json_str.replace("'", '"')
        
        # O resultado deve ser uma LISTA JSON: [ {...}, {...} ]
        input_results = json.loads(json_str)
        
        # Garante que seja uma lista para processamento
        if not isinstance(input_results, list):
            if isinstance(input_results, dict):
                 input_results = [input_results]
            else:
                 raise ValueError("A entrada não é uma lista ou um objeto JSON válido.")

    except json.JSONDecodeDECODINGError as e:
        print(f"\nERRO FATAL: JSON inválido. Verifique se o formato é uma lista []. Detalhes: {e}")
        return
    except ValueError as e:
        print(f"\nERRO FATAL: {e}")
        return
    except Exception as e:
         print(f"\nERRO INESPERADO: {e}")
         return
    
    # Processa e exibe o resultado
    if input_results:
        result = consolidate_series_positions(input_results)
        
        print("\n=========================================================")
        print("  ✅ RESULTADO DA SUPER-POSIÇÃO CONSOLIDADA")
        print("=========================================================")
        
        if result:
            print(f"Posições de entrada utilizadas: {result['total_positions_used']}")
            print("-" * 55)
            print(f"Latitude Final:    {result['final_latitude']:.8f}")
            print(f"Longitude Final:   {result['final_longitude']:.8f}")
            print(f"Raio de Erro Final: {result['final_error_radius_m']:.2f} metros")
        else:
            print("Não foi possível consolidar. Verifique se os dados de erro são válidos (> 0).")
            
# Executar a função principal
if __name__ == "__main__":
    main()