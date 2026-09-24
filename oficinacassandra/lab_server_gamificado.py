"""
lab_server_gamificado.py - Oficina Cassandra em formato de jogo (v2 - 10 exercicios)
Servidor central: roda numa maquina, todos os jogadores conectam pelo IP local.

Instalacao (so na maquina servidor):
    pip install flask cassandra-driver

Uso:
    python3 lab_server_gamificado.py

Jogadores acessam: http://IP_DO_SERVIDOR:5000
Projetor acessa:    http://IP_DO_SERVIDOR:5000/projetor
"""

from flask import Flask, request, render_template_string, session as flask_session, redirect, url_for
from cassandra.cluster import Cluster
from cassandra import InvalidRequest
import re

app = Flask(__name__)
app.secret_key = "oficina-cassandra-2026"  # troque se quiser

cluster = Cluster(["127.0.0.1"], port=9042)
db = cluster.connect()

db.execute("""
    CREATE KEYSPACE IF NOT EXISTS oficina
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
""")
db.set_keyspace("oficina")

TABELA_BASE = "livros"


def tabela_do_jogador(nome):
    """Gera um nome de tabela isolado por jogador (evita colisao entre jogadores)."""
    sufixo = re.sub(r"[^a-z0-9_]", "", nome.lower().replace(" ", "_"))
    if not sufixo:
        sufixo = "anon"
    return f"{TABELA_BASE}_{sufixo}"


def resetar_tabela_jogador(nome):
    """Remove a tabela pessoal do jogador, garantindo um comeco limpo."""
    tabela = tabela_do_jogador(nome)
    db.execute(f"DROP TABLE IF EXISTS {tabela}")


def adaptar_comando_para_jogador(texto_cql, nome):
    """
    Substitui o nome de tabela 'livros' (como o jogador digitou)
    pelo nome de tabela isolado dele, sem o jogador perceber a diferenca.
    """
    tabela = tabela_do_jogador(nome)
    return re.sub(r"(?i)\blivros\b", tabela, texto_cql)


def select_seguro(query):
    """
    Executa um SELECT de verificacao. Se o Cassandra recusar por precisar de
    ALLOW FILTERING (porque o jogador escolheu uma ordem de chave diferente
    da esperada), tenta de novo automaticamente com ALLOW FILTERING no final.
    Isso evita que a estrutura de chave escolhida no exercicio 1 quebre a
    validacao dos exercicios seguintes.
    """
    try:
        return db.execute(query)
    except InvalidRequest as e:
        if "ALLOW FILTERING" in str(e):
            return db.execute(query + " ALLOW FILTERING")
        raise


def resultado_como_lista(rows):
    return [dict(zip(row._fields, row)) for row in rows]


# Cada exercicio referencia a tabela generica 'livros' (adaptada por jogador em tempo real).
EXERCICIOS = [
    {
        "id": 1,
        "pontos": 10,
        "enunciado": "Crie uma tabela 'livros' com partition key 'categoria' (text) e clustering key 'codigo' (int), contendo tambem 'titulo' (text), 'autor' (text) e 'ano' (int).",
        "dica": "CREATE TABLE livros (categoria text, codigo int, titulo text, autor text, ano int, PRIMARY KEY (categoria, codigo)).",
        "tipo": "ddl",
    },
    {
        "id": 2,
        "pontos": 10,
        "enunciado": "Insira o livro (categoria='ficcao', codigo=1, titulo='Duna', autor='Frank Herbert', ano=1965) na tabela livros.",
        "gabarito": "INSERT INTO livros (categoria, codigo, titulo, autor, ano) VALUES ('ficcao', 1, 'Duna', 'Frank Herbert', 1965)",
        "verificacao": "SELECT * FROM livros WHERE categoria='ficcao' AND codigo=1",
        "dica": "INSERT INTO livros (categoria, codigo, titulo, autor, ano) VALUES ('ficcao', 1, 'Duna', 'Frank Herbert', 1965).",
        "tipo": "dml_insert",
    },
    {
        "id": 3,
        "pontos": 10,
        "enunciado": "Insira um segundo livro: (categoria='ficcao', codigo=2, titulo='Fundacao', autor='Isaac Asimov', ano=1951).",
        "gabarito": "INSERT INTO livros (categoria, codigo, titulo, autor, ano) VALUES ('ficcao', 2, 'Fundacao', 'Isaac Asimov', 1951)",
        "verificacao": "SELECT * FROM livros WHERE categoria='ficcao' AND codigo=2",
        "dica": "Mesma sintaxe do exercicio anterior, so trocando os valores.",
        "tipo": "dml_insert",
    },
    {
        "id": 4,
        "pontos": 10,
        "enunciado": "Escreva uma consulta que retorne todos os livros da categoria 'ficcao'.",
        "gabarito": "SELECT * FROM livros WHERE categoria = 'ficcao'",
        "dica": "SELECT * FROM livros WHERE categoria = 'ficcao'. Deve trazer os dois livros inseridos.",
        "tipo": "select",
    },
    {
        "id": 5,
        "pontos": 10,
        "enunciado": "Escreva uma consulta que retorne os livros da categoria 'ficcao' ordenados por codigo em ordem decrescente.",
        "gabarito": "SELECT * FROM livros WHERE categoria = 'ficcao' ORDER BY codigo DESC",
        "dica": "Use ORDER BY codigo DESC no final da consulta. So funciona ordenando pela clustering key.",
        "tipo": "select",
    },
    {
        "id": 6,
        "pontos": 10,
        "enunciado": "Atualize o ano do livro (categoria='ficcao', codigo=1) para 2021 (ano do filme de Duna).",
        "gabarito": "UPDATE livros SET ano = 2021 WHERE categoria='ficcao' AND codigo=1",
        "verificacao": "SELECT * FROM livros WHERE categoria='ficcao' AND codigo=1",
        "dica": "UPDATE livros SET ano = 2021 WHERE categoria='ficcao' AND codigo=1.",
        "tipo": "dml_update",
    },
    {
        "id": 7,
        "pontos": 10,
        "enunciado": "Atualize o titulo do livro (categoria='ficcao', codigo=2) para 'Fundacao - Edicao Comemorativa'.",
        "gabarito": "UPDATE livros SET titulo = 'Fundacao - Edicao Comemorativa' WHERE categoria='ficcao' AND codigo=2",
        "verificacao": "SELECT * FROM livros WHERE categoria='ficcao' AND codigo=2",
        "dica": "UPDATE livros SET titulo = '...' WHERE categoria='ficcao' AND codigo=2.",
        "tipo": "dml_update",
    },
    {
        "id": 8,
        "pontos": 10,
        "enunciado": "Adicione uma nova coluna 'disponivel' do tipo boolean na tabela livros.",
        "gabarito": "ALTER TABLE livros ADD disponivel boolean",
        "dica": "ALTER TABLE livros ADD disponivel boolean.",
        "tipo": "alter",
    },
    {
        "id": 9,
        "pontos": 10,
        "enunciado": "Crie um indice secundario na coluna 'autor' e consulte todos os livros de 'Isaac Asimov'.",
        "gabarito": "CREATE INDEX ON livros (autor)",
        "verificacao_extra": "SELECT * FROM livros WHERE autor = 'Isaac Asimov'",
        "dica": "Primeiro: CREATE INDEX ON livros (autor). Depois: SELECT * FROM livros WHERE autor = 'Isaac Asimov'.",
        "tipo": "index_select",
    },
    {
        "id": 10,
        "pontos": 10,
        "enunciado": "Exclua o livro (categoria='ficcao', codigo=2).",
        "gabarito": "DELETE FROM livros WHERE categoria='ficcao' AND codigo=2",
        "verificacao": "SELECT * FROM livros WHERE categoria='ficcao' AND codigo=2",
        "dica": "DELETE FROM livros WHERE categoria='ficcao' AND codigo=2.",
        "tipo": "dml_delete",
    },
]

PONTOS_TOTAIS = sum(e["pontos"] for e in EXERCICIOS)


def validar_exercicio(ex, comando_jogador, nome):
    """Executa o comando do jogador (isolado na tabela pessoal dele) e valida o resultado."""
    tabela = tabela_do_jogador(nome)
    comando_adaptado = adaptar_comando_para_jogador(comando_jogador, nome)

    try:
        db.execute(comando_adaptado)
    except Exception as e:
        erro_str = str(e)
        if ex["tipo"] in ("ddl", "alter", "index_select") and "already exists" in erro_str.lower():
            pass  # reenvio do mesmo exercicio - nao penaliza
        else:
            return False, f"Erro ao executar: {e}"

    if ex["tipo"] == "ddl":
        try:
            select_seguro(f"SELECT * FROM {tabela} LIMIT 1")
            return True, "Tabela criada com sucesso!"
        except Exception as e:
            return False, f"Tabela nao encontrada ou estrutura incorreta: {e}"

    if ex["tipo"] in ("dml_insert", "dml_update"):
        verificacao = adaptar_comando_para_jogador(ex["verificacao"], nome)
        rows = resultado_como_lista(select_seguro(verificacao))
        if not rows:
            return False, "Nenhum registro encontrado apos o comando."
        return True, f"Certo! Estado atual: {rows}"

    if ex["tipo"] == "dml_delete":
        verificacao = adaptar_comando_para_jogador(ex["verificacao"], nome)
        rows = resultado_como_lista(select_seguro(verificacao))
        if rows:
            return False, "O registro ainda existe, delete nao funcionou como esperado."
        return True, "Certo! Registro removido."

    if ex["tipo"] == "select":
        return True, "Consulta executada com sucesso!"

    if ex["tipo"] == "alter":
        try:
            select_seguro(f"SELECT disponivel FROM {tabela} LIMIT 1")
            return True, "Coluna adicionada com sucesso!"
        except Exception as e:
            return False, f"Coluna nao encontrada: {e}"

    if ex["tipo"] == "index_select":
        # o jogador digita CREATE INDEX; validamos rodando a consulta que o indice deveria permitir
        verificacao = adaptar_comando_para_jogador(ex["verificacao_extra"], nome)
        try:
            rows = resultado_como_lista(db.execute(verificacao))
        except Exception:
            rows = resultado_como_lista(select_seguro(verificacao))
        return True, f"Indice criado! Resultado da consulta: {rows}"

    return False, "Tipo de exercicio desconhecido."


def analisar_proximidade(ex, comando_jogador):
    """Analise heuristica simples de proximidade, sem depender de IA/internet."""
    texto = comando_jogador.lower()
    palavras_chave = {
        "ddl": ["create table", "livros", "primary key"],
        "dml_insert": ["insert into", "livros", "values"],
        "dml_update": ["update", "livros", "set", "where"],
        "dml_delete": ["delete from", "livros", "where"],
        "select": ["select", "livros", "where"],
        "alter": ["alter table", "livros", "add"],
        "index_select": ["create index", "livros", "select"],
    }
    componentes = palavras_chave.get(ex["tipo"], [])
    if not componentes:
        return 0, []
    encontrados = sum(1 for c in componentes if c in texto)
    faltantes = [c for c in componentes if c not in texto]
    percentual = round((encontrados / len(componentes)) * 100)
    return percentual, faltantes


# Ranking em memoria: {nome_jogador: {"pontos": int, "resolvidos": set(ids)}}
RANKING = {}

PAGINA_LOGIN = """
<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="UTF-8"><title>Oficina Cassandra - Lobby</title>
<style>
* { box-sizing: border-box; }
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
    background: radial-gradient(circle at top, #1e1e3f 0%, #0a0a18 70%);
    color:white;
}
.card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    backdrop-filter: blur(6px);
    padding: 50px 40px;
    border-radius: 16px;
    text-align:center;
    width: 380px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.emoji { font-size: 48px; margin-bottom: 10px; }
h1 { margin: 0 0 8px; font-size: 26px; background: linear-gradient(90deg,#7f5af0,#2cb67d); -webkit-background-clip:text; background-clip:text; color:transparent; }
p { color: #b8b8d1; margin-bottom: 24px; font-size:14px; }
input {
    padding: 14px; font-size: 16px; width: 100%; margin-bottom: 16px;
    border-radius: 10px; border: 1px solid rgba(255,255,255,0.15);
    background: rgba(255,255,255,0.06); color: white; outline: none;
}
input:focus { border-color: #7f5af0; }
input::placeholder { color: #6f6f8f; }
button {
    padding: 14px; font-size: 16px; width: 100%; border: none; border-radius: 10px;
    background: linear-gradient(90deg,#7f5af0,#2cb67d); color: white; font-weight: bold;
    cursor: pointer;
}
</style></head>
<body>
<div class="card">
    <div class="emoji">🎮</div>
    <h1>Oficina Cassandra</h1>
    <p>Bancos de Dados Orientados a Colunas</p>
    <form method="POST">
        <input type="text" name="nome" placeholder="Digite seu nome" required autofocus>
        <button type="submit">Entrar no lobby</button>
    </form>
</div>
</body></html>
"""

PAGINA_JOGO = """
<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="UTF-8"><title>Oficina Cassandra</title>
<style>
* { box-sizing: border-box; }
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    margin:0; min-height:100vh;
    background: radial-gradient(circle at top, #1e1e3f 0%, #0a0a18 70%);
    color: white; padding: 30px 16px;
}
.container { max-width: 640px; margin: 0 auto; }
.topbar {
    display:flex; justify-content:space-between; align-items:center;
    background: rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1);
    padding: 14px 20px; border-radius: 12px; margin-bottom: 20px;
}
.topbar .nome { color:#b8b8d1; font-size:14px; }
.topbar .pontos { font-size:20px; font-weight:bold; color:#2cb67d; }
.progresso-wrap { margin-bottom: 8px; color:#8888aa; font-size:13px; }
.barra { height:6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden; margin-bottom:24px; }
.barra-fill { height:100%; background: linear-gradient(90deg,#7f5af0,#2cb67d); }
.exercicio {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px; padding: 26px; box-shadow: 0 10px 40px rgba(0,0,0,0.3);
}
.badge { display:inline-block; background: rgba(127,90,240,0.2); color:#a78bfa; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:bold; margin-bottom:14px; }
.enunciado { font-size: 17px; line-height:1.5; margin-bottom:18px; }
.dica-linha { display:flex; align-items:center; gap:8px; margin-bottom: 16px; }
.dica-btn {
    width:26px; height:26px; border-radius:50%; border:1px solid #7f5af0; background:transparent;
    color:#a78bfa; font-weight:bold; font-size:14px; cursor:pointer; flex-shrink:0;
    display:flex; align-items:center; justify-content:center;
}
.dica-texto {
    display:none; background: rgba(127,90,240,0.12); border-left: 3px solid #7f5af0;
    padding: 12px 16px; border-radius: 8px; font-size: 14px; color:#d8d3f7; margin-bottom:16px;
}
.dica-texto.aberta { display:block; }
textarea {
    width:100%; height:90px; font-family:'Consolas',monospace; font-size:14px; padding:14px;
    border-radius: 10px; border: 1px solid rgba(255,255,255,0.15);
    background: rgba(0,0,0,0.3); color:#e0e0f0; outline:none; resize:vertical;
}
textarea:focus { border-color: #7f5af0; }
.enviar {
    margin-top: 14px; padding: 12px 24px; font-size:15px; border:none; border-radius: 10px;
    background: linear-gradient(90deg,#7f5af0,#2cb67d); color:white; font-weight:bold; cursor:pointer;
}
.resultado {
    margin-top: 16px; padding: 14px; border-radius: 10px; font-family:'Consolas',monospace;
    white-space:pre-wrap; font-size: 13px;
}
.resultado.ok { background: rgba(44,182,125,0.15); border:1px solid #2cb67d; color:#8ef0c4; }
.resultado.erro { background: rgba(240,90,90,0.15); border:1px solid #f05a5a; color:#ffb3b3; }
.proximidade { margin-top: 14px; }
.proximidade-topo { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; font-family:'Segoe UI',Arial,sans-serif; font-size:13px; color:#b8b8d1; }
.proximidade-pct { font-weight:bold; font-size:15px; }
.proximidade-barra { height:8px; background:rgba(255,255,255,0.08); border-radius:4px; overflow:hidden; margin-bottom:12px; }
.proximidade-fill { height:100%; border-radius:4px; }
.faltantes { font-family:'Segoe UI',Arial,sans-serif; font-size:13px; }
.faltantes ul { margin: 6px 0 0; padding-left: 18px; color:#ffb3b3; }
.completo {
    text-align:center; background: rgba(44,182,125,0.1); border:1px solid #2cb67d;
    border-radius: 16px; padding: 50px 30px;
}
.completo .emoji { font-size: 56px; margin-bottom: 10px; }
.completo h1 { color:#2cb67d; margin-bottom:8px; }
.completo p { color:#b8b8d1; }
</style>
<script>
function toggleDica() {
    document.getElementById('dica-texto').classList.toggle('aberta');
}
</script>
</head>
<body>
<div class="container">
    <div class="topbar">
        <span class="nome">👤 {{ nome }}</span>
        <span class="pontos">⭐ {{ pontos }} pts</span>
    </div>

    {% if exercicio_atual %}
    <div class="progresso-wrap">Exercicio {{ posicao }} de {{ total }}</div>
    <div class="barra"><div class="barra-fill" style="width: {{ ((posicao - 1) / total * 100) }}%;"></div></div>

    <div class="exercicio">
        <div class="badge">+{{ exercicio_atual.pontos }} pontos</div>
        <div class="enunciado">{{ exercicio_atual.enunciado }}</div>

        {% if exercicio_atual.dica %}
        <div class="dica-linha">
            <button type="button" class="dica-btn" onclick="toggleDica()" title="Ver dica">i</button>
            <span style="color:#8888aa; font-size:13px;">Precisa de uma dica?</span>
        </div>
        <div class="dica-texto" id="dica-texto">💡 {{ exercicio_atual.dica }}</div>
        {% endif %}

        <form method="POST" action="{{ url_for('responder', ex_id=exercicio_atual.id) }}">
            <textarea name="comando" placeholder="Digite seu comando CQL aqui..." autofocus></textarea><br>
            <button type="submit" class="enviar">Enviar resposta ▸</button>
        </form>
        {% if mensagem %}
            <div class="resultado {{ 'ok' if mensagem.startswith('✅') else 'erro' }}">{{ mensagem }}</div>
        {% endif %}
        {% if proximidade %}
        <div class="proximidade">
            <div class="proximidade-topo">
                <span>🎯 Quao perto voce chegou</span>
                <span class="proximidade-pct" style="color: {{ '#2cb67d' if proximidade.percentual >= 70 else '#f0c94a' if proximidade.percentual >= 40 else '#f05a5a' }};">{{ proximidade.percentual }}%</span>
            </div>
            <div class="proximidade-barra">
                <div class="proximidade-fill" style="width: {{ proximidade.percentual }}%; background: {{ '#2cb67d' if proximidade.percentual >= 70 else '#f0c94a' if proximidade.percentual >= 40 else '#f05a5a' }};"></div>
            </div>
            {% if proximidade.faltantes %}
            <div class="faltantes">
                O que ainda falta ou esta incorreto:
                <ul>
                {% for item in proximidade.faltantes %}
                    <li>{{ item }}</li>
                {% endfor %}
                </ul>
            </div>
            {% endif %}
        </div>
        {% endif %}
    </div>
    {% else %}
    <div class="completo">
        <div class="emoji">🎉</div>
        <h1>Parabens!</h1>
        <p>Voce concluiu todos os exercicios com {{ pontos }} pontos.</p>
        <p>Acompanhe o ranking final no telao.</p>
    </div>
    {% endif %}
</div>
</body></html>
"""

PAGINA_PROJETOR = """
<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="UTF-8"><title>Ranking - Oficina Cassandra</title>
<meta http-equiv="refresh" content="3">
<style>
* { box-sizing: border-box; }
body {
    font-family:'Segoe UI', Arial, sans-serif;
    background: radial-gradient(circle at top, #1e1e3f 0%, #0a0a18 70%);
    color:white; margin:0; padding:50px;
}
h1 { text-align:center; font-size:52px; margin-bottom:4px; background: linear-gradient(90deg,#7f5af0,#2cb67d); -webkit-background-clip:text; background-clip:text; color:transparent; }
.subtitulo { text-align:center; color:#8888aa; font-size:20px; margin-bottom:50px; }
table { width:100%; max-width:900px; margin:0 auto; border-collapse:collapse; font-size:26px; }
td, th { padding:18px 24px; text-align:left; }
th { color:#8888aa; font-size:16px; text-transform:uppercase; letter-spacing:1px; border-bottom: 2px solid rgba(255,255,255,0.1); }
tr.linha td { border-bottom: 1px solid rgba(255,255,255,0.06); }
tr.ouro td { color:#FFD700; font-weight:bold; font-size:32px; }
tr.prata td { color:#C0C0C0; font-weight:bold; }
tr.bronze td { color:#CD7F32; font-weight:bold; }
.pos { width:70px; text-align:center; }
</style></head>
<body>
<h1>🏆 Ranking</h1>
<div class="subtitulo">Oficina — Bancos de Dados Orientados a Colunas</div>
<table>
<tr><th class="pos">#</th><th>Jogador</th><th>Pontos</th></tr>
{% for i, (nome_r, dados) in enumerate(ranking_ordenado, 1) %}
<tr class="linha {{ 'ouro' if i==1 else 'prata' if i==2 else 'bronze' if i==3 else '' }}">
    <td class="pos">{% if i==1 %}🥇{% elif i==2 %}🥈{% elif i==3 %}🥉{% else %}{{ i }}{% endif %}</td>
    <td>{{ nome_r }}</td>
    <td>{{ dados.pontos }}</td>
</tr>
{% endfor %}
</table>
</body></html>
"""


def proximo_exercicio(resolvidos):
    for ex in EXERCICIOS:
        if ex["id"] not in resolvidos:
            return ex
    return None


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        if nome:
            flask_session["nome"] = nome
            if nome not in RANKING:
                RANKING[nome] = {"pontos": 0, "resolvidos": set()}
                resetar_tabela_jogador(nome)
            return redirect(url_for("jogo"))
    return render_template_string(PAGINA_LOGIN)


@app.route("/jogo")
def jogo():
    nome = flask_session.get("nome")
    if not nome:
        return redirect(url_for("login"))

    jogador = RANKING[nome]
    resolvidos = jogador["resolvidos"]
    exercicio_atual = proximo_exercicio(resolvidos)
    mensagem = flask_session.pop("mensagem", None)
    proximidade = flask_session.pop("proximidade", None)

    return render_template_string(
        PAGINA_JOGO,
        nome=nome,
        pontos=jogador["pontos"],
        exercicio_atual=exercicio_atual,
        posicao=len(resolvidos) + 1,
        total=len(EXERCICIOS),
        mensagem=mensagem,
        proximidade=proximidade,
    )


@app.route("/responder/<int:ex_id>", methods=["POST"])
def responder(ex_id):
    nome = flask_session.get("nome")
    if not nome:
        return redirect(url_for("login"))

    ex = next((e for e in EXERCICIOS if e["id"] == ex_id), None)
    comando = request.form.get("comando", "").strip()

    if ex["id"] in RANKING[nome]["resolvidos"]:
        flask_session["mensagem"] = "Voce ja resolveu este exercicio."
        flask_session["proximidade"] = None
    else:
        ok, msg = validar_exercicio(ex, comando, nome)
        if ok:
            RANKING[nome]["pontos"] += ex["pontos"]
            RANKING[nome]["resolvidos"].add(ex_id)
            flask_session["mensagem"] = f"✅ Correto! +{ex['pontos']} pontos. {msg}"
            flask_session["proximidade"] = None
        else:
            percentual, faltantes = analisar_proximidade(ex, comando)
            flask_session["mensagem"] = f"❌ {msg}"
            flask_session["proximidade"] = {"percentual": percentual, "faltantes": faltantes}

    return redirect(url_for("jogo"))


@app.route("/projetor")
def projetor():
    ranking_ordenado = sorted(RANKING.items(), key=lambda x: x[1]["pontos"], reverse=True)
    return render_template_string(PAGINA_PROJETOR, ranking_ordenado=ranking_ordenado, enumerate=enumerate)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
