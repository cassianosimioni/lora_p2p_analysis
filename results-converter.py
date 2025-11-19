import re
import json
import os

def extract_data_from_text(text_block):
    """
    Tenta extrair Latitude, Longitude e Erro de um bloco de texto
    usando Expressões Regulares (Regex).
    """
    try:
        # Regex para capturar os valores
        lat_match = re.search(r"Latitude Estimada:\s*(-?\d+\.\d+)", text_block)
        lon_match = re.search(r"Longitude Estimada:\s*(-?\d+\.\d+)", text_block)
        error_match = re.search(r"Raio de Erro Estimado:\s*(\d+)", text_block) # Pega o número antes de "metros"

        if lat_match and lon_match and error_match:
            return {
                "lat": float(lat_match.group(1)),
                "lon": float(lon_match.group(1)),
                "error": int(error_match.group(1))
            }
        return None
    except Exception:
        return None

def main():
    print("=============================================================")
    print(" 🛠️  CONVERSOR DE DADOS: TEXTO -> DATA.JSON 🛠️")
    print("=============================================================")
    print("Instruções:")
    print("1. Copie o resultado do primeiro script (o bloco com Lat/Lon/Erro).")
    print("2. Cole aqui no terminal.")
    print("3. Pressione ENTER.")
    print("4. Digite 'ADD' (e Enter) para confirmar esse bloco.")
    print("5. Repita para quantos resultados quiser.")
    print("6. Digite 'SALVAR' para criar o arquivo data.json e sair.")
    print("=============================================================\n")

    collected_data = []
    current_buffer = []

    while True:
        try:
            line = input()
            
            # Comando para finalizar e salvar
            if line.strip().upper() == 'SALVAR':
                break
            
            # Comando para processar o que foi colado até agora
            elif line.strip().upper() == 'ADD':
                full_text = "\n".join(current_buffer)
                result = extract_data_from_text(full_text)
                
                if result:
                    collected_data.append(result)
                    print(f"   ✅ Bloco capturado! (Total: {len(collected_data)}) - Cole o próximo ou digite SALVAR.")
                else:
                    print("   ⚠️  Não encontrei dados válidos no que foi colado. Tente colar novamente.")
                
                current_buffer = [] # Limpa o buffer para o próximo
            
            else:
                # Vai acumulando as linhas coladas
                current_buffer.append(line)
                
        except EOFError:
            break

    # --- Salvar no arquivo data.json ---
    if collected_data:
        filename = "data.json"
        try:
            with open(filename, "w", encoding='utf-8') as f:
                json.dump(collected_data, f, indent=4)
            
            print(f"\n🎉 Sucesso! Arquivo '{filename}' gerado com {len(collected_data)} posições.")
            print("Agora você pode rodar o script de consolidação assim:")
            print(f"cat {filename} | python script_consolidacao.py")
            # Ou no Windows: type data.json | python script_consolidacao.py
        except IOError as e:
            print(f"Erro ao salvar o arquivo: {e}")
    else:
        print("\nNenhum dado válido foi coletado. Arquivo não gerado.")

if __name__ == "__main__":
    main()