-- ============================================================================
-- Trabalho II (IBI-TAB001) - Consultas e recursos NoSQL - Apache Cassandra
-- Keyspace: ciclismo   |   Execute no cqlsh:  docker exec -it tdf-cassandra1 cqlsh
-- (ou cole no "Console CQL" da tela Bastidores; ele aceita só SELECT)
-- id usado nos exemplos: Chris Froome = b4ae88d7-30d6-5319-a1af-154d59f91201
-- ============================================================================
USE ciclismo;

-- ----------------------------------------------------------------------------
-- 3 CONSULTAS SIMPLES (uma partição, pela chave)
-- ----------------------------------------------------------------------------
-- 1. Dados de uma edição
SELECT * FROM edicoes WHERE ano = 2010;

-- 2. Etapas de uma edição, já em ordem (clustering key: ordem)
SELECT numero, data_etapa, tipo, distancia_km, origem, destino, vencedor
FROM etapas WHERE ano = 2010;

-- 3. Ranking de uma etapa, já ordenado por posição (clustering key: posicao)
SELECT posicao, nome, equipe, idade FROM resultados_por_etapa
WHERE ano = 2010 AND ordem = 4 LIMIT 10;

-- ----------------------------------------------------------------------------
-- 3 CONSULTAS COM MÚLTIPLOS CRITÉRIOS
-- ----------------------------------------------------------------------------
-- 4. Pódio de uma etapa: faixa (range) na clustering key
SELECT posicao, nome, equipe FROM resultados_por_etapa
WHERE ano = 2010 AND ordem = 4 AND posicao <= 3;

-- 5. Histórico de um ciclista em uma faixa de anos (clustering key: ano)
SELECT ano, ordem, posicao, status, tipo, distancia_km FROM resultados_por_ciclista
WHERE ciclista_id = b4ae88d7-30d6-5319-a1af-154d59f91201 AND ano >= 2013 AND ano <= 2016;

-- 6. Quem não terminou uma etapa: posicao = 9999 lê só uma fatia da partição
--    (é o motivo de usar 9999 em vez de null: clustering key não aceita null)
SELECT nome, status FROM resultados_por_etapa
WHERE ano = 2010 AND ordem = 4 AND posicao = 9999;

-- Extra (filtro fora da chave, dentro de uma única partição): etapas longas de 2010
SELECT numero, tipo, distancia_km, origem, destino FROM etapas
WHERE ano = 2010 AND distancia_km > 200 ALLOW FILTERING;

-- ----------------------------------------------------------------------------
-- 2 CONSULTAS DE AGREGAÇÃO (funções nativas, dentro de uma partição)
-- ----------------------------------------------------------------------------
-- 7. Pelotão de uma etapa: tamanho, menor, maior e idade média
SELECT COUNT(*) AS participantes, MIN(idade) AS mais_novo, MAX(idade) AS mais_velho,
       AVG(CAST(idade AS double)) AS idade_media
FROM resultados_por_etapa WHERE ano = 2010 AND ordem = 4;

-- 8. Carreira de um ciclista: etapas disputadas, melhor posição e pontos
SELECT COUNT(*) AS etapas, MIN(posicao) AS melhor_posicao, SUM(pontos) AS pontos
FROM resultados_por_ciclista WHERE ciclista_id = b4ae88d7-30d6-5319-a1af-154d59f91201;

-- ----------------------------------------------------------------------------
-- 2 CONSULTAS AVANÇADAS (particionamento, replicação, recursos do CQL)
-- ----------------------------------------------------------------------------
-- 9. PARTICIONAMENTO: token (Murmur3) de cada partição. Mostra onde ela cai no anel.
SELECT token(ano, ordem), ano, ordem FROM resultados_por_etapa
WHERE ano = 2010 AND ordem IN (1, 2, 3, 4) PER PARTITION LIMIT 1;
--    Em etapas a chave é só o ano: todas as etapas de 2010 têm o mesmo token.
SELECT token(ano), ano, ordem FROM etapas WHERE ano = 2010 LIMIT 4;
--    No terminal (fora do cqlsh), quais nós guardam a partição (ano=2010, ordem=4):
--      docker exec tdf-cassandra1 nodetool getendpoints ciclismo resultados_por_etapa 2010:4
--      docker exec tdf-cassandra1 nodetool status ciclismo

-- 10. REPLICAÇÃO E CONSISTÊNCIA: o mesmo SELECT com níveis diferentes
DESCRIBE KEYSPACE ciclismo;                      -- mostra a estratégia e o fator de replicação
CONSISTENCY ONE;
SELECT posicao, nome FROM resultados_por_etapa WHERE ano = 2010 AND ordem = 4 LIMIT 3;
CONSISTENCY QUORUM;                              -- RF=3: precisa de 2 réplicas
SELECT posicao, nome FROM resultados_por_etapa WHERE ano = 2010 AND ordem = 4 LIMIT 3;
CONSISTENCY ALL;                                 -- precisa das 3 réplicas
SELECT posicao, nome FROM resultados_por_etapa WHERE ano = 2010 AND ordem = 4 LIMIT 3;
--    Derrube um nó (docker stop tdf-cassandra3) e repita: ONE e QUORUM respondem; ALL falha
--    com "Not enough replicas available".

-- ----------------------------------------------------------------------------
-- OUTROS RECURSOS DO CQL (para citar na apresentação)
-- ----------------------------------------------------------------------------
-- Transação leve (LWT): insere só se não existir
INSERT INTO ciclistas (ciclista_id, nome, pais)
VALUES (00000000-0000-0000-0000-000000000001, 'Ciclista de Teste', 'BRA') IF NOT EXISTS;   -- rode 2x: [applied] = False
-- Quando o dado foi gravado (microssegundos)
SELECT nome, WRITETIME(nome) FROM ciclistas WHERE ciclista_id = b4ae88d7-30d6-5319-a1af-154d59f91201;
-- O que NÃO funciona bem: filtro sem a chave. Resulta em erro sem ALLOW FILTERING e, com ele,
-- em varredura de todo o cluster (não use em produção).
SELECT * FROM etapas WHERE tipo = 'High mountain stage';
SELECT nome FROM ciclistas WHERE pais = 'BRA' ALLOW FILTERING;
