artista(<u>id_artista</u>, nome)

album(<u>id_album</u>, nome)

genero(<u>id_genero</u>, nome)

faixa(<u>id_faixa</u>, nome, duracao_ms, explicita, popularidade,
      danceability, energy, loudness, speechiness, acousticness,
      instrumentalness, liveness, valence, tempo, key, mode, time_signature,
      id_album#, id_genero#)

faixa_artista(<u>id_faixa#, id_artista#</u>)   -- resolve N:N, PK composta