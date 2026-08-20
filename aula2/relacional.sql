-- =========================================================
-- ESQUEMA RELACIONAL — Spotify Tracks Dataset
-- =========================================================

-- 1. Criação das tabelas (sem FK primeiro)
CREATE TABLE artista (
    id_artista   SERIAL PRIMARY KEY,
    nome         VARCHAR(200) NOT NULL
);

CREATE TABLE album (
    id_album     SERIAL PRIMARY KEY,
    nome         VARCHAR(300) NOT NULL
);

CREATE TABLE genero (
    id_genero    SERIAL PRIMARY KEY,
    nome         VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE faixa (
    id_faixa           VARCHAR(30) PRIMARY KEY,  -- track_id do Spotify
    nome                VARCHAR(300) NOT NULL,
    duracao_ms          INTEGER NOT NULL CHECK (duracao_ms > 0),
    explicita            BOOLEAN NOT NULL DEFAULT FALSE,
    popularidade         INTEGER NOT NULL CHECK (popularidade BETWEEN 0 AND 100),

    danceability         NUMERIC(5,4),
    energy               NUMERIC(5,4),
    loudness             NUMERIC(6,3),
    speechiness          NUMERIC(5,4),
    acousticness         NUMERIC(5,4),
    instrumentalness     NUMERIC(6,5),
    liveness             NUMERIC(5,4),
    valence              NUMERIC(5,4),
    tempo                NUMERIC(6,2),

    nota_chave           SMALLINT CHECK (nota_chave BETWEEN -1 AND 11),
    modo                 SMALLINT CHECK (modo IN (0,1)),
    compasso             SMALLINT,

    id_album            INTEGER NOT NULL REFERENCES album(id_album),
    id_genero           INTEGER NOT NULL REFERENCES genero(id_genero)
);

-- resolve o N:N faixa-artista
CREATE TABLE faixa_artista (
    id_faixa     VARCHAR(30) REFERENCES faixa(id_faixa),
    id_artista   INTEGER REFERENCES artista(id_artista),
    PRIMARY KEY (id_faixa, id_artista)
);


-- =========================================================
-- 2. Dados de teste (demo ao vivo)
-- =========================================================

INSERT INTO artista (nome) VALUES ('Drake'), ('21 Savage');

INSERT INTO album (nome) VALUES ('Her Loss');

INSERT INTO genero (nome) VALUES ('hip-hop');

INSERT INTO faixa (
    id_faixa, nome, duracao_ms, explicita, popularidade,
    danceability, energy, loudness, speechiness, acousticness,
    instrumentalness, liveness, valence, tempo,
    nota_chave, modo, compasso, id_album, id_genero
) VALUES (
    'trk001', 'Rich Flex', 218424, true, 88,
    0.7250, 0.5910, -6.629, 0.2170, 0.0785,
    0.0000, 0.1210, 0.3600, 152.925,
    1, 1, 4, 1, 1
);

INSERT INTO faixa_artista (id_faixa, id_artista) VALUES
    ('trk001', 1),
    ('trk001', 2);


-- =========================================================
-- 3. Query — busca de artistas de uma faixa exige JOIN
-- =========================================================

SELECT f.nome, a.nome AS artista
FROM faixa f
JOIN faixa_artista fa ON fa.id_faixa = f.id_faixa
JOIN artista a ON a.id_artista = fa.id_artista
WHERE f.id_faixa = 'trk001';


-- =========================================================
-- 4. Demo — CHECK rejeitando popularidade inválida
-- =========================================================

INSERT INTO faixa (
    id_faixa, nome, duracao_ms, popularidade, id_album, id_genero
) VALUES (
    'trk_erro', 'Teste', 200000, 150, 1, 1
);
-- ERRO esperado: new row for relation "faixa" violates check constraint "faixa_popularidade_check"
