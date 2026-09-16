# Oficina Cassandra - Bancos de Dados Orientados a Colunas

Instituto Federal do Rio Grande do Sul - Campus Ibirubá
Autores: Mateus Medeiros Schneider, Miguel Bohrz Vogel

Repositório com todo o material da oficina: scripts de instalação, servidor
gamificado da parte prática e gabarito dos exercícios.

## Sumário

- [Sobre a oficina](#sobre-a-oficina)
- [Pré-requisitos](#pré-requisitos)
- [Passo a passo - Instalação (Linux Mint / Ubuntu)](#passo-a-passo---instalação-linux-mint--ubuntu)
- [Rodando o servidor da oficina](#rodando-o-servidor-da-oficina)
- [Como os participantes acessam](#como-os-participantes-acessam)
- [Gabarito dos exercícios](#gabarito-dos-exercícios)
- [Solução de problemas comuns](#solução-de-problemas-comuns)

---

## Sobre a oficina

Esta oficina apresenta o Apache Cassandra como estudo de caso de banco de
dados orientado a colunas. A atividade é dividida em duas etapas:

1. **Teoria**: conceitos de Cassandra, diferenças para o modelo relacional,
   sintaxe CQL, estratégias de modelagem.
2. **Prática**: um jogo web onde cada participante resolve exercícios de CQL
   em tempo real, com pontuação e ranking ao vivo, direto no navegador -
   sem precisar instalar nada na própria máquina.

---

## Pré-requisitos

Apenas na máquina que vai rodar o servidor (não nas máquinas dos
participantes):

- Linux Mint 22.3 (ou qualquer base Ubuntu/Debian recente)
- Acesso à internet para baixar o Docker e a imagem do Cassandra
- Permissão de `sudo`

Os participantes só precisam de um navegador e estar na mesma rede local.

---

## Passo a passo - Instalação (Linux Mint / Ubuntu)

### 1. Baixe o script de instalação

Use o script `setup_mint.sh` deste repositório.

### 2. Dê permissão de execução e rode

```bash
chmod +x setup_mint.sh
./setup_mint.sh
```

O script faz automaticamente:

- Instala o Docker (caso não esteja instalado)
- Sobe o container do Cassandra e aguarda ele ficar pronto
- Cria um ambiente Python (`venv`) com Flask e o driver do Cassandra
- Libera a porta 5000 no firewall, se necessário

> **Se for a primeira instalação do Docker na máquina**, o script vai pedir
> para você fazer logout/login (ou reiniciar) antes de continuar. Depois
> disso, rode o script novamente.

### 3. Confirme que o Cassandra está de pé

```bash
docker ps
```

Deve aparecer o container `cassandra-oficina` com status "Up".

---

## Rodando o servidor da oficina

Copie o arquivo `lab_server_gamificado.py` para a pasta criada pelo script
(`~/oficinacassandra/`) e rode:

```bash
cd ~/oficinacassandra
source venv/bin/activate
python3 lab_server_gamificado.py
```

O servidor sobe em `http://0.0.0.0:5000`, acessível por qualquer dispositivo
na mesma rede.

---

## Como os participantes acessam

1. Descubra o IP da máquina servidor:

```bash
hostname -I
```

2. Cada participante abre no navegador (celular ou notebook, mesma rede
   Wi-Fi/cabo):

```
http://IP_DO_SERVIDOR:5000
```

3. Para exibir o ranking no telão/projetor, abra em tela cheia:

```
http://IP_DO_SERVIDOR:5000/projetor
```

Cada jogador digita um nome, resolve os exercícios de CQL um por vez (com
dicas disponíveis), e acompanha sua pontuação e o ranking geral em tempo
real.

---

## Gabarito dos exercícios

Ver arquivo `gabarito.txt` neste repositório para a lista completa de
comandos CQL esperados em cada exercício.

---

## Solução de problemas comuns

**`docker: command not found`**
O Docker Desktop não está integrado com a distro em uso (comum no WSL).
Ative a integração em Docker Desktop → Settings → Resources → WSL
Integration.

**`Connection refused` ao conectar no Cassandra**
O container ainda está inicializando. Aguarde 1-2 minutos e verifique com:

```bash
docker logs cassandra-oficina --tail 20
```

Procure pela linha indicando que o Cassandra está aceitando conexões CQL.

**`externally-managed-environment` ao rodar `pip install`**
Use um ambiente virtual (já incluso no `setup_mint.sh`):

```bash
python3 -m venv venv
source venv/bin/activate
pip install flask cassandra-driver
```

**Erro de rede / DNS (`Temporary failure in name resolution`)**
Comum em redes corporativas/educacionais com WSL. Teste `ping 8.8.8.8` no
Windows (fora do WSL); se funcionar lá mas não no WSL, ative o modo de rede
mirrored no `.wslconfig`:

```
[wsl2]
networkingMode=mirrored
```

Depois rode `wsl --shutdown` e reabra o terminal.

**Tabela "already exists" ao criar no exercício 1**
Já resolvido no `lab_server_gamificado.py` atual: cada jogador tem uma
tabela isolada internamente, então não há mais conflito entre
participantes.

---

*Material de apoio produzido com auxílio de IA (Claude e ChatGPT) para a
disciplina de Tópicos Avançados de Banco de Dados - IFRS Campus Ibirubá.*
