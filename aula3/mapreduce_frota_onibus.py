"""
Exemplo de MapReduce - Frota de Onibus de Porto Alegre (STPoa)
Fonte: https://dadosabertos.poa.br/dataset/stpoa-sistema-de-transporte-publico-de-porto-alegre

Objetivo: contar quantos onibus cada empresa operadora possui na frota.
Isso segue exatamente o mesmo padrao do classico "word count":
  - MapReduce classico: (palavra, 1) -> soma por palavra
  - Este exemplo:        (operador, 1) -> soma por operador

As 6 etapas do MapReduce sao implementadas de forma explicita e sequencial
(sem cluster real), apenas para fins didaticos.
"""

import csv
from collections import defaultdict

ARQUIVO_ENTRADA = "frota_onibus.csv"
NUM_MAPEADORES = 4   # simula 4 mapeadores processando blocos em "paralelo"
NUM_REDUTORES = 3    # simula 3 redutores recebendo chaves diferentes


# ---------------------------------------------------------------------
# ETAPA 1: ENTRADA
# ---------------------------------------------------------------------
def ler_entrada(caminho):
    with open(caminho, encoding="utf-8") as f:
        leitor = csv.DictReader(f, delimiter=";")
        linhas = list(leitor)
    print(f"[ENTRADA] {len(linhas)} registros lidos de '{caminho}'")
    return linhas


# ---------------------------------------------------------------------
# ETAPA 2: DIVISAO (SPLIT)
# ---------------------------------------------------------------------
def dividir_em_blocos(linhas, n_blocos):
    tamanho = (len(linhas) + n_blocos - 1) // n_blocos
    blocos = [linhas[i:i + tamanho] for i in range(0, len(linhas), tamanho)]
    print(f"[DIVISAO] Dados divididos em {len(blocos)} blocos "
          f"(~{tamanho} registros cada), um por mapeador")
    return blocos


# ---------------------------------------------------------------------
# ETAPA 3: MAPEAMENTO
# ---------------------------------------------------------------------
def mapear(bloco, id_mapeador):
    """Cada mapeador emite (operador, 1) para cada onibus do seu bloco."""
    pares = []
    for linha in bloco:
        operador = linha["operador"].strip()
        pares.append((operador, 1))
    print(f"[MAPEAMENTO] Mapeador {id_mapeador} processou {len(bloco)} "
          f"registros e emitiu {len(pares)} pares chave/valor")
    return pares


# ---------------------------------------------------------------------
# ETAPA 4: EMBARALHAMENTO (SHUFFLE)
# ---------------------------------------------------------------------
def embaralhar(todos_os_pares):
    """Agrupa todos os valores pela mesma chave (operador)."""
    agrupado = defaultdict(list)
    for chave, valor in todos_os_pares:
        agrupado[chave].append(valor)
    print(f"[EMBARALHAMENTO] {len(todos_os_pares)} pares agrupados em "
          f"{len(agrupado)} chaves distintas (operadoras)")
    return agrupado


# ---------------------------------------------------------------------
# ETAPA 5: REDUCAO
# ---------------------------------------------------------------------
def reduzir(chave, valores, id_redutor):
    """Cada redutor soma os valores de sua(s) chave(s) atribuida(s)."""
    total = sum(valores)
    print(f"[REDUCAO] Redutor {id_redutor} -> ({chave}, {total})")
    return chave, total


# ---------------------------------------------------------------------
# ETAPA 6: SAIDA
# ---------------------------------------------------------------------
def gerar_saida(resultados):
    resultados_ordenados = sorted(resultados, key=lambda x: x[1], reverse=True)
    print("\n[SAIDA] Total de onibus por operadora:")
    for operador, total in resultados_ordenados:
        print(f"  {operador:<45} {total:>4} onibus")
    return resultados_ordenados


def main():
    # 1. Entrada
    linhas = ler_entrada(ARQUIVO_ENTRADA)

    # 2. Divisao
    blocos = dividir_em_blocos(linhas, NUM_MAPEADORES)

    # 3. Mapeamento (um "mapeador" por bloco)
    todos_os_pares = []
    for i, bloco in enumerate(blocos, start=1):
        todos_os_pares.extend(mapear(bloco, i))

    # 4. Embaralhamento
    agrupado = embaralhar(todos_os_pares)

    # 5. Reducao (distribuindo as chaves entre os redutores simulados)
    chaves = list(agrupado.keys())
    resultados = []
    for i, chave in enumerate(chaves):
        id_redutor = (i % NUM_REDUTORES) + 1
        resultados.append(reduzir(chave, agrupado[chave], id_redutor))

    # 6. Saida
    gerar_saida(resultados)


if __name__ == "__main__":
    main()
