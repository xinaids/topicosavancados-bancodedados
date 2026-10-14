"""Modo demonstração: mesma API, mas lendo os CSVs em memória (sem Cassandra).

Serve para desenvolver e visualizar a interface sem o banco. Tudo que depende de um cluster
real (nós, tokens, consistência) é SIMULADO e aparece marcado como tal na interface.
"""
import hashlib
import os
import uuid

import pandas as pd

from .common import (ApiError, NAO_CLASSIFICADO, STATUS_VALIDOS, busca_key, categoria, ciclista_id, estatisticas_historico,
                     fmt_cql, media, ser, ser_row, to_date)

NOS = [('10.0.0.11', 'rack1'), ('10.0.0.12', 'rack2'), ('10.0.0.13', 'rack3')]


def _registros(df):
    return df.astype(object).where(df.notna(), None).to_dict('records')


class DemoDB:
    modo = 'demo'

    def __init__(self, pasta):
        L = lambda n, **kw: pd.read_csv(os.path.join(pasta, n), **kw)
        self.edicoes_ = {r['ano']: r for r in _registros(L('edicoes.csv', dtype={'edicao': 'Int64', 'vitorias_etapa': 'Int64',
                                                                                   'etapas_lideradas': 'Int64'}))}
        self.etapas_ = {}
        for r in _registros(L('etapas.csv', dtype={'numero': str})):
            self.etapas_.setdefault(r['ano'], {})[r['ordem']] = r
        ints = {'posicao': 'Int64', 'idade': 'Int64', 'pontos': 'Int64'}
        self.por_etapa = {}
        for r in _registros(L('resultados_por_etapa.csv', dtype=ints)):
            self.por_etapa.setdefault((r['ano'], r['ordem']), []).append(r)
        for v in self.por_etapa.values():
            v.sort(key=lambda r: (r['posicao'], r['ciclista_id']))
        self.por_ciclista = {}
        for r in _registros(L('resultados_por_ciclista.csv', dtype=ints)):
            self.por_ciclista.setdefault(r['ciclista_id'], []).append(r)
        for v in self.por_ciclista.values():
            v.sort(key=lambda r: (r['ano'], r['ordem']), reverse=True)
        self.ciclistas = {}
        for r in _registros(L('ciclistas.csv')):
            self.ciclistas[r['ciclista_id']] = {'id': r['ciclista_id'], 'nome': r['nome'], 'pais': r['pais'],
                                                'data_nascimento': r['data_nascimento'], 'k': busca_key(r['nome'])}

    def _log(self, cql, params=()):
        return [{'cql': fmt_cql(cql, params), 'ms': 0, 'demo': True}]

    # ------------------------------------------------------------ leitura
    def resumo(self):
        return {'edicoes': len(self.edicoes_), 'edicoes_com_resultados': sum(1 for e in self.edicoes_.values() if e['com_resultados']),
                'etapas': sum(len(v) for v in self.etapas_.values()), 'ciclistas': len(self.ciclistas),
                'resultados': sum(len(v) for v in self.por_etapa.values()),
                'ano_min': min(self.edicoes_), 'ano_max': max(self.edicoes_)}, self._log('SELECT COUNT(*) FROM ...')

    def edicoes(self):
        return [ser_row(self.edicoes_[a]) for a in sorted(self.edicoes_)], self._log('SELECT * FROM edicoes')

    def edicao(self, ano):
        if ano not in self.edicoes_:
            raise ApiError(404, f'Edição {ano} não encontrada')
        et = [{**ser_row(self.etapas_[ano][o]), 'categoria': categoria(self.etapas_[ano][o]['tipo'])}
              for o in sorted(self.etapas_.get(ano, {}))]
        return {'edicao': ser_row(self.edicoes_[ano]), 'etapas': et}, self._log('SELECT * FROM etapas WHERE ano = ?', (ano,))

    def ranking(self, ano, ordem, cl='ONE'):
        e = self.etapas_.get(ano, {}).get(ordem)
        if not e:
            raise ApiError(404, f'Etapa {ano}/{ordem} não encontrada')
        rows = [{k: r[k] for k in ('posicao', 'ciclista_id', 'nome', 'equipe', 'idade', 'status', 'pontos')}
                for r in self.por_etapa.get((ano, ordem), [])]
        rows = [ser_row(r) for r in rows]
        por_status = {}
        for r in rows:
            por_status[r['status']] = por_status.get(r['status'], 0) + 1
        return {'etapa': {**ser_row(e), 'categoria': categoria(e['tipo'])}, 'resultados': rows,
                'resumo': {'participantes': len(rows), 'finalizaram': por_status.get('FIN', 0),
                           'nao_classificados': len(rows) - por_status.get('FIN', 0), 'por_status': por_status,
                           'idade_media': media([r['idade'] for r in rows])}}, self._log(
            'SELECT posicao, ciclista_id, nome, equipe, idade, status, pontos FROM resultados_por_etapa '
            'WHERE ano = ? AND ordem = ?', (ano, ordem))

    def busca_ciclistas(self, q, limite=15):
        tokens = busca_key(q).split()
        if not tokens:
            return [], []
        a = [c for c in self.ciclistas.values() if all(t in c['k'] for t in tokens)]
        a.sort(key=lambda c: (not c['k'].startswith(tokens[0]), c['nome']))
        return [{k: c[k] for k in ('id', 'nome', 'pais')} for c in a[:limite]], []

    def ciclista(self, cid):
        c = self.ciclistas.get(cid)
        if not c:
            raise ApiError(404, 'Ciclista não encontrado')
        hist = [ser_row(r) for r in self.por_ciclista.get(cid, [])]
        pontos = [r['pontos'] for r in hist if r['pontos'] is not None]
        return {'ciclista': {'ciclista_id': cid, 'nome': c['nome'], 'pais': c['pais'], 'data_nascimento': c['data_nascimento']},
                'estatisticas': estatisticas_historico(hist),
                'agregado_cql': {'etapas': len(hist), 'melhor_posicao_cql': min((r['posicao'] for r in hist), default=None),
                                 'pontos': sum(pontos) if pontos else None},
                'historico': hist}, self._log('SELECT * FROM resultados_por_ciclista WHERE ciclista_id = ?', (cid,))

    # ------------------------------------------------------------ agregações
    def agg_edicao(self, ano):
        if ano not in self.etapas_:
            raise ApiError(404, f'Edição {ano} sem etapas')
        por_etapa, equipes = [], {}
        for o in sorted(self.etapas_[ano]):
            e, rs = self.etapas_[ano][o], self.por_etapa.get((ano, o), [])
            top = next((r for r in rs if r['posicao'] == 1), None)
            if top and top['equipe']:
                equipes[top['equipe']] = equipes.get(top['equipe'], 0) + 1
            por_etapa.append({'ordem': o, 'numero': e['numero'], 'tipo': e['tipo'], 'categoria': categoria(e['tipo']),
                              'distancia_km': ser(e['distancia_km']), 'participantes': len(rs),
                              'idade_media': media([r['idade'] for r in rs]),
                              'nao_classificados': sum(1 for r in rs if r['posicao'] == NAO_CLASSIFICADO),
                              'vencedor': top['nome'] if top else e['vencedor'],
                              'equipe_vencedora': top['equipe'] if top else None})
        return {'ano': ano, 'por_etapa': por_etapa,
                'vitorias_por_equipe': sorted(({'equipe': k, 'vitorias': v} for k, v in equipes.items()),
                                              key=lambda x: -x['vitorias'])}, self._log(
            'SELECT COUNT(*) AS participantes, AVG(CAST(idade AS double)) AS idade_media FROM resultados_por_etapa '
            'WHERE ano = ? AND ordem = ?', (ano, '<ordem>'))

    def agg_etapa(self, ano, ordem):
        rs = self.por_etapa.get((ano, ordem), [])
        idades = [r['idade'] for r in rs if r['idade'] is not None]
        return {'participantes': len(rs), 'idade_min': min(idades, default=None), 'idade_max': max(idades, default=None),
                'idade_media': media(idades), 'pontos_distribuidos': None}, []

    # ------------------------------------------------------------ escrita (em memória)
    def inserir_ciclista(self, nome, pais, nascimento):
        nome = (nome or '').strip()
        if len(nome) < 3:
            raise ApiError(400, 'Informe o nome do ciclista')
        cid = str(ciclista_id(nome))
        if cid in self.ciclistas:
            return {'aplicado': False, 'ciclista_id': cid, 'mensagem': 'Já existia um ciclista com esse nome (IF NOT EXISTS).'}, \
                self._log('INSERT INTO ciclistas (...) VALUES (...) IF NOT EXISTS')
        self.ciclistas[cid] = {'id': cid, 'nome': nome, 'pais': (pais or '').upper() or None,
                               'data_nascimento': str(to_date(nascimento) or '') or None, 'k': busca_key(nome)}
        return {'aplicado': True, 'ciclista_id': cid, 'mensagem': 'Ciclista inserido (em memória, modo demonstração).'}, \
            self._log('INSERT INTO ciclistas (ciclista_id, nome, pais, data_nascimento) VALUES (?, ?, ?, ?) IF NOT EXISTS',
                      (cid, nome, pais, nascimento))

    def inserir_etapa(self, d):
        ano, ordem = int(d['ano']), int(d['ordem'])
        self.etapas_.setdefault(ano, {})[ordem] = {
            'ano': ano, 'ordem': ordem, 'numero': str(d.get('numero') or ordem), 'data_etapa': str(to_date(d.get('data_etapa')) or ''),
            'tipo': d.get('tipo') or 'Plain stage', 'distancia_km': float(d['distancia_km']) if d.get('distancia_km') else None,
            'origem': d.get('origem') or None, 'destino': d.get('destino') or None, 'vencedor': d.get('vencedor') or None}
        return {'mensagem': f'Etapa {ano}/{ordem} gravada (modo demonstração).'}, self._log('INSERT INTO etapas (...) VALUES (...)')

    def inserir_resultado(self, d):
        ano, ordem = int(d['ano']), int(d['ordem'])
        status = (d.get('status') or 'FIN').upper()
        if status not in STATUS_VALIDOS:
            raise ApiError(400, 'status inválido')
        e = self.etapas_.get(ano, {}).get(ordem)
        if not e:
            raise ApiError(404, f'Etapa {ano}/{ordem} não existe: cadastre a etapa primeiro')
        c = self.ciclistas.get(d.get('ciclista_id'))
        if not c:
            raise ApiError(404, 'Ciclista não existe: cadastre o ciclista primeiro')
        pos = int(d['posicao']) if status == 'FIN' else NAO_CLASSIFICADO
        num = lambda k: int(d[k]) if d.get(k) not in (None, '') else None
        base = {'posicao': pos, 'status': status, 'equipe': d.get('equipe') or None, 'idade': num('idade'), 'pontos': num('pontos')}
        lst = self.por_etapa.setdefault((ano, ordem), [])
        lst[:] = [r for r in lst if not (r['ciclista_id'] == c['id'])]
        lst.append({'ano': ano, 'ordem': ordem, 'ciclista_id': c['id'], 'nome': c['nome'], **base})
        lst.sort(key=lambda r: (r['posicao'], r['ciclista_id']))
        h = self.por_ciclista.setdefault(c['id'], [])
        h[:] = [r for r in h if not (r['ano'] == ano and r['ordem'] == ordem)]
        h.append({'ciclista_id': c['id'], 'ano': ano, 'ordem': ordem, **base, 'data_etapa': e['data_etapa'], 'tipo': e['tipo'],
                  'distancia_km': e['distancia_km']})
        h.sort(key=lambda r: (r['ano'], r['ordem']), reverse=True)
        return {'mensagem': 'Resultado gravado nas duas tabelas (modo demonstração).'}, self._log('BEGIN BATCH ... APPLY BATCH')

    def atualizar_cadastro(self, d):
        c = self.ciclistas.get(d.get('ciclista_id'))
        if not c:
            raise ApiError(404, 'Ciclista não existe')
        if d.get('pais'):
            c['pais'] = d['pais'].upper()
        if d.get('data_nascimento'):
            c['data_nascimento'] = str(to_date(d['data_nascimento']))
        return {'mensagem': 'Cadastro atualizado (modo demonstração).'}, self._log('UPDATE ciclistas SET ... IF EXISTS')

    def desclassificar(self, d):
        ano, ordem, cid = int(d['ano']), int(d['ordem']), d.get('ciclista_id')
        rs = self.por_etapa.get((ano, ordem), [])
        r = next((x for x in rs if x['ciclista_id'] == cid), None)
        if not r:
            raise ApiError(404, 'Esse ciclista não tem resultado nessa etapa')
        if r['status'] == 'DSQ':
            raise ApiError(409, 'Resultado já está como DSQ')
        antiga = r['posicao']
        r.update(posicao=NAO_CLASSIFICADO, status='DSQ', pontos=None)
        rs.sort(key=lambda x: (x['posicao'], x['ciclista_id']))
        for h in self.por_ciclista.get(cid, []):
            if h['ano'] == ano and h['ordem'] == ordem:
                h.update(posicao=NAO_CLASSIFICADO, status='DSQ', pontos=None)
        return {'mensagem': f'Desclassificado (era {antiga}º) (modo demonstração).'}, self._log('BEGIN BATCH ... APPLY BATCH')

    def cancelar_etapa(self, d):
        ano, ordem = int(d['ano']), int(d['ordem'])
        if ordem not in self.etapas_.get(ano, {}) and (ano, ordem) not in self.por_etapa:
            raise ApiError(404, f'Etapa {ano}/{ordem} não encontrada')
        rs = self.por_etapa.pop((ano, ordem), [])
        for r in rs:
            h = self.por_ciclista.get(r['ciclista_id'], [])
            h[:] = [x for x in h if not (x['ano'] == ano and x['ordem'] == ordem)]
        self.etapas_.get(ano, {}).pop(ordem, None)
        return {'mensagem': f'Etapa cancelada: {len(rs)} resultados removidos (modo demonstração).'}, self._log(
            'DELETE FROM resultados_por_etapa WHERE ano = ? AND ordem = ?', (ano, ordem))

    # ------------------------------------------------------------ avançado (simulado)
    def cluster_info(self):
        tabelas = [
            ('ciclistas', ['ciclista_id'], []), ('edicoes', ['ano'], []),
            ('etapas', ['ano'], [('ordem', 'ASC')]),
            ('resultados_por_etapa', ['ano', 'ordem'], [('posicao', 'ASC'), ('ciclista_id', 'ASC')]),
            ('resultados_por_ciclista', ['ciclista_id'], [('ano', 'DESC'), ('ordem', 'DESC')])]
        return {'simulado': True, 'keyspace': 'ciclismo', 'rf': 3,
                'replicacao': "{'class': 'SimpleStrategy', 'replication_factor': '3'}",
                'nos': [{'endereco': ip, 'dc': 'datacenter1', 'rack': rk, 'ativo': True, 'versao': '5.0'} for ip, rk in NOS],
                'tabelas': [{'tabela': n, 'particao': p, 'clustering': [{'coluna': c, 'ordem': o} for c, o in cl]}
                            for n, p, cl in tabelas]}, []

    def _token(self, chave):
        h = int.from_bytes(hashlib.sha256(chave.encode()).digest()[:8], 'big', signed=True)
        return h, [NOS[(i + (h % 3)) % 3][0] for i in range(3)]

    def particoes(self, ano):
        out = {'simulado': True, 'ano': ano, 'resultados_por_etapa': [], 'etapas': None}
        t, rep = self._token(f'etapas:{ano}')
        out['etapas'] = {'token': str(t), 'frac': (t + 2 ** 63) / 2 ** 64, 'replicas': rep}
        for o in sorted(self.etapas_.get(ano, {})):
            if (ano, o) in self.por_etapa:
                t, rep = self._token(f'{ano}:{o}')
                out['resultados_por_etapa'].append({'ordem': o, 'token': str(t), 'frac': (t + 2 ** 63) / 2 ** 64, 'replicas': rep})
        return out, []

    def teste_consistencia(self, ano, ordem, cl):
        cl = cl.upper()
        precisa = {'ONE': 1, 'LOCAL_ONE': 1, 'TWO': 2, 'QUORUM': 2, 'LOCAL_QUORUM': 2, 'ALL': 3}.get(cl)
        if precisa is None:
            raise ApiError(400, 'Nível de consistência inválido')
        _, rep = self._token(f'{ano}:{ordem}')
        rs = self.por_etapa.get((ano, ordem), [])[:3]
        return {'simulado': True, 'ok': True, 'erro': None, 'cl': cl, 'rf': 3, 'replicas_necessarias': precisa,
                'replicas': rep, 'linhas': [{'posicao': r['posicao'], 'nome': r['nome']} for r in rs], 'ms': 1.0}, []

    def console(self, texto):
        raise ApiError(501, 'O console CQL só funciona com o Cassandra conectado (modo demonstração ativo).')
