-- =========================================================
-- ESQUEMA OBJETO-RELACIONAL — Spotify Tracks Dataset
-- =========================================================

-- 1. ENUM para a nota musical (key)
CREATE TYPE nota_musical AS ENUM (
    'C','C#','D','D#','E','F','F#','G','G#','A','A#','B','INDEFINIDA'
);

-- 2. DOMAIN para popularidade (0-100), reaproveitável em qualquer tabela futura
CREATE DOMAIN popularidade_spotify AS INTEGER
    CHECK (VALUE BETWEEN 0 AND 100);

-- 3. COMPOSITE TYPE agrupando os atributos de áudio
CREATE TYPE audio_features AS (
    danceability      NUMERIC(5,4),
    energy            NUMERIC(5,4),
    loudness          NUMERIC(6,3),
    speechiness       NUMERIC(5,4),
    acousticness      NUMERIC(5,4),
    instrumentalness  NUMERIC(6,5),
    liveness          NUMERIC(5,4),
    valence           NUMERIC(5,4),
    tempo             NUMERIC(6,2)
);

CREATE TABLE album (
    id_album   SERIAL PRIMARY KEY,
    nome       VARCHAR(300) NOT NULL
);

CREATE TABLE genero (
    id_genero  SERIAL PRIMARY KEY,
    nome       VARCHAR(100) NOT NULL UNIQUE
);

-- 4. ARRAY substitui a tabela associativa faixa_artista
CREATE TABLE faixa (
    id_faixa       VARCHAR(30) PRIMARY KEY,
    nome            VARCHAR(300) NOT NULL,
    duracao_ms      INTEGER NOT NULL CHECK (duracao_ms > 0),
    explicita        BOOLEAN NOT NULL DEFAULT FALSE,
    popularidade     popularidade_spotify NOT NULL,

    features         audio_features NOT NULL,

    nota_chave       nota_musical NOT NULL,
    modo             SMALLINT CHECK (modo IN (0,1)),
    compasso         SMALLINT,

    artistas         VARCHAR(200)[] NOT NULL,   -- array de nomes de artista

    id_album        INTEGER NOT NULL REFERENCES album(id_album),
    id_genero       INTEGER NOT NULL REFERENCES genero(id_genero)
);

-- 5. HERANÇA — especialização de faixa explícita
CREATE TABLE faixa_explicita (
    motivo_flag   VARCHAR(100)  -- ex.: 'linguagem', 'conteúdo sexual'
) INHERITS (faixa);


-- =========================================================
-- 6. Dados de teste (demo ao vivo)
-- =========================================================

INSERT INTO album (nome) VALUES ('Her Loss');
INSERT INTO genero (nome) VALUES ('hip-hop');

INSERT INTO faixa (
    id_faixa, nome, duracao_ms, explicita, popularidade,
    features, nota_chave, modo, compasso, artistas, id_album, id_genero
) VALUES (
    'trk001', 'Rich Flex', 218424, true, 88,
    ROW(0.7250, 0.5910, -6.629, 0.2170, 0.0785, 0.0000, 0.1210, 0.3600, 152.925),
    'C#', 1, 4,
    ARRAY['Drake', '21 Savage'],
    1, 1
);


-- =========================================================
-- 7. Queries — vantagens do objeto-relacional
-- =========================================================

-- COMPOSITE TYPE: acessar campo direto
SELECT nome, (features).danceability, (features).energy
FROM faixa WHERE id_faixa = 'trk001';

-- ARRAY: buscar faixa por artista sem JOIN
SELECT nome FROM faixa WHERE 'Drake' = ANY(artistas);


-- =========================================================
-- 8. Demo — DOMAIN rejeitando popularidade inválida
-- =========================================================

INSERT INTO faixa (
    id_faixa, nome, duracao_ms, popularidade,
    features, nota_chave, artistas, id_album, id_genero
) VALUES (
    'trk_erro', 'Teste', 200000, 150,
    ROW(0.5,0.5,-5,0.1,0.1,0.0,0.1,0.5,120),
    'C', ARRAY['X'], 1, 1
);
-- ERRO esperado: value for domain popularidade_spotify violates check constraint


-- =========================================================
-- 9. Demo — ENUM rejeitando valor fora da lista
-- =========================================================

INSERT INTO faixa (
    id_faixa, nome, duracao_ms, popularidade,
    features, nota_chave, artistas, id_album, id_genero
) VALUES (
    'trk_erro2', 'Teste', 200000, 50,
    ROW(0.5,0.5,-5,0.1,0.1,0.0,0.1,0.5,120),
    'H', ARRAY['X'], 1, 1
);
-- ERRO esperado: invalid input value for enum nota_musical: "H"


-- =========================================================
-- 10. Demo — HERANÇA (faixa_explicita)
-- =========================================================

INSERT INTO faixa_explicita (
    id_faixa, nome, duracao_ms, explicita, popularidade,
    features, nota_chave, artistas, id_album, id_genero, motivo_flag
) VALUES (
    'trk002', 'Testando Heranca', 200000, true, 60,
    ROW(0.5,0.5,-5,0.1,0.1,0.0,0.1,0.5,120),
    'A', ARRAY['Artista X'], 1, 1, 'linguagem'
);

-- Consulta em faixa TAMBÉM traz a faixa explícita (herança funciona)
SELECT * FROM faixa;
