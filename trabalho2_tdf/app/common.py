"""Utilidades compartilhadas entre o modo Cassandra e o modo demonstração."""
import re
import unicodedata
import uuid
import datetime as dt
from decimal import Decimal

NS = uuid.UUID('6ba7b811-9dad-11d1-80b4-00c04fd430c8')  # mesmo namespace do preparar_dados.py
STATUS_VALIDOS = ('FIN', 'DNF', 'DNS', 'OTL', 'DSQ', 'NQ')
NAO_CLASSIFICADO = 9999


def norm_tokens(nome):
    s = unicodedata.normalize('NFKD', str(nome)).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"[^a-z0-9' ]+", ' ', s)
    return ' '.join(sorted(s.split()))


def ciclista_id(nome):
    """UUID v5 determinístico: o mesmo nome (em qualquer ordem) gera o mesmo id."""
    return uuid.uuid5(NS, 'tdf:' + norm_tokens(nome))


def busca_key(texto):
    s = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r"[^a-z0-9 ]+", ' ', s)


def ser(v):
    """Converte valores do driver em tipos JSON."""
    if v is None:
        return None
    if isinstance(v, (uuid.UUID,)):
        return str(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, (int, float, bool, str)):
        return v
    s = str(v)  # cassandra.util.Date, Time etc.
    return s


def ser_row(row):
    if hasattr(row, '_asdict'):
        row = row._asdict()
    return {k: ser(v) for k, v in dict(row).items()}


def categoria(tipo):
    """Agrupa os tipos de etapa do dataset em 5 categorias visuais."""
    t = (tipo or '').lower()
    if 'team time trial' in t:
        return 'tte'
    if 'time trial' in t:
        return 'crl'
    if 'mountain' in t and 'medium' not in t:
        return 'montanha'
    if 'hilly' in t or 'medium mountain' in t or 'intermediate' in t:
        return 'colinas'
    return 'plano'


def dec(x):
    return None if x in (None, '') else Decimal(str(x))


def to_date(x):
    if x in (None, ''):
        return None
    if isinstance(x, dt.date):
        return x
    return dt.date.fromisoformat(str(x)[:10])


def media(valores):
    v = [x for x in valores if x is not None]
    return round(sum(v) / len(v), 1) if v else None


def estatisticas_historico(linhas):
    """Estatísticas de um ciclista a partir das linhas de resultados_por_ciclista."""
    fin = [r for r in linhas if r['status'] == 'FIN']
    por_ano = {}
    for r in linhas:
        a = por_ano.setdefault(r['ano'], {'ano': r['ano'], 'etapas': 0, 'vitorias': 0, 'top10': 0})
        a['etapas'] += 1
        if r['status'] == 'FIN' and r['posicao'] == 1:
            a['vitorias'] += 1
        if r['status'] == 'FIN' and r['posicao'] <= 10:
            a['top10'] += 1
    return {
        'etapas': len(linhas),
        'vitorias': sum(1 for r in fin if r['posicao'] == 1),
        'podios': sum(1 for r in fin if r['posicao'] <= 3),
        'top10': sum(1 for r in fin if r['posicao'] <= 10),
        'melhor_posicao': min((r['posicao'] for r in fin), default=None),
        'abandonos': sum(1 for r in linhas if r['status'] in ('DNF', 'DNS', 'OTL', 'DSQ')),
        'anos': sorted(por_ano.values(), key=lambda a: a['ano']),
    }


class ApiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status
        self.msg = msg


def fmt_cql(cql, params=()):
    """Substitui os '?' pelos valores, só para exibir o CQL executado na interface."""
    it = iter(params or ())

    def sub(_m):
        try:
            v = next(it)
        except StopIteration:
            return '?'
        if v is None:
            return 'null'
        if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
            return str(v)
        if isinstance(v, bool):
            return 'true' if v else 'false'
        if isinstance(v, (uuid.UUID,)):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"
    return re.sub(r'\?', sub, cql)
