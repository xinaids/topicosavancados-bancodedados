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