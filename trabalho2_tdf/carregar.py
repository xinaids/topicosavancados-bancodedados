#!/usr/bin/env python3
"""Cria o keyspace/tabelas (schema.cql) e carrega os CSVs da pasta dados/ no Apache Cassandra.

Exemplos:
  python carregar.py                          # Cassandra em 127.0.0.1:9042, RF=1
  python carregar.py --host cassandra1 --rf 3 # dentro do docker compose (cluster de 3 nós)
  python carregar.py --reset                  # apaga o keyspace e recria tudo
  python carregar.py --dry-run                # só valida os CSVs, sem conectar
"""
import argparse
import csv
import datetime as dt
import os
import re
import sys
import time
import uuid
from decimal import Decimal

BASE = os.path.dirname(os.path.abspath(__file__))
INT, DEC, DATE, UUID, BOOL, TEXT = 'int', 'dec', 'date', 'uuid', 'bool', 'text'

TABELAS = [
    ('ciclistas.csv', 'ciclistas', [('ciclista_id', UUID), ('nome', TEXT), ('pais', TEXT), ('data_nascimento', DATE)]),
    ('edicoes.csv', 'edicoes', [('ano', INT), ('edicao', INT), ('data_inicio', DATE), ('distancia_km', DEC), ('tempo_total_h', DEC),
                                ('vencedor', TEXT), ('equipe_vencedora', TEXT), ('vitorias_etapa', INT), ('etapas_lideradas', INT),
                                ('com_resultados', BOOL)]),
    ('etapas.csv', 'etapas', [('ano', INT), ('ordem', INT), ('numero', TEXT), ('data_etapa', DATE), ('tipo', TEXT),
                              ('distancia_km', DEC), ('origem', TEXT), ('destino', TEXT), ('vencedor', TEXT)]),
    ('resultados_por_etapa.csv', 'resultados_por_etapa', [('ano', INT), ('ordem', INT), ('posicao', INT), ('ciclista_id', UUID),
                                                          ('nome', TEXT), ('equipe', TEXT), ('idade', INT), ('status', TEXT), ('pontos', INT)]),
    ('resultados_por_ciclista.csv', 'resultados_por_ciclista', [('ciclista_id', UUID), ('ano', INT), ('ordem', INT), ('posicao', INT),
                                                                ('status', TEXT), ('equipe', TEXT), ('idade', INT), ('pontos', INT),
                                                                ('data_etapa', DATE), ('tipo', TEXT), ('distancia_km', DEC)]),
]


def converte(tipo, v, unset):
    if v is None or v == '':
        return unset  # célula vazia: não grava nada (evita tombstone)
    if tipo == INT:
        return int(float(v))
    if tipo == DEC:
        return Decimal(v)
    if tipo == DATE:
        return dt.date.fromisoformat(v[:10])
    if tipo == UUID:
        return uuid.UUID(v)
    if tipo == BOOL:
        return v.strip().lower() == 'true'
    return v


def linhas(caminho, colunas, unset):
    with open(caminho, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            yield tuple(converte(t, r[c], unset) for c, t in colunas)


def comandos_schema(rf):
    txt = open(os.path.join(BASE, 'schema.cql'), encoding='utf-8').read()
    txt = '\n'.join(l.split('--')[0] for l in txt.splitlines())
    txt = re.sub(r"'replication_factor'\s*:\s*\d+", f"'replication_factor': {rf}", txt)
    return [c.strip() for c in txt.split(';') if c.strip()]


def conectar(hosts, port, espera):
    from cassandra.cluster import Cluster
    t0 = time.time()
    while True:
        try:
            c = Cluster(hosts, port=port, connect_timeout=10)
            return c, c.connect()
        except Exception as e:  # noqa: BLE001
            if time.time() - t0 > espera:
                sys.exit(f'Não consegui conectar em {hosts}:{port} ({type(e).__name__}: {e})')
            print('Aguardando o Cassandra subir…', flush=True)
            time.sleep(6)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', default=os.getenv('TDF_HOSTS', '127.0.0.1'))
    ap.add_argument('--port', type=int, default=9042)
    ap.add_argument('--rf', type=int, default=1, help='fator de replicação do keyspace (SimpleStrategy)')
    ap.add_argument('--dados', default=os.path.join(BASE, 'dados'))
    ap.add_argument('--reset', action='store_true', help='DROP KEYSPACE antes de criar')
    ap.add_argument('--se-vazio', action='store_true', help='não recarrega se o keyspace já tiver dados')
    ap.add_argument('--dry-run', action='store_true', help='só valida os CSVs')
    ap.add_argument('--espera', type=int, default=240, help='segundos esperando o Cassandra subir')
    a = ap.parse_args()

    if a.dry_run:
        from cassandra.query import UNSET_VALUE
        for arq, tab, cols in TABELAS:
            n = sum(1 for _ in linhas(os.path.join(a.dados, arq), cols, UNSET_VALUE))
            print(f'{tab:26s} {n:>8,} linhas OK')
        print(f'schema: {len(comandos_schema(a.rf))} comandos')
        return

    from cassandra.concurrent import execute_concurrent_with_args
    from cassandra.query import UNSET_VALUE
    cluster, s = conectar([h.strip() for h in a.host.split(',')], a.port, a.espera)
    print('Conectado:', [str(h.address) for h in cluster.metadata.all_hosts()])
    if a.reset:
        s.execute('DROP KEYSPACE IF EXISTS ciclismo')
        print('Keyspace antigo removido.')
    for cmd in comandos_schema(a.rf):
        s.execute(cmd)
    s.set_keyspace('ciclismo')
    print(f'Esquema criado (RF={a.rf}).')
    if a.se_vazio and s.execute('SELECT ano FROM edicoes LIMIT 1').one():
        print('Os dados já estão carregados; nada a fazer.')
        cluster.shutdown()
        return

    for arq, tab, cols in TABELAS:
        nomes = ', '.join(c for c, _ in cols)
        ps = s.prepare(f'INSERT INTO {tab} ({nomes}) VALUES ({", ".join("?" for _ in cols)})')
        lote, total, t0 = [], 0, time.time()
        for row in linhas(os.path.join(a.dados, arq), cols, UNSET_VALUE):
            lote.append(row)
            if len(lote) >= 4000:
                execute_concurrent_with_args(s, ps, lote, concurrency=96, raise_on_first_error=True)
                total += len(lote); lote = []
                print(f'  {tab}: {total:,} linhas…', end='\r', flush=True)
        if lote:
            execute_concurrent_with_args(s, ps, lote, concurrency=96, raise_on_first_error=True)
            total += len(lote)
        print(f'{tab:26s} {total:>8,} linhas em {time.time() - t0:5.1f}s')
    print('\nPronto. Agora é só subir a API: uvicorn app.main:app  (ou docker compose up).')
    cluster.shutdown()


if __name__ == '__main__':
    main()
