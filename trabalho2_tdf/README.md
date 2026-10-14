# Le Tour · Estatísticas (Trabalho II, NoSQL)

Sistema web sobre **Apache Cassandra** com os dados do Tour de France (Kaggle: `stage_data`, `tdf_stages`, `tdf_winners`).
Autores: Mateus Medeiros Schneider e Miguel Bohrz Vogel · IBI-TAB001 · IFRS Campus Ibirubá.

- **Back-end:** Python + FastAPI + `cassandra-driver`
- **Front-end:** HTML, CSS e JS puros (sem dependências), tema Tour de France
- **Banco:** Cassandra 5.0, keyspace `ciclismo`, 5 tabelas (`schema.cql`)

## Como rodar

### Opção A: Docker, 1 nó (mais simples)
```bash
docker compose up --build
```
Abra **http://localhost:8000**. Na primeira vez o Cassandra demora uns 2 minutos para subir e a carga dos
171 mil resultados leva mais alguns. Nas próximas, a carga é pulada (`--se-vazio`).

### Opção B: Docker, cluster de 3 nós (para a apresentação de replicação)
```bash
docker compose -f docker-compose.cluster.yml up --build
```
Precisa de uns 6 GB de RAM livres. Com RF=3 dá para mostrar a tolerância a falhas: na tela **Bastidores → Consistência**,
execute `ALL`, `QUORUM` e `ONE`, depois rode `docker stop tdf-cassandra3` e execute de novo.

### Opção C: Cassandra já instalado
```bash
pip install -r requirements.txt
python carregar.py --host 127.0.0.1 --rf 1      # cria o esquema e carrega os CSVs
TDF_HOSTS=127.0.0.1 uvicorn app.main:app --reload
```

### Sem Cassandra (só para ver a interface)
```bash
pip install -r requirements-demo.txt
TDF_MODE=demo uvicorn app.main:app
```
Lê os CSVs em memória. O cabeçalho mostra **"Modo demonstração"**, e nós, tokens e consistência aparecem
marcados como **SIMULADO**. Não use esse modo na apresentação.

Variáveis: `TDF_MODE` (`auto` | `cassandra` | `demo`), `TDF_HOSTS`, `TDF_PORT`, `TDF_KEYSPACE`.
O padrão `auto` tenta o Cassandra e, se não conseguir, cai para o modo demonstração com aviso no cabeçalho.
Use `TDF_MODE=cassandra` para falhar de verdade se o banco não estiver no ar.

## O que cada tela mostra

| Tela | O que demonstra | Requisito do enunciado |
|---|---|---|
| **Edições** | cartões por década, vencedor, distância e tempo (`edicoes`) | consulta simples |
| **Edição → Etapas** | perfil das etapas (`etapas`) e ranking com pódio (`resultados_por_etapa`) | consultas simples e por chave |
| **Edição → Números** | pelotão, idade média, não classificados e vitórias por equipe | agregações (`COUNT`, `AVG`, fan-out por partição) |
| **Ciclistas** | busca e histórico completo (`resultados_por_ciclista`), estatísticas e gráfico ano a ano | consulta por partição, agregação |
| **Demonstração** | INSERT, UPDATE e DELETE com dados reais, mostrando o efeito nas duas tabelas | demonstração do sistema |
| **Bastidores** | nós e replicação, chaves de partição e clustering, anel de tokens, níveis de consistência, console CQL | consultas avançadas (particionamento, replicação, CQL) |
| **Botão `</> CQL`** | todo CQL executado por trás de cada tela, com tempo | transparência do modelo |

As 10 consultas do enunciado (3 simples, 3 com múltiplos critérios, 2 de agregação, 2 avançadas) estão prontas em
`consultas_trabalho2.cql`.

## Decisões de modelagem que aparecem no sistema

- **Uma tabela por consulta** (modelagem orientada a consulta): o ranking de uma etapa e o histórico de um ciclista são
  a mesma informação gravada duas vezes. O INSERT de resultado usa um `LOGGED BATCH` para manter as duas cópias juntas.
- **`posicao = 9999`** para quem não terminou: coluna de clustering não aceita `null`. A vantagem é poder ler só essa fatia
  (`AND posicao = 9999`).
- **UPDATE de chave de clustering vira DELETE + INSERT** (desclassificação em `resultados_por_etapa`).
- **Nome desnormalizado** em `resultados_por_etapa`: evita JOIN, mas por isso o nome não é editável na tela de cadastro.
- **Cancelar etapa**: um `DELETE` de partição em `resultados_por_etapa`, mas um `DELETE` por linha em
  `resultados_por_ciclista`, porque cada resultado fica em uma partição diferente.
- **Busca por nome** é feita em memória (o Cassandra não tem `LIKE`): os nomes são lidos uma vez na inicialização.
- **Ids de ciclista** são UUID v5 do nome normalizado; assim, o `IF NOT EXISTS` evita cadastrar o mesmo nome duas vezes.
- Os exemplos da Demonstração usam o ano fictício **2099** para não alterar os dados reais.

## Arquivos

```
app/main.py            API (FastAPI)
app/db_cassandra.py    todas as consultas em CQL (driver oficial)
app/db_demo.py         modo sem Cassandra (CSV em memória)
app/static/            interface (index.html, style.css, app.js, extra.js)
schema.cql             keyspace e tabelas
carregar.py            cria o esquema e carrega dados/*.csv
dados/                 5 CSVs prontos (gerados por preparar_dados.py a partir do Kaggle)
consultas_trabalho2.cql  as 10 consultas do enunciado + recursos do CQL
preparar_dados.py      como os CSVs foram gerados (precisa dos CSVs originais do Kaggle)
docker-compose*.yml    1 nó e 3 nós
```

## Limitações conhecidas

- Só 72 das 106 edições têm etapas e resultados: nas demais, os arquivos do Kaggle não puderam ser ligados com segurança.
  Elas aparecem na tela com a marcação **"só vencedor"**.
- Os nomes vêm do dataset como "Sobrenome Nome".
- A camada de acesso ao Cassandra foi testada com um driver simulado e a interface com os CSVs em memória. A execução
  contra um Cassandra real depende de você subir o Docker; se algum CQL falhar, a mensagem de erro aparece na própria tela.
