"""Acesso ao Apache Cassandra (keyspace `ciclismo`).

Cada método devolve (dados, log). O log lista os CQLs executados e o tempo de cada um;
a interface mostra isso no painel "CQL" para deixar claro o que o banco está fazendo.
"""
import os
import re
import threading
import time
import uuid
from decimal import Decimal

from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent_with_args
from cassandra.query import BatchStatement, BatchType, SimpleStatement, UNSET_VALUE, dict_factory

from .common import (ApiError, NAO_CLASSIFICADO, STATUS_VALIDOS, busca_key, categoria, ciclista_id, dec,
                     estatisticas_historico, fmt_cql, media, ser, ser_row, to_date)

KS = os.getenv('TDF_KEYSPACE', 'ciclismo')
CLS = {
    'ONE': ConsistencyLevel.ONE, 'TWO': ConsistencyLevel.TWO, 'QUORUM': ConsistencyLevel.QUORUM,
    'ALL': ConsistencyLevel.ALL, 'LOCAL_ONE': ConsistencyLevel.LOCAL_ONE,
    'LOCAL_QUORUM': ConsistencyLevel.LOCAL_QUORUM,
}


def uv(x):
    """None -> UNSET_VALUE (não grava célula nula, evita tombstone)."""
    return UNSET_VALUE if x is None else x


class CassandraDB:
    modo = 'cassandra'

    def __init__(self, hosts, port=9042):
        self.cluster = Cluster(hosts, port=port, connect_timeout=10)
        self.session = self.cluster.connect(KS)
        self.session.row_factory = dict_factory
        self.session.default_timeout = 30
        self._ps = {}
        self._n_resultados = None
        self.ciclistas = {}
        self._carregar_ciclistas()
        threading.Thread(target=self._contar_resultados, daemon=True).start()

    # ------------------------------------------------------------ infraestrutura
    def _prep(self, cql):
        if cql not in self._ps:
            self._ps[cql] = self.session.prepare(cql)
        return self._ps[cql]

    def _ex(self, log, cql, params=(), cl=None):
        ps = self._prep(cql)
        bound = ps.bind(params)
        if cl is not None:
            bound.consistency_level = cl
        t = time.perf_counter()
        rows = list(self.session.execute(bound))
        log.append({'cql': fmt_cql(cql, params), 'ms': round((time.perf_counter() - t) * 1000, 1)})
        return rows

    def _many(self, log, cql, lista_params):
        """Executa o mesmo CQL várias vezes em paralelo (fan-out no cliente)."""
        ps = self._prep(cql)
        t = time.perf_counter()
        res = execute_concurrent_with_args(self.session, ps, lista_params, concurrency=32,
                                           raise_on_first_error=True)
        log.append({'cql': fmt_cql(cql, lista_params[0] if lista_params else ()),
                    'ms': round((time.perf_counter() - t) * 1000, 1), 'n': len(lista_params)})
        return [list(r[1]) for r in res]

    def _carregar_ciclistas(self):
        rows = self.session.execute('SELECT ciclista_id, nome, pais FROM ciclistas')
        self.ciclistas = {str(r['ciclista_id']): {'id': str(r['ciclista_id']), 'nome': r['nome'],
                                                  'pais': r['pais'], 'k': busca_key(r['nome'])} for r in rows}

    def _contar_resultados(self):
        try:
            s = SimpleStatement('SELECT COUNT(*) AS n FROM resultados_por_ciclista')
            self._n_resultados = self.session.execute(s, timeout=120).one()['n']
        except Exception:
            self._n_resultados = None

    def _etapa(self, log, ano, ordem):
        r = self._ex(log, 'SELECT * FROM etapas WHERE ano = ? AND ordem = ?', (ano, ordem))
        return r[0] if r else None

    def _rf(self):
        rs = self.cluster.metadata.keyspaces[KS].replication_strategy
        rf = getattr(rs, 'replication_factor', None)
        if rf is None:
            rf = sum(int(v) for v in getattr(rs, 'dc_replication_factors', {}).values())
        return int(rf), rs

    # ------------------------------------------------------------ leitura
    def resumo(self):
        log = []
        ed = self._ex(log, 'SELECT ano, com_resultados FROM edicoes')
        n_etapas = self._ex(log, 'SELECT COUNT(*) AS n FROM etapas')[0]['n']
        n_cic = self._ex(log, 'SELECT COUNT(*) AS n FROM ciclistas')[0]['n']
        return {
            'edicoes': len(ed), 'edicoes_com_resultados': sum(1 for e in ed if e['com_resultados']),
            'etapas': n_etapas, 'ciclistas': n_cic, 'resultados': self._n_resultados,
            'ano_min': min(e['ano'] for e in ed), 'ano_max': max(e['ano'] for e in ed),
        }, log

    def edicoes(self):
        log = []
        rows = self._ex(log, 'SELECT * FROM edicoes')
        return sorted((ser_row(r) for r in rows), key=lambda r: r['ano']), log

    def edicao(self, ano):
        log = []
        ed = self._ex(log, 'SELECT * FROM edicoes WHERE ano = ?', (ano,))
        if not ed:
            raise ApiError(404, f'Edição {ano} não encontrada')
        et = self._ex(log, 'SELECT * FROM etapas WHERE ano = ?', (ano,))
        etapas = []
        for r in et:
            r = ser_row(r)
            r['categoria'] = categoria(r['tipo'])
            etapas.append(r)
        return {'edicao': ser_row(ed[0]), 'etapas': etapas}, log

    def ranking(self, ano, ordem, cl='ONE'):
        log = []
        etapa = self._etapa(log, ano, ordem)
        if not etapa:
            raise ApiError(404, f'Etapa {ano}/{ordem} não encontrada')
        rows = self._ex(
            log, 'SELECT posicao, ciclista_id, nome, equipe, idade, status, pontos '
                 'FROM resultados_por_etapa WHERE ano = ? AND ordem = ?', (ano, ordem), cl=CLS.get(cl, CLS['ONE']))
        rows = [ser_row(r) for r in rows]
        return {'etapa': {**ser_row(etapa), 'categoria': categoria(etapa['tipo'])}, 'resultados': rows,
                'resumo': _resumo_etapa(rows)}, log

    def busca_ciclistas(self, q, limite=15):
        tokens = busca_key(q).split()
        if not tokens:
            return [], []
        achados = [c for c in self.ciclistas.values() if all(t in c['k'] for t in tokens)]
        achados.sort(key=lambda c: (not c['k'].startswith(tokens[0]), c['nome']))
        return [{k: v for k, v in c.items() if k != 'k'} for c in achados[:limite]], [{
            'cql': 'SELECT ciclista_id, nome, pais FROM ciclistas;  -- lido uma vez na inicialização; '
                   'a busca por nome acontece em memória (Cassandra não faz LIKE)', 'ms': 0}]

    def ciclista(self, cid):
        log = []
        try:
            cid_u = uuid.UUID(cid)
        except ValueError:
            raise ApiError(400, 'ciclista_id inválido')
        p = self._ex(log, 'SELECT * FROM ciclistas WHERE ciclista_id = ?', (cid_u,))
        if not p:
            raise ApiError(404, 'Ciclista não encontrado')
        hist = [ser_row(r) for r in self._ex(
            log, 'SELECT * FROM resultados_por_ciclista WHERE ciclista_id = ?', (cid_u,))]
        agg = self._ex(
            log, 'SELECT COUNT(*) AS etapas, MIN(posicao) AS melhor_posicao_cql, SUM(pontos) AS pontos '
                 'FROM resultados_por_ciclista WHERE ciclista_id = ?', (cid_u,))[0]
        return {'ciclista': ser_row(p[0]), 'estatisticas': estatisticas_historico(hist),
                'agregado_cql': ser_row(agg), 'historico': hist}, log

    # ------------------------------------------------------------ agregações
    def agg_edicao(self, ano):
        log = []
        et = self._ex(log, 'SELECT ordem, numero, tipo, distancia_km, vencedor FROM etapas WHERE ano = ?', (ano,))
        if not et:
            raise ApiError(404, f'Edição {ano} sem etapas')
        params = [(ano, e['ordem']) for e in et]
        q1 = self._many(log, 'SELECT COUNT(*) AS participantes, AVG(CAST(idade AS double)) AS idade_media '
                             'FROM resultados_por_etapa WHERE ano = ? AND ordem = ?', params)
        q2 = self._many(log, 'SELECT COUNT(*) AS nao_classificados FROM resultados_por_etapa '
                             'WHERE ano = ? AND ordem = ? AND posicao = 9999', params)
        q3 = self._many(log, 'SELECT nome, equipe FROM resultados_por_etapa '
                             'WHERE ano = ? AND ordem = ? AND posicao = 1 LIMIT 1', params)
        por_etapa, equipes = [], {}
        for e, a, b, c in zip(et, q1, q2, q3):
            eq = c[0]['equipe'] if c else None
            if eq:
                equipes[eq] = equipes.get(eq, 0) + 1
            por_etapa.append({
                'ordem': e['ordem'], 'numero': e['numero'], 'tipo': e['tipo'], 'categoria': categoria(e['tipo']),
                'distancia_km': ser(e['distancia_km']), 'participantes': a[0]['participantes'],
                'idade_media': round(a[0]['idade_media'], 1) if a[0]['idade_media'] else None,
                'nao_classificados': b[0]['nao_classificados'],
                'vencedor': c[0]['nome'] if c else e['vencedor'], 'equipe_vencedora': eq})
        por_etapa.sort(key=lambda x: x['ordem'])
        return {'ano': ano, 'por_etapa': por_etapa,
                'vitorias_por_equipe': sorted(({'equipe': k, 'vitorias': v} for k, v in equipes.items()),
                                              key=lambda x: -x['vitorias'])}, log

    def agg_etapa(self, ano, ordem):
        log = []
        r = self._ex(log, 'SELECT COUNT(*) AS participantes, MIN(idade) AS idade_min, MAX(idade) AS idade_max, '
                          'AVG(CAST(idade AS double)) AS idade_media, SUM(pontos) AS pontos_distribuidos '
                          'FROM resultados_por_etapa WHERE ano = ? AND ordem = ?', (ano, ordem))
        return ser_row(r[0]), log

    # ------------------------------------------------------------ escrita (CRUD)
    def inserir_ciclista(self, nome, pais, nascimento):
        log = []
        nome = (nome or '').strip()
        if len(nome) < 3:
            raise ApiError(400, 'Informe o nome do ciclista')
        cid = ciclista_id(nome)
        pais = (pais or '').strip().upper() or None
        rows = self._ex(log, 'INSERT INTO ciclistas (ciclista_id, nome, pais, data_nascimento) '
                             'VALUES (?, ?, ?, ?) IF NOT EXISTS',
                        (cid, nome, uv(pais), uv(to_date(nascimento))))
        aplicado = bool(rows[0]['[applied]'])
        if aplicado:
            self.ciclistas[str(cid)] = {'id': str(cid), 'nome': nome, 'pais': pais, 'k': busca_key(nome)}
        return {'aplicado': aplicado, 'ciclista_id': str(cid),
                'mensagem': 'Ciclista inserido.' if aplicado else
                'Já existia um ciclista com esse nome (o IF NOT EXISTS não sobrescreve). O id é um UUID v5 '
                'gerado do nome normalizado, igual ao da carga.'}, log

    def inserir_etapa(self, d):
        log = []
        ano, ordem = int(d['ano']), int(d['ordem'])
        self._ex(log, 'INSERT INTO etapas (ano, ordem, numero, data_etapa, tipo, distancia_km, origem, destino, vencedor) '
                      'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (ano, ordem, str(d.get('numero') or ordem), to_date(d.get('data_etapa')),
                  d.get('tipo') or 'Plain stage', dec(d.get('distancia_km')), d.get('origem') or None,
                  d.get('destino') or None, d.get('vencedor') or None))
        return {'mensagem': f'Etapa {ano}/{ordem} gravada (INSERT no Cassandra é um upsert: se já existia, foi substituída).'}, log

    def inserir_resultado(self, d):
        log = []
        ano, ordem = int(d['ano']), int(d['ordem'])
        status = (d.get('status') or 'FIN').upper()
        if status not in STATUS_VALIDOS:
            raise ApiError(400, f'status deve ser um de {", ".join(STATUS_VALIDOS)}')
        posicao = int(d['posicao']) if status == 'FIN' else NAO_CLASSIFICADO
        if status == 'FIN' and posicao < 1:
            raise ApiError(400, 'posição deve ser >= 1')
        etapa = self._etapa(log, ano, ordem)
        if not etapa:
            raise ApiError(404, f'Etapa {ano}/{ordem} não existe: cadastre a etapa primeiro')
        try:
            cid = uuid.UUID(d['ciclista_id'])
        except Exception:
            raise ApiError(400, 'Escolha um ciclista')
        c = self._ex(log, 'SELECT nome FROM ciclistas WHERE ciclista_id = ?', (cid,))
        if not c:
            raise ApiError(404, 'Ciclista não existe: cadastre o ciclista primeiro')
        idade = int(d['idade']) if d.get('idade') not in (None, '') else None
        pontos = int(d['pontos']) if d.get('pontos') not in (None, '') else None
        equipe = d.get('equipe') or None
        s1 = self._prep('INSERT INTO resultados_por_etapa (ano, ordem, posicao, ciclista_id, nome, equipe, idade, status, pontos) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)')
        p1 = (ano, ordem, posicao, cid, c[0]['nome'], uv(equipe), uv(idade), status, uv(pontos))
        s2 = self._prep('INSERT INTO resultados_por_ciclista (ciclista_id, ano, ordem, posicao, status, equipe, idade, pontos, '
                        'data_etapa, tipo, distancia_km) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
        p2 = (cid, ano, ordem, posicao, status, uv(equipe), uv(idade), uv(pontos), etapa['data_etapa'],
              etapa['tipo'], etapa['distancia_km'])
        self._batch(log, [(s1, p1), (s2, p2)])
        return {'mensagem': 'Resultado gravado nas duas tabelas (resultados_por_etapa e resultados_por_ciclista) '
                            'dentro de um LOGGED BATCH: a duplicação é o preço de consultar sem JOIN.'}, log

    def _batch(self, log, itens):
        b = BatchStatement(batch_type=BatchType.LOGGED)
        textos = []
        for ps, params in itens:
            b.add(ps, params)
            textos.append('  ' + fmt_cql(ps.query_string, [None if p is UNSET_VALUE else p for p in params]) + ';')
        t = time.perf_counter()
        self.session.execute(b)
        log.append({'cql': 'BEGIN BATCH\n' + '\n'.join(textos) + '\nAPPLY BATCH;',
                    'ms': round((time.perf_counter() - t) * 1000, 1)})

    def atualizar_cadastro(self, d):
        log = []
        try:
            cid = uuid.UUID(d['ciclista_id'])
        except Exception:
            raise ApiError(400, 'Escolha um ciclista')
        pais = (d.get('pais') or '').strip().upper() or None
        nasc = to_date(d.get('data_nascimento'))
        if pais is None and nasc is None:
            raise ApiError(400, 'Informe o país e/ou a data de nascimento')
        rows = self._ex(log, 'UPDATE ciclistas SET pais = ?, data_nascimento = ? WHERE ciclista_id = ? IF EXISTS',
                        (uv(pais), uv(nasc), cid))
        if not rows[0]['[applied]']:
            raise ApiError(404, 'Ciclista não existe (IF EXISTS impede criar linha por engano)')
        if str(cid) in self.ciclistas:
            self.ciclistas[str(cid)]['pais'] = pais or self.ciclistas[str(cid)]['pais']
        return {'mensagem': 'Cadastro atualizado. O nome não é alterado aqui porque está desnormalizado em '
                            'resultados_por_etapa (mudar o nome exigiria reescrever todas as linhas do ciclista).'}, log

    def desclassificar(self, d):
        log = []
        ano, ordem = int(d['ano']), int(d['ordem'])
        try:
            cid = uuid.UUID(d['ciclista_id'])
        except Exception:
            raise ApiError(400, 'Escolha um ciclista')
        r = self._ex(log, 'SELECT * FROM resultados_por_ciclista WHERE ciclista_id = ? AND ano = ? AND ordem = ?',
                     (cid, ano, ordem))
        if not r:
            raise ApiError(404, 'Esse ciclista não tem resultado nessa etapa')
        r = r[0]
        if r['status'] == 'DSQ':
            raise ApiError(409, 'Resultado já está como DSQ')
        nome = self.ciclistas.get(str(cid), {}).get('nome') or (
            self._ex(log, 'SELECT nome FROM ciclistas WHERE ciclista_id = ?', (cid,)) or [{'nome': None}])[0]['nome']
        apagar = self._prep('DELETE FROM resultados_por_etapa WHERE ano = ? AND ordem = ? AND posicao = ? AND ciclista_id = ?')
        novo = self._prep('INSERT INTO resultados_por_etapa (ano, ordem, posicao, ciclista_id, nome, equipe, idade, status) '
                          'VALUES (?, ?, ?, ?, ?, ?, ?, ?)')
        upd = self._prep('UPDATE resultados_por_ciclista SET posicao = ?, status = ?, pontos = ? '
                         'WHERE ciclista_id = ? AND ano = ? AND ordem = ?')
        self._batch(log, [
            (apagar, (ano, ordem, r['posicao'], cid)),
            (novo, (ano, ordem, NAO_CLASSIFICADO, cid, nome, uv(r['equipe']), uv(r['idade']), 'DSQ')),
            (upd, (NAO_CLASSIFICADO, 'DSQ', None, cid, ano, ordem))])
        return {'mensagem': f'Desclassificado (era {r["posicao"]}º). Em resultados_por_etapa a posição faz parte da '
                            'chave de clustering, então o UPDATE vira DELETE + INSERT; em resultados_por_ciclista '
                            'posicao não é chave e basta um UPDATE.'}, log

    def cancelar_etapa(self, d):
        log = []
        ano, ordem = int(d['ano']), int(d['ordem'])
        existe = self._etapa(log, ano, ordem)
        ids = self._ex(log, 'SELECT ciclista_id FROM resultados_por_etapa WHERE ano = ? AND ordem = ?', (ano, ordem))
        if not existe and not ids:
            raise ApiError(404, f'Etapa {ano}/{ordem} não encontrada')
        if ids:
            self._many(log, 'DELETE FROM resultados_por_ciclista WHERE ciclista_id = ? AND ano = ? AND ordem = ?',
                       [(r['ciclista_id'], ano, ordem) for r in ids])
        self._ex(log, 'DELETE FROM resultados_por_etapa WHERE ano = ? AND ordem = ?', (ano, ordem))
        self._ex(log, 'DELETE FROM etapas WHERE ano = ? AND ordem = ?', (ano, ordem))
        return {'mensagem': f'Etapa cancelada: {len(ids)} resultados removidos. Na tabela por etapa foi um único '
                            'DELETE de partição; na tabela por ciclista foi um DELETE por linha, '
                            'porque cada resultado está em uma partição diferente.'}, log

    # ------------------------------------------------------------ avançado
    def cluster_info(self):
        meta = self.cluster.metadata
        ks = meta.keyspaces[KS]
        rf, rs = self._rf()
        nos = [{'endereco': str(h.address), 'dc': h.datacenter, 'rack': h.rack, 'ativo': bool(h.is_up),
                'versao': h.release_version} for h in meta.all_hosts()]
        tabelas = []
        for nome, t in ks.tables.items():
            tabelas.append({'tabela': nome, 'particao': [c.name for c in t.partition_key],
                            'clustering': [{'coluna': c.name, 'ordem': 'DESC' if c.is_reversed else 'ASC'}
                                           for c in t.clustering_key]})
        return {'keyspace': KS, 'replicacao': rs.export_for_schema(), 'rf': rf,
                'nos': sorted(nos, key=lambda n: n['endereco']),
                'tabelas': sorted(tabelas, key=lambda t: t['tabela'])}, []

    def particoes(self, ano):
        log = []
        et = self._ex(log, 'SELECT ordem FROM etapas WHERE ano = ?', (ano,))
        meta = self.cluster.metadata
        ps_r = self._prep('SELECT token(ano, ordem) AS tk FROM resultados_por_etapa WHERE ano = ? AND ordem = ? LIMIT 1')
        ps_e = self._prep('SELECT token(ano) AS tk FROM etapas WHERE ano = ? LIMIT 1')
        lo, span = -2 ** 63, 2 ** 64
        out = {'ano': ano, 'resultados_por_etapa': [], 'etapas': None}
        t = time.perf_counter()
        b = ps_e.bind((ano,))
        row = self.session.execute(b).one()
        if row:
            out['etapas'] = {'token': str(row['tk']), 'frac': (row['tk'] - lo) / span,
                             'replicas': [str(h.address) for h in meta.get_replicas(KS, b.routing_key)]}
        for e in et:
            b = ps_r.bind((ano, e['ordem']))
            row = self.session.execute(b).one()
            if row:
                out['resultados_por_etapa'].append({
                    'ordem': e['ordem'], 'token': str(row['tk']), 'frac': (row['tk'] - lo) / span,
                    'replicas': [str(h.address) for h in meta.get_replicas(KS, b.routing_key)]})
        out['resultados_por_etapa'].sort(key=lambda x: x['ordem'])
        log.append({'cql': fmt_cql(ps_r.query_string, (ano, '<ordem>')), 'ms': round((time.perf_counter() - t) * 1000, 1),
                    'n': len(out['resultados_por_etapa']) + 1})
        return out, log

    def teste_consistencia(self, ano, ordem, cl):
        cl = cl.upper()
        if cl not in CLS:
            raise ApiError(400, 'Nível de consistência inválido')
        rf, _ = self._rf()
        precisa = {'ONE': 1, 'LOCAL_ONE': 1, 'TWO': 2, 'QUORUM': rf // 2 + 1, 'LOCAL_QUORUM': rf // 2 + 1, 'ALL': rf}[cl]
        cql = 'SELECT posicao, nome FROM resultados_por_etapa WHERE ano = ? AND ordem = ? LIMIT 3'
        ps = self._prep(cql)
        b = ps.bind((ano, ordem))
        b.consistency_level = CLS[cl]
        replicas = [str(h.address) for h in self.cluster.metadata.get_replicas(KS, b.routing_key)]
        t = time.perf_counter()
        try:
            rows = list(self.session.execute(b))
            ok, erro = True, None
        except Exception as e:  # Unavailable, ReadTimeout, NoHostAvailable...
            rows, ok, erro = [], False, f'{type(e).__name__}: {e}'
        ms = round((time.perf_counter() - t) * 1000, 1)
        return {'ok': ok, 'erro': erro, 'cl': cl, 'rf': rf, 'replicas_necessarias': precisa, 'replicas': replicas,
                'linhas': [ser_row(r) for r in rows], 'ms': ms}, [
            {'cql': f'CONSISTENCY {cl};\n' + fmt_cql(cql, (ano, ordem)), 'ms': ms}]

    def console(self, texto):
        q = (texto or '').strip().rstrip(';').strip()
        if not re.match(r'(?is)^select\s', q) or ';' in q:
            raise ApiError(400, 'O console aceita apenas uma instrução SELECT.')
        if not re.search(r'(?i)\blimit\b', q):
            if re.search(r'(?i)\ballow\s+filtering\s*$', q):
                q = re.sub(r'(?i)\s*allow\s+filtering\s*$', ' LIMIT 100 ALLOW FILTERING', q)
            else:
                q += ' LIMIT 100'
        t = time.perf_counter()
        try:
            rows = list(self.session.execute(SimpleStatement(q, fetch_size=200), timeout=20))[:200]
        except Exception as e:
            raise ApiError(400, f'{type(e).__name__}: {e}')
        ms = round((time.perf_counter() - t) * 1000, 1)
        cols = list(rows[0].keys()) if rows else []
        return {'colunas': cols, 'linhas': [ser_row(r) for r in rows], 'cql': q}, [{'cql': q, 'ms': ms}]


def _resumo_etapa(rows):
    por_status = {}
    for r in rows:
        por_status[r['status']] = por_status.get(r['status'], 0) + 1
    return {'participantes': len(rows), 'finalizaram': por_status.get('FIN', 0),
            'nao_classificados': len(rows) - por_status.get('FIN', 0), 'por_status': por_status,
            'idade_media': media([r['idade'] for r in rows])}
