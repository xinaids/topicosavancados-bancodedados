# Trabalho Prático NoSQL — Trabalho I

**Disciplina:** IBI-TAB001 — IFRS Campus Ibirubá
**Alunos:** Mateus Medeiros Schneider, Miguel Bohrz Vogel
**Tecnologia:** Apache Cassandra (Colunas — sorteada na oficina)
**Tema:** Estatísticas do Tour de France (edições, etapas e resultados)

---

## 1. Problema

Analistas, equipes e fãs de ciclismo precisam consultar mais de um século de resultados do Tour de France: o ranking de cada etapa, o histórico de cada ciclista ao longo das edições e os dados de cada edição. São centenas de milhares de linhas de resultado, com muitos campos que só existem para parte das linhas (país, data de nascimento, equipe, pontos).

Em um banco relacional, essas consultas exigem JOINs entre ciclistas, edições, etapas e resultados, e o modelo rígido obriga a tratar como NULL os campos ausentes.

## 2. Descrição do sistema

Plataforma de consulta de estatísticas do Tour de France. Permite:

- cadastrar edições, etapas (data, tipo, distância, origem e destino) e ciclistas;
- registrar o resultado de cada ciclista em cada etapa (posição, equipe, idade, status);
- consultar o ranking de uma etapa, as etapas de uma edição e o histórico de um ciclista;
- calcular agregações (etapas disputadas por ciclista, vitórias por equipe, idade média por etapa).

## 3. Público-alvo

Equipes ciclísticas, treinadores, jornalistas esportivos e plataformas de estatísticas de ciclismo.

## 4. Tecnologia NoSQL escolhida

**Apache Cassandra** (banco orientado a colunas — tecnologia sorteada para o grupo na oficina).

## 5. Justificativa da escolha

- **Volume:** 255.752 resultados por etapa no dataset (1903–2019); 171.221 carregados após a validação (ver seção 6).
- **Acesso previsível por chave:** "ranking de uma etapa", "histórico de um ciclista" e "etapas de uma edição" mapeiam direto para partition key + clustering key, sem JOINs. Os dados são históricos e lidos com muito mais frequência do que escritos.
- **Dados esparsos:** `pontos` vazio em 88% das linhas, `equipe` em 13%, `pais` em 87% dos ciclistas. No Cassandra, coluna sem valor não ocupa espaço.
- **Escalabilidade:** o particionamento por etapa e por ciclista distribui os dados entre nós conforme o volume cresce (novas edições a cada ano).

> Observação para a comparação do Trabalho II: o domínio é bem estruturado e cabe num relacional sem dificuldade. O ganho do Cassandra está no acesso por chave e na escala, não na flexibilidade.

## 6. Dados que serão armazenados

| Dado | Conteúdo | Arquivo de origem |
|---|---|---|
| Ciclista | id, nome, país (opcional), data de nascimento (opcional) | `stage_data`, `tdf_stages`, `tdf_winners` |
| Edição | ano, número, data de início, distância, tempo total, vencedor, equipe vencedora, vitórias de etapa, etapas lideradas | `tdf_winners` |
| Etapa | edição (ano), número, data, tipo, distância, origem, destino, vencedor | `tdf_stages` |
| Resultado | posição, status (FIN/DNF/DNS/OTL/DSQ/NQ), equipe, idade, pontos | `stage_data` |

**Fonte (Kaggle):** *Tour de France* — `stage_data.csv`, `tdf_stages.csv` e `tdf_winners.csv`.

**Como as etapas são ligadas aos resultados:** os arquivos não compartilham um id de etapa. A ligação é feita pela ordem da etapa dentro da edição. Só entram as edições em que o número de etapas bate nos dois arquivos e pelo menos 85% dos vencedores de etapa (exceto contrarrelógio por equipes) coincidem com o 1º colocado do resultado. Isso deixa **72 das 104 edições comparáveis**; a tabela de edições entra completa, com a coluna `com_resultados` indicando quais têm etapas e resultados.

| Tabela Cassandra | Linhas |
|---|---|
| `ciclistas` | 4.302 |
| `edicoes` | 106 |
| `etapas` | 1.431 |
| `resultados_por_etapa` | 171.221 |
| `resultados_por_ciclista` | 171.221 |

Todas as 5 tabelas passam de 100 linhas.

**Limitações a declarar na apresentação:**
- Sem tempo por ciclista: as colunas `time`/`elapsed` do dataset têm formato ambíguo, então não entram no modelo.
- `pais` existe para 557 dos 4.302 ciclistas (os que venceram etapas) e `data_nascimento` para 60 (campeões de edição).
- O `ciclista_id` é gerado a partir do nome normalizado (UUID v5); homônimos seriam fundidos.
- Em algumas etapas o vencedor do resultado difere do oficial (desclassificações posteriores por doping e grafias diferentes).
- 34 edições ficam só com os dados da edição, sem etapas nem resultados.

## 7. Principais operações

- **Inserção:** cadastro de edição, etapa e ciclista; registro de resultado.
- **Atualização:** correção de resultado (ex.: desclassificação posterior → status `DSQ`); dados cadastrais.
- **Remoção:** etapa cancelada e seus resultados (remoção por partição).
- **Consulta:** dados de uma edição; etapas de uma edição; ranking de uma etapa; histórico de um ciclista.
- **Agregação:** etapas disputadas por ciclista, idade média por etapa, vitórias por equipe (na aplicação, já que o Cassandra tem agregação limitada).

## 8. Modelo inicial

### 8.1 MER conceitual (notação de Chen / brModelo)

**CICLISTA** (entidade)
- `ciclista_id` (PK), `nome`, `pais` (opcional), `data_nascimento` (opcional)

**EDICAO** (entidade)
- `ano` (PK), `edicao`, `data_inicio`, `distancia_km`, `tempo_total_h` (opcional), `vencedor`, `equipe_vencedora`, `vitorias_etapa`, `etapas_lideradas`

**ETAPA** (entidade)
- `etapa_id` (PK), `numero`, `data_etapa`, `tipo`, `distancia_km`, `origem`, `destino`, `vencedor`

**RESULTADO** (entidade)
- `resultado_id` (PK), `posicao_final` (opcional — vazio para DNF/DNS), `status`, `equipe` (opcional), `idade` (opcional), `pontos` (opcional)

**Relacionamentos e cardinalidades (mín,máx)**

| Relacionamento | Entidades | Cardinalidades | Tipo |
|---|---|---|---|
| **realiza** | CICLISTA — RESULTADO | CICLISTA (0,N) · RESULTADO (1,1) | 1:N |
| **refere-se** | RESULTADO — ETAPA | RESULTADO (1,1) · ETAPA (1,N) | N:1 |
| **pertence** | ETAPA — EDICAO | ETAPA (1,1) · EDICAO (1,N) | N:1 |

```
CICLISTA (0,N) ──< realiza >── (1,1) RESULTADO (1,1) ──< refere-se >── (1,N) ETAPA (1,1) ──< pertence >── (1,N) EDICAO
```

Leitura: um ciclista realiza zero ou vários resultados; cada resultado é de um único ciclista e de uma única etapa; cada etapa tem um ou mais resultados e pertence a uma única edição; cada edição tem uma ou mais etapas.

> `equipe` fica em RESULTADO e não em CICLISTA porque a equipe muda de uma edição para outra.
> Restrição: "um ciclista tem no máximo um resultado por etapa" — `UNIQUE (ciclista_id, etapa_id)`.
> No conjunto de dados carregado, 34 edições têm só os dados da edição (sem etapas); isso é limitação da fonte, não do modelo.

### 8.2 Esquema relacional equivalente (referência para a comparação do Trabalho II)

```
ciclista(ciclista_id, nome, pais, data_nascimento)
edicao(ano, edicao, data_inicio, distancia_km, tempo_total_h, vencedor, equipe_vencedora, vitorias_etapa, etapas_lideradas)
etapa(etapa_id, ano#, numero, data_etapa, tipo, distancia_km, origem, destino, vencedor)
resultado(resultado_id, ciclista_id#, etapa_id#, posicao_final, status, equipe, idade, pontos)
```

### 8.3 Prévia do mapeamento para Cassandra (detalhar no Trabalho II)

No Cassandra a modelagem parte das consultas, não das entidades. Etapa = (`ano`, `ordem`).

| Tabela | PRIMARY KEY | Consulta atendida |
|---|---|---|
| `ciclistas` | `ciclista_id` | dados cadastrais |
| `edicoes` | `ano` | dados de uma edição |
| `etapas` | `((ano), ordem)` | etapas de uma edição |
| `resultados_por_etapa` | `((ano, ordem), posicao, ciclista_id)` | ranking de uma etapa |
| `resultados_por_ciclista` | `((ciclista_id), ano, ordem)` | histórico de um ciclista |

Decisões a justificar:
- duplicação dos resultados em duas tabelas (uma por padrão de consulta);
- `nome` e `equipe` desnormalizados em `resultados_por_etapa`; `data_etapa`, `tipo` e `distancia_km` desnormalizados em `resultados_por_ciclista`;
- `resultado_id` e `etapa_id` não existem no Cassandra: (`ano`, `ordem`) identifica a etapa e (`ciclista_id`, `ano`, `ordem`) identifica o resultado;
- `posicao = 9999` para não classificados, já que chave de clustering não aceita nulo (o motivo fica na coluna `status`).

Script CQL completo: `modelo_cassandra_ciclismo.cql`. Preparação dos dados: `preparar_dados.py`.

### 8.4 Chaves primárias

**No MER / modelo relacional**

| Entidade | Chave primária | Observação |
|---|---|---|
| CICLISTA | `ciclista_id` | chave substituta (UUID v5 do nome normalizado) |
| EDICAO | `ano` | uma edição por ano; `edicao` (número) é chave candidata |
| ETAPA | `etapa_id` | chave substituta; (`ano`, `ordem`) é chave candidata |
| RESULTADO | `resultado_id` | chave substituta; (`ciclista_id`, `etapa_id`) é chave candidata (UNIQUE) |

**No Cassandra** (PK = partition key + clustering keys)

| Tabela | PRIMARY KEY | Por quê |
|---|---|---|
| `ciclistas` | `ciclista_id` | busca direta por id |
| `edicoes` | `ano` | busca direta por ano |
| `etapas` | `((ano), ordem)` | todas as etapas de uma edição, em ordem |
| `resultados_por_etapa` | `((ano, ordem), posicao, ciclista_id)` | `ciclista_id` desempata posições repetidas (ex.: 9999 dos não classificados); maior partição: 198 linhas |
| `resultados_por_ciclista` | `((ciclista_id), ano, ordem)` | histórico do mais recente para o mais antigo; maior partição: 328 linhas |

---

## Pendências

- [x] Dataset definido: somente Tour de France
- [x] Script de preparação (`preparar_dados.py`) — gera os 5 CSVs
- [ ] Redesenhar o MER no brModelo (remover TELEMETRIA; PROVA → ETAPA; incluir EDICAO)
- [ ] Atualizar os slides (problema, justificativa, dados, modelo, mapeamento)
- [ ] Subir Cassandra no Docker/WSL2, rodar o `.cql` e carregar os CSVs com `COPY`
- [ ] Confirmar com o professor o formato de entrega e se "5 tabelas × 100 linhas" é por tabela ou total

## Para o Trabalho II

- Problema e justificativa
- Modelagem (MER → Cassandra, com justificativas)
- Demonstração do sistema (INSERT/UPDATE/DELETE + dados reais)
- Consultas: 3 simples, 3 com múltiplos critérios, 2 de agregação, 2 avançadas (particionamento, replicação, CQL)
- Comparação NoSQL × relacional (10 critérios do enunciado)
- Conclusão
