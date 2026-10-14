#!/usr/bin/env python3
"""
Prepara os CSVs para carga no Cassandra (keyspace `ciclismo`) a partir do dataset
Kaggle "Tour de France" (stage_data.csv, tdf_stages.csv, tdf_winners.csv).

Uso:
  python3 preparar_dados.py --tdf dados --out out [--min-match 0.85]

Como as etapas sao ligadas aos resultados:
  - stage_data identifica a etapa como 'stage-N' e tdf_stages usa 'P' (prologo) e datas.
    As duas fontes sao casadas pela ORDEM da etapa dentro da edicao (ano, ordem).
  - So entram edicoes em que (1) o numero de etapas bate nos dois arquivos e
    (2) pelo menos --min-match dos vencedores de etapa (exceto contrarrelogio por equipes)
    coincidem com o 1o colocado do resultado. As demais ficam sem etapas/resultados.
  - A tabela de edicoes (tdf_winners) entra completa; a coluna com_resultados indica
    quais edicoes tem etapas e resultados carregados.

Convencoes:
  - posicao = 9999 para quem nao foi classificado (DNF, DNS, OTL, DSQ, DF, NQ); ver 'status'.
  - ciclista_id = UUID v5 deterministico a partir do nome normalizado (homonimos se fundem).
"""
import argparse, os, re, unicodedata, uuid
import pandas as pd

NS = uuid.UUID('6ba7b811-9dad-11d1-80b4-00c04fd430c8')  # namespace URL


def norm_tokens(nome):
    s = unicodedata.normalize('NFKD', str(nome)).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"[^a-z0-9' ]+", ' ', s)
    return ' '.join(sorted(s.split()))


def cid(nome):
    return str(uuid.uuid5(NS, 'tdf:' + norm_tokens(nome)))


def stage_key(sid):
    m = re.fullmatch(r'stage-(\d+)([a-z]?)', sid)
    return (int(m.group(1)), m.group(2)) if m else (10**6, sid)


def parecido(a, b):
    A, B = set(norm_tokens(a).split()), set(norm_tokens(b).split())
    return len(A & B) / max(1, len(A | B)) >= 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tdf', default='dados'); ap.add_argument('--out', default='out')
    ap.add_argument('--min-match', type=float, default=0.85)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    sd = pd.read_csv(f'{a.tdf}/stage_data.csv', dtype=str)
    st = pd.read_csv(f'{a.tdf}/tdf_stages.csv', dtype=str)
    wn = pd.read_csv(f'{a.tdf}/tdf_winners.csv', dtype=str)
    st['ano'] = st['Date'].str[:4].astype(int)
    st['Winner'] = st['Winner'].str.replace(r'\[.*?\]', '', regex=True).str.strip()  # notas de rodape
    sd['ano'] = sd['year'].astype(int)
    st = st.reset_index(drop=True)
    st['ordem'] = st.groupby('ano').cumcount() + 1
    ids = (sd[['ano', 'stage_results_id']].drop_duplicates()
           .assign(k=lambda d: d.stage_results_id.map(stage_key)).sort_values(['ano', 'k']))
    ids['ordem'] = ids.groupby('ano').cumcount() + 1
    sd = sd.merge(ids[['ano', 'stage_results_id', 'ordem']], on=['ano', 'stage_results_id'])

    # --- selecao das edicoes confiaveis -------------------------------------
    n_sd, n_st = ids.groupby('ano').size(), st.groupby('ano').size()
    v1 = (sd[sd['rank'] == '1'][['ano', 'ordem', 'rider']].drop_duplicates(['ano', 'ordem'])
          .merge(st[['ano', 'ordem', 'Winner', 'Type']], on=['ano', 'ordem']))
    v1 = v1[v1.Type != 'Team time trial']
    v1['ok'] = [parecido(x, y) for x, y in zip(v1.rider, v1.Winner)]
    taxa = v1.groupby('ano').ok.mean()
    bons = sorted(y for y in taxa.index if n_sd.get(y) == n_st.get(y) and taxa[y] >= a.min_match)
    print(f'edicoes com etapas/resultados carregados: {len(bons)} de {len(taxa)} comparaveis '
          f'(contagem de etapas igual e >= {a.min_match:.0%} de vencedores conferindo)')
    sd, st = sd[sd.ano.isin(bons)].copy(), st[st.ano.isin(bons)].copy()

    # --- ciclistas -----------------------------------------------------------
    pais = {norm_tokens(r.Winner): r.Winner_Country.strip() for r in st.dropna(subset=['Winner_Country']).itertuples()}
    nasc = {norm_tokens(r.winner_name): r.born for r in wn.dropna(subset=['born']).itertuples()}
    cic = pd.DataFrame({'nome': sd['rider'].drop_duplicates()})
    cic['k'] = cic.nome.map(norm_tokens)
    cic = cic.drop_duplicates('k')
    cic['ciclista_id'] = cic.nome.map(cid)
    cic['pais'] = cic.k.map(pais)
    cic['data_nascimento'] = cic.k.map(nasc)
    ciclistas = cic[['ciclista_id', 'nome', 'pais', 'data_nascimento']]

    # --- edicoes (todas) -----------------------------------------------------
    ed = pd.DataFrame({
        'ano': wn.start_date.str[:4].astype(int), 'edicao': wn.edition.astype(int),
        'data_inicio': wn.start_date, 'distancia_km': pd.to_numeric(wn.distance),
        'tempo_total_h': pd.to_numeric(wn.time_overall).round(2),
        'vencedor': wn.winner_name, 'equipe_vencedora': wn.winner_team,
        'vitorias_etapa': pd.to_numeric(wn.stage_wins).astype('Int64'),
        'etapas_lideradas': pd.to_numeric(wn.stages_led).astype('Int64')})
    ed['com_resultados'] = ed.ano.isin(bons)
    edicoes = ed

    # --- etapas --------------------------------------------------------------
    etapas = st[['ano', 'ordem', 'Stage', 'Date', 'Type', 'Distance', 'Origin', 'Destination', 'Winner']].copy()
    etapas.columns = ['ano', 'ordem', 'numero', 'data_etapa', 'tipo', 'distancia_km', 'origem', 'destino', 'vencedor']

    # --- resultados ----------------------------------------------------------
    sd['ciclista_id'] = sd.rider.map(cid)
    sd['status'] = sd['rank'].where(~sd['rank'].str.fullmatch(r'\d+'), 'FIN')
    sd['posicao'] = pd.to_numeric(sd['rank'], errors='coerce').fillna(9999).astype(int)
    sd['idade'] = pd.to_numeric(sd['age'], errors='coerce').round().astype('Int64')
    sd['pontos'] = pd.to_numeric(sd['points'], errors='coerce').round().astype('Int64')
    sd = sd.drop_duplicates(['ano', 'ordem', 'ciclista_id'])
    res = sd[['ano', 'ordem', 'posicao', 'ciclista_id', 'rider', 'team', 'idade', 'status', 'pontos']].copy()
    res.columns = ['ano', 'ordem', 'posicao', 'ciclista_id', 'nome', 'equipe', 'idade', 'status', 'pontos']
    rpc = res.merge(etapas[['ano', 'ordem', 'data_etapa', 'tipo', 'distancia_km']], on=['ano', 'ordem'])
    rpc = rpc[['ciclista_id', 'ano', 'ordem', 'posicao', 'status', 'equipe', 'idade', 'pontos',
               'data_etapa', 'tipo', 'distancia_km']]

    saidas = [('ciclistas', ciclistas), ('edicoes', edicoes), ('etapas', etapas),
              ('resultados_por_etapa', res), ('resultados_por_ciclista', rpc)]
    for n, d in saidas:
        d.to_csv(f'{a.out}/{n}.csv', index=False, na_rep='')
    print('\nlinhas geradas:')
    for n, d in saidas:
        print(f'  {n:26s} {len(d):8d}')


if __name__ == '__main__':
    main()
