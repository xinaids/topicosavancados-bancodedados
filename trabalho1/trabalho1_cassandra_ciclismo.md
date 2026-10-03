# Trabalho Prático NoSQL — Trabalho I

**Disciplina:** IBI-TAB001 — IFRS Campus Ibirubá
**Aluno:** Mateus Medeiros Schneider
**Tecnologia:** Apache Cassandra (Colunas — sorteada na oficina)
**Tema:** Estatísticas e telemetria de provas de ciclismo

---

## 1. Problema

Equipes e treinadores de ciclismo precisam registrar o resultado formal das provas (posição, tempo) e também a telemetria de alta frequência capturada por sensores durante a competição (potência, cadência, frequência cardíaca, velocidade, altitude, GPS — uma leitura por segundo).

Em um banco relacional, esse volume concentrado em uma única tabela, com FKs e índices, degrada a escrita concorrente (vários atletas gerando dados ao mesmo tempo) e a leitura de séries temporais.

## 2. Descrição do sistema

Plataforma de registro e consulta de provas de ciclismo. Permite:

- cadastrar ciclistas e provas;
- registrar o resultado final de cada ciclista em cada prova;
- ingerir leituras contínuas de telemetria durante a prova;
- consultar a série temporal de um atleta, o ranking de uma prova e agregações de desempenho (potência média/máxima, FC média).

## 3. Público-alvo

Equipes ciclísticas, treinadores e plataformas de análise de performance esportiva (modelo Strava / TrainingPeaks).

## 4. Tecnologia NoSQL escolhida

**Apache Cassandra** (banco orientado a colunas), a tecnologia sorteada para o grupo na oficina.

## 5. Justificativa da escolha

O domínio atende a duas características exigidas pelo enunciado:

- **Grande volume:** uma prova de ~3h gera até 10.800 leituras por atleta (1 leitura/s).
- **Escalabilidade:** várias provas e atletas escrevendo ao mesmo tempo, com escrita distribuída.

O acesso predominante é "telemetria de um ciclista, numa prova, num intervalo de tempo". O Cassandra atende isso bem: partition key composta `(ciclista_id, prova_id)` e clustering key temporal, sem JOINs.

## 6. Dados que serão armazenados

| Dado | Conteúdo |
|---|---|
| Ciclista | id, nome, equipe, categoria, país, data de nascimento |
| Prova | id, nome, data, tipo (estrada/mtb/contrarrelógio), distância, local |
| Resultado | posição final e tempo total de um ciclista em uma prova |
| Telemetria | timestamp, potência (W), cadência (rpm), FC (bpm), velocidade (km/h), altitude (m), latitude, longitude |

**Fonte dos dados:** dataset real do Kaggle *TCX file Cycling Dataset* (`triskadecaepyon/tcx-file-cycling-dataset`).
Requisito mínimo: equivalente a 5 tabelas × 100 linhas com dados reais.

## 7. Principais operações

- **Inserção:** leitura de telemetria (alta frequência); cadastro de ciclista e prova; registro de resultado.
- **Atualização:** dados cadastrais; correção de resultado (ex.: penalidade).
- **Remoção:** prova cancelada e suas leituras (remoção por partição ou TTL).
- **Consulta:** série temporal por ciclista/prova/intervalo; ranking de uma prova; histórico de um ciclista.
- **Agregação:** potência média/máxima e FC média por ciclista/prova.

## 8. Modelo inicial

### 8.1 MER conceitual

**CICLISTA** (entidade forte)
- `ciclista_id` (PK), `nome`, `equipe` (opcional), `categoria`, `pais`, `data_nascimento`

**PROVA** (entidade forte)
- `prova_id` (PK), `nome`, `data_prova`, `tipo`, `distancia_km`, `local`

**PARTICIPA** (relacionamento N:N entre CICLISTA e PROVA)
- Cardinalidade: CICLISTA (0,N) — PROVA (1,N)
- Atributos próprios: `posicao_final`, `tempo_total`
- Por ter atributos próprios, vira a entidade associativa **RESULTADO** (chave composta `ciclista_id` + `prova_id`)

**TELEMETRIA** (entidade fraca)
- Depende de RESULTADO pelo relacionamento identificador **REGISTRA** (1:N, participação total do lado fraco)
- Chave = `timestamp` (chave parcial) + `ciclista_id` + `prova_id`
- Atributos: `potencia_w`, `cadencia_rpm`, `fc_bpm`, `velocidade_kmh`, `altitude_m`, `latitude`, `longitude`

```
CICLISTA (0,N) ──< PARTICIPA >── (1,N) PROVA
                       │
                  RESULTADO (posicao_final, tempo_total)
                       │ (1,N) REGISTRA [identificador]
                       ▼
                  TELEMETRIA (fraca)
```

> Para o brModelo: desenhar RESULTADO como entidade associativa e TELEMETRIA com borda dupla.

### 8.2 Esquema relacional equivalente (referência para a comparação do Trabalho II)

```
ciclista(ciclista_id, nome, equipe, categoria, pais, data_nascimento)
prova(prova_id, nome, data_prova, tipo, distancia_km, local)
resultado(ciclista_id#, prova_id#, posicao_final, tempo_total)
telemetria(ciclista_id#, prova_id#, ts, potencia_w, cadencia_rpm, fc_bpm,
           velocidade_kmh, altitude_m, latitude, longitude)
```

### 8.3 Prévia do mapeamento para Cassandra (detalhar no Trabalho II)

No Cassandra a modelagem parte das consultas, não das entidades. Tabelas previstas:

| Tabela | Partition key | Clustering key | Consulta atendida |
|---|---|---|---|
| `ciclistas` | `ciclista_id` | — | dados cadastrais |
| `provas` | `prova_id` | — | dados da prova |
| `resultados_por_prova` | `prova_id` | `posicao_final`, `ciclista_id` | ranking de uma prova |
| `resultados_por_ciclista` | `ciclista_id` | `data_prova DESC`, `prova_id` | histórico de um ciclista |
| `telemetria_por_ciclista_prova` | `(ciclista_id, prova_id)` | `ts` | série temporal |

Decisões a justificar: duplicação de resultados em duas tabelas (uma por padrão de consulta) e `nome_ciclista` desnormalizado em `resultados_por_prova`.

Script CQL completo: `modelo_inicial_cassandra_ciclismo.cql`.

### 8.4 Chaves primárias

**No MER / modelo relacional**

| Entidade | Chave primária | Observação |
|---|---|---|
| CICLISTA | `ciclista_id` | chave substituta (UUID); `nome` não identifica sozinho (homônimos) |
| PROVA | `prova_id` | chave substituta (UUID); (`nome`, `data_prova`) seria chave candidata |
| RESULTADO | (`ciclista_id`, `prova_id`) | chave composta; cada uma é FK (`#`) |
| TELEMETRIA (fraca) | (`ciclista_id`, `prova_id`, `ts`) | chave parcial `ts` + PK de RESULTADO (relacionamento identificador) |

**No Cassandra** (a PK = partition key + clustering keys)

| Tabela | PRIMARY KEY | Por quê |
|---|---|---|
| `ciclistas` | `ciclista_id` | busca direta por id |
| `provas` | `prova_id` | busca direta por id |
| `resultados_por_prova` | `(prova_id, posicao_final, ciclista_id)` | `ciclista_id` desempata empates de posição, que senão sobrescreveriam a linha |
| `resultados_por_ciclista` | `(ciclista_id, data_prova, prova_id)` | `prova_id` evita colisão se houver duas provas no mesmo dia |
| `telemetria_por_ciclista_prova` | `((ciclista_id, prova_id), ts)` | partição por atleta+prova; `ts` ordena a série temporal |

**Origem dos ids no dataset:** os arquivos TCX não trazem `ciclista_id` nem `prova_id`. Os ids serão gerados na carga (UUID), e cada arquivo/atividade TCX será tratado como uma participação em uma prova. O `ts` vem do campo `Time` de cada trackpoint.

---

## Pendências

- [ ] Baixar o dataset do Kaggle e conferir colunas e volume
- [ ] Definir como gerar ciclistas/provas a partir do dataset (um arquivo TCX = uma atividade?)
- [ ] Desenhar o MER no brModelo
- [ ] Confirmar com o professor o formato de entrega (slides PDF ou documento)
- [ ] Subir Cassandra no Docker/WSL2 e testar o `.cql`

## Para o Trabalho II

- Problema e justificativa
- Modelagem (MER → Cassandra, com justificativas)
- Demonstração do sistema (INSERT/UPDATE/DELETE + dados reais)
- Consultas: 3 simples, 3 com múltiplos critérios, 2 de agregação, 2 avançadas (particionamento, replicação, CQL)
- Comparação NoSQL × relacional (10 critérios do enunciado)
- Conclusão
