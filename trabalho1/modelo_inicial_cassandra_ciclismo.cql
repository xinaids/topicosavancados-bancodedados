-- ============================================================
-- Trabalho Prático - IBI-TAB001 - Banco de Dados NoSQL (Colunas)
-- Tema: Estatísticas e Telemetria de Provas de Ciclismo
-- SGBD: Apache Cassandra
-- Autor: Mateus Medeiros Schneider
-- ============================================================

CREATE KEYSPACE IF NOT EXISTS ciclismo
WITH REPLICATION = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
};

USE ciclismo;

-- ------------------------------------------------------------
-- 1. Ciclistas
-- Consulta: buscar dados cadastrais de um ciclista pelo id
-- ------------------------------------------------------------
CREATE TABLE ciclistas (
    ciclista_id     UUID PRIMARY KEY,
    nome            TEXT,
    equipe          TEXT,
    categoria       TEXT,      -- ex: Elite, Sub-23, Master A, Master B
    pais            TEXT,
    data_nascimento DATE
);

-- ------------------------------------------------------------
-- 2. Provas
-- Consulta: buscar dados de uma prova pelo id
-- ------------------------------------------------------------
CREATE TABLE provas (
    prova_id        UUID PRIMARY KEY,
    nome            TEXT,
    data_prova      DATE,
    tipo            TEXT,      -- estrada | mtb | contrarrelogio
    distancia_km    DECIMAL,
    local           TEXT
);

-- ------------------------------------------------------------
-- 3. Resultados por prova
-- Consulta: ranking/resultados de UMA prova, ordenado por posição
-- Partition key: prova_id  |  Clustering keys: posicao_final, ciclista_id (desempate)
-- ------------------------------------------------------------
CREATE TABLE resultados_por_prova (
    prova_id        UUID,
    posicao_final   INT,
    ciclista_id     UUID,
    nome_ciclista   TEXT,       -- desnormalizado: evita lookup extra em ciclistas
    categoria       TEXT,
    tempo_total     TIME,
    PRIMARY KEY (prova_id, posicao_final, ciclista_id)
) WITH CLUSTERING ORDER BY (posicao_final ASC, ciclista_id ASC);

-- ------------------------------------------------------------
-- 4. Resultados por ciclista (mesma informação, outro padrão de acesso)
-- Consulta: histórico de resultados de UM ciclista, mais recentes primeiro
-- Partition key: ciclista_id  |  Clustering keys: data_prova, prova_id
-- Justificativa: em Cassandra, tabelas são desenhadas por consulta;
-- duplicar dados evita JOIN, que o modelo não suporta nativamente.
-- ------------------------------------------------------------
CREATE TABLE resultados_por_ciclista (
    ciclista_id     UUID,
    data_prova      DATE,
    prova_id        UUID,
    nome_prova      TEXT,
    posicao_final   INT,
    tempo_total     TIME,
    PRIMARY KEY (ciclista_id, data_prova, prova_id)
) WITH CLUSTERING ORDER BY (data_prova DESC, prova_id ASC);

-- ------------------------------------------------------------
-- 5. Telemetria por ciclista/prova (tabela de maior volume)
-- Consulta: série temporal de um ciclista numa prova específica,
-- opcionalmente filtrada por intervalo de tempo (timestamp >= / <=)
-- Partition key: (ciclista_id, prova_id)  |  Clustering key: timestamp
-- Justificativa: uma prova de ~3h gera até 10.800 leituras por atleta
-- (1 leitura/segundo). Particionar por ciclista+prova mantém cada
-- partição em um tamanho gerenciável e a busca por intervalo de tempo
-- é eficiente graças à ordenação pelo clustering key.
-- ------------------------------------------------------------
CREATE TABLE telemetria_por_ciclista_prova (
    ciclista_id     UUID,
    prova_id        UUID,
    ts              TIMESTAMP,
    potencia_w      INT,
    cadencia_rpm    INT,
    fc_bpm          INT,
    velocidade_kmh  DECIMAL,
    altitude_m       DECIMAL,
    latitude        DECIMAL,
    longitude       DECIMAL,
    PRIMARY KEY ((ciclista_id, prova_id), ts)
) WITH CLUSTERING ORDER BY (ts ASC);

-- ============================================================
-- Exemplos de operações principais (a detalhar no Trabalho II)
-- ============================================================

-- Inserção de leitura de telemetria (alta frequência, 1x/segundo)
-- INSERT INTO telemetria_por_ciclista_prova
--   (ciclista_id, prova_id, ts, potencia_w, cadencia_rpm, fc_bpm, velocidade_kmh, altitude_m, latitude, longitude)
-- VALUES (?, ?, toTimestamp(now()), ?, ?, ?, ?, ?, ?, ?);

-- Consulta simples: dados cadastrais de um ciclista
-- SELECT * FROM ciclistas WHERE ciclista_id = ?;

-- Consulta com múltiplos critérios: telemetria de um ciclista numa prova,
-- dentro de uma janela de tempo (ex: últimos 10km de uma etapa)
-- SELECT * FROM telemetria_por_ciclista_prova
-- WHERE ciclista_id = ? AND prova_id = ? AND ts >= ? AND ts <= ?;

-- Ranking de uma prova por categoria (filtragem aplicada na aplicação
-- ou com ALLOW FILTERING / índice secundário em categoria, a avaliar)
-- SELECT * FROM resultados_por_prova WHERE prova_id = ?;
