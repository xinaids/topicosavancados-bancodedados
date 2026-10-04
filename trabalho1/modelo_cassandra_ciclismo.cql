-- ============================================================
-- Trabalho Prático - IBI-TAB001 - Banco de Dados NoSQL (Colunas)
-- Tema: Estatísticas do Tour de France (edições, etapas e resultados)
-- SGBD: Apache Cassandra
-- Autores: Mateus Medeiros Schneider, Miguel Bohrz Vogel
-- Fonte: Kaggle "Tour de France" (stage_data, tdf_stages, tdf_winners)
--
-- Convenções:
--   * Etapa = (ano, ordem). 'ordem' é a posição da etapa dentro da edição (1..N).
--   * posicao = 9999 para quem não foi classificado (ver coluna 'status').
-- ============================================================

CREATE KEYSPACE IF NOT EXISTS ciclismo
WITH REPLICATION = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
};

USE ciclismo;

-- 1. Ciclistas -------------------------------------------------
-- Consulta: dados cadastrais de um ciclista.
-- pais e data_nascimento são opcionais (só existem para vencedores de etapas/edições).
CREATE TABLE IF NOT EXISTS ciclistas (
    ciclista_id     UUID PRIMARY KEY,
    nome            TEXT,
    pais            TEXT,
    data_nascimento DATE
);

-- 2. Edições ---------------------------------------------------
-- Consulta: dados de uma edição (vencedor, distância total).
-- com_resultados = TRUE quando há etapas e resultados carregados para o ano.
CREATE TABLE IF NOT EXISTS edicoes (
    ano               INT PRIMARY KEY,
    edicao            INT,
    data_inicio       DATE,
    distancia_km      DECIMAL,
    tempo_total_h     DECIMAL,        -- opcional
    vencedor          TEXT,
    equipe_vencedora  TEXT,
    vitorias_etapa    INT,
    etapas_lideradas  INT,
    com_resultados    BOOLEAN
);

-- 3. Etapas ----------------------------------------------------
-- Consulta: etapas de uma edição, em ordem.
-- Partition key: ano  |  Clustering key: ordem
CREATE TABLE IF NOT EXISTS etapas (
    ano           INT,
    ordem         INT,
    numero        TEXT,        -- 'P' (prólogo), '1', '2'...
    data_etapa    DATE,
    tipo          TEXT,        -- Plain stage, High mountain stage, Individual time trial...
    distancia_km  DECIMAL,
    origem        TEXT,
    destino       TEXT,
    vencedor      TEXT,
    PRIMARY KEY ((ano), ordem)
) WITH CLUSTERING ORDER BY (ordem ASC);

-- 4. Resultados por etapa --------------------------------------
-- Consulta: ranking de UMA etapa, ordenado por posição.
-- Partition key: (ano, ordem)  |  Clustering keys: posicao, ciclista_id (desempate)
-- Maior partição do conjunto de dados: 198 linhas.
CREATE TABLE IF NOT EXISTS resultados_por_etapa (
    ano          INT,
    ordem        INT,
    posicao      INT,          -- 9999 = não classificado (ver status)
    ciclista_id  UUID,
    nome         TEXT,         -- desnormalizado: evita lookup em ciclistas
    equipe       TEXT,         -- opcional
    idade        INT,          -- opcional
    status       TEXT,         -- FIN, DNF, DNS, OTL, DSQ, NQ
    pontos       INT,          -- opcional (vazio em ~88% das linhas)
    PRIMARY KEY ((ano, ordem), posicao, ciclista_id)
) WITH CLUSTERING ORDER BY (posicao ASC, ciclista_id ASC);

-- 5. Resultados por ciclista -----------------------------------
-- Consulta: histórico de UM ciclista, etapas mais recentes primeiro.
-- Mesma informação da tabela 4, outro padrão de acesso (sem JOIN).
-- Partition key: ciclista_id  |  Clustering keys: ano DESC, ordem DESC
-- Maior partição do conjunto de dados: 328 linhas.
CREATE TABLE IF NOT EXISTS resultados_por_ciclista (
    ciclista_id   UUID,
    ano           INT,
    ordem         INT,
    posicao       INT,
    status        TEXT,
    equipe        TEXT,
    idade         INT,
    pontos        INT,
    data_etapa    DATE,        -- desnormalizado da etapa
    tipo          TEXT,        -- desnormalizado da etapa
    distancia_km  DECIMAL,     -- desnormalizado da etapa
    PRIMARY KEY ((ciclista_id), ano, ordem)
) WITH CLUSTERING ORDER BY (ano DESC, ordem DESC);

-- ============================================================
-- Carga (cqlsh) — gerar os CSVs antes com: python3 preparar_dados.py --tdf dados --out out
-- ============================================================
-- COPY ciclistas (ciclista_id, nome, pais, data_nascimento)
--   FROM 'out/ciclistas.csv' WITH HEADER = TRUE AND NULL = '';
-- COPY edicoes (ano, edicao, data_inicio, distancia_km, tempo_total_h, vencedor, equipe_vencedora, vitorias_etapa, etapas_lideradas, com_resultados)
--   FROM 'out/edicoes.csv' WITH HEADER = TRUE AND NULL = '';
-- COPY etapas (ano, ordem, numero, data_etapa, tipo, distancia_km, origem, destino, vencedor)
--   FROM 'out/etapas.csv' WITH HEADER = TRUE AND NULL = '';
-- COPY resultados_por_etapa (ano, ordem, posicao, ciclista_id, nome, equipe, idade, status, pontos)
--   FROM 'out/resultados_por_etapa.csv' WITH HEADER = TRUE AND NULL = '';
-- COPY resultados_por_ciclista (ciclista_id, ano, ordem, posicao, status, equipe, idade, pontos, data_etapa, tipo, distancia_km)
--   FROM 'out/resultados_por_ciclista.csv' WITH HEADER = TRUE AND NULL = '';

-- ============================================================
-- Exemplos de consultas (a detalhar no Trabalho II)
-- ============================================================
-- Dados de uma edição:       SELECT * FROM edicoes WHERE ano = 2010;
-- Etapas de uma edição:      SELECT * FROM etapas WHERE ano = 2010;
-- Ranking de uma etapa:      SELECT posicao, nome, equipe FROM resultados_por_etapa WHERE ano = 2010 AND ordem = 4 LIMIT 10;
-- Histórico de um ciclista:  SELECT * FROM resultados_por_ciclista WHERE ciclista_id = ?;
