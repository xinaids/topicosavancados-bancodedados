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


--- outros exemplos
-- COMPOSITE TYPE: acessar campo direto
SELECT nome, (features).danceability FROM faixa WHERE (features).energy > 0.8;

-- ARRAY: buscar faixa por artista sem JOIN
SELECT nome FROM faixa WHERE 'Drake' = ANY(artistas);

-- DOMAIN: rejeita automaticamente
INSERT INTO faixa (id_faixa, nome, duracao_ms, popularidade, ...)
VALUES ('abc123', 'Teste', 200000, 150, ...); -- ERRO: violates domain constraint