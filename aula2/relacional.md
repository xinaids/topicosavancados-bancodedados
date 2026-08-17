artista(<ins>id_artista</ins>, nome)

album(<ins>id_album</ins>, nome)

genero(<ins>id_genero</ins>, nome)

faixa(<ins>id_faixa</ins>, nome, duracao_ms, explicita, popularidade,
      danceability, energy, loudness, speechiness, acousticness,
      instrumentalness, liveness, valence, tempo, key, mode, time_signature,
      id_album#, id_genero#)

faixa_artista(<ins>id_faixa#, id_artista#</ins>) -- resolve N:N, PK composta
