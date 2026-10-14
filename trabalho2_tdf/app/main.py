"""API do sistema Le Tour — Estatísticas (FastAPI + Apache Cassandra).

Execução:
    uvicorn app.main:app --reload
Variáveis de ambiente:
    TDF_MODE   auto (padrão) | cassandra | demo
    TDF_HOSTS  nós de contato do Cassandra (padrão 127.0.0.1)
    TDF_DADOS  pasta com os CSVs, usada só no modo demo (padrão ./dados)
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .common import ApiError

BASE = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger('tdf')
state = {'db': None, 'aviso': None}


def conectar():
    modo = os.getenv('TDF_MODE', 'auto').lower()
    hosts = [h.strip() for h in os.getenv('TDF_HOSTS', '127.0.0.1').split(',') if h.strip()]
    if modo in ('auto', 'cassandra'):
        try:
            from .db_cassandra import CassandraDB
            db = CassandraDB(hosts, int(os.getenv('TDF_PORT', '9042')))
            log.warning('Conectado ao Cassandra em %s', hosts)
            return db, None
        except Exception as e:  # noqa: BLE001
            if modo == 'cassandra':
                raise
            state['aviso'] = f'Cassandra indisponível ({type(e).__name__}); usando CSVs em memória.'
            log.warning(state['aviso'])
    from .db_demo import DemoDB
    return DemoDB(os.getenv('TDF_DADOS', os.path.join(BASE, '..', 'dados'))), state['aviso']


@asynccontextmanager
async def lifespan(_app):
    state['db'], state['aviso'] = conectar()
    yield


app = FastAPI(title='Le Tour — Estatísticas', lifespan=lifespan)


@app.exception_handler(ApiError)
async def api_error(_r: Request, e: ApiError):
    return JSONResponse({'erro': e.msg}, status_code=e.status)


@app.exception_handler(Exception)
async def erro_geral(_r: Request, e: Exception):
    log.exception('erro')
    return JSONResponse({'erro': f'{type(e).__name__}: {e}'}, status_code=500)


def out(res):
    data, cql = res
    return {'data': data, 'cql': cql}


db = lambda: state['db']  # noqa: E731


@app.get('/api/modo')
def modo():
    return {'modo': db().modo, 'aviso': state['aviso']}


@app.get('/api/resumo')
def resumo():
    return out(db().resumo())


@app.get('/api/edicoes')
def edicoes():
    return out(db().edicoes())


@app.get('/api/edicoes/{ano}')
def edicao(ano: int):
    return out(db().edicao(ano))


@app.get('/api/etapas/{ano}/{ordem}')
def etapa(ano: int, ordem: int, cl: str = 'ONE'):
    return out(db().ranking(ano, ordem, cl.upper()))


@app.get('/api/ciclistas')
def buscar(q: str = ''):
    return out(db().busca_ciclistas(q))


@app.get('/api/ciclistas/{cid}')
def ciclista(cid: str):
    return out(db().ciclista(cid))


@app.get('/api/agg/edicao/{ano}')
def agg_edicao(ano: int):
    return out(db().agg_edicao(ano))


@app.get('/api/agg/etapa/{ano}/{ordem}')
def agg_etapa(ano: int, ordem: int):
    return out(db().agg_etapa(ano, ordem))


# ---- CRUD de demonstração
@app.post('/api/crud/ciclista')
def c_ciclista(d: dict = Body(...)):
    return out(db().inserir_ciclista(d.get('nome'), d.get('pais'), d.get('data_nascimento')))


@app.post('/api/crud/etapa')
def c_etapa(d: dict = Body(...)):
    return out(db().inserir_etapa(d))


@app.post('/api/crud/resultado')
def c_resultado(d: dict = Body(...)):
    return out(db().inserir_resultado(d))


@app.put('/api/crud/ciclista')
def c_cadastro(d: dict = Body(...)):
    return out(db().atualizar_cadastro(d))


@app.post('/api/crud/desclassificar')
def c_dsq(d: dict = Body(...)):
    return out(db().desclassificar(d))


@app.delete('/api/crud/etapa/{ano}/{ordem}')
def c_cancelar(ano: int, ordem: int):
    return out(db().cancelar_etapa({'ano': ano, 'ordem': ordem}))


# ---- Bastidores (recursos específicos do Cassandra)
@app.get('/api/avancado/cluster')
def a_cluster():
    return out(db().cluster_info())


@app.get('/api/avancado/particoes/{ano}')
def a_particoes(ano: int):
    return out(db().particoes(ano))


@app.get('/api/avancado/consistencia')
def a_consistencia(ano: int, ordem: int, cl: str = 'ONE'):
    return out(db().teste_consistencia(ano, ordem, cl))


@app.post('/api/avancado/console')
def a_console(d: dict = Body(...)):
    return out(db().console(d.get('cql')))


@app.get('/')
def index():
    return FileResponse(os.path.join(BASE, 'static', 'index.html'))


app.mount('/static', StaticFiles(directory=os.path.join(BASE, 'static')), name='static')
