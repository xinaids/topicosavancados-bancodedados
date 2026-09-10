#!/bin/bash
# =========================================================
# setup_mint.sh - Instalação completa para a Oficina Cassandra
# Testado para Linux Mint 22.3 (base Ubuntu 24.04)
#
# O que este script faz:
#   1. Instala Docker
#   2. Sobe o container do Cassandra
#   3. Cria ambiente Python (venv) com Flask + cassandra-driver
#   4. Libera a porta 5000 no firewall (se o ufw estiver ativo)
#   5. Deixa tudo pronto para rodar o lab_server_gamificado.py
#
# Uso:
#   chmod +x setup_mint.sh
#   ./setup_mint.sh
# =========================================================

set -e

PASTA_PROJETO="$HOME/oficinacassandra"
NOME_CONTAINER="cassandra-oficina"

echo "================================================"
echo " Oficina Cassandra - Setup para Linux Mint 22.3"
echo "================================================"
echo ""

# --- 1. Docker ---------------------------------------------------
echo "[1/6] Verificando Docker..."
if ! command -v docker &> /dev/null; then
    echo "Docker não encontrado. Instalando..."
    sudo apt update
    sudo apt install -y docker.io
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker "$USER"
    echo ""
    echo ">>> Docker instalado. É necessário fazer LOGOUT e LOGIN novamente"
    echo ">>> (ou reiniciar o computador) para usar o Docker sem sudo."
    echo ">>> Depois de logar de novo, rode este script mais uma vez."
    exit 0
else
    echo "Docker já instalado: $(docker --version)"
fi

# --- 2. Testar se o usuário consegue rodar docker sem sudo -------
echo ""
echo "[2/6] Testando permissões do Docker..."
if ! docker ps &> /dev/null; then
    echo "ERRO: seu usuário ainda não tem permissão para rodar Docker sem sudo."
    echo "Faça logout/login (ou reinicie) e rode o script novamente."
    exit 1
fi
echo "OK - Docker acessível sem sudo."

# --- 3. Subir o Cassandra ------------------------------------------
echo ""
echo "[3/6] Configurando o container do Cassandra..."
if [ "$(docker ps -aq -f name=$NOME_CONTAINER)" ]; then
    echo "Container '$NOME_CONTAINER' já existe."
    if [ "$(docker ps -q -f name=$NOME_CONTAINER)" ]; then
        echo "Já está em execução."
    else
        echo "Iniciando container existente..."
        docker start "$NOME_CONTAINER"
    fi
else
    echo "Baixando imagem e criando container (pode demorar alguns minutos)..."
    docker run --name "$NOME_CONTAINER" -d -p 9042:9042 cassandra:latest
fi

echo "Aguardando o Cassandra ficar pronto para aceitar conexões..."
echo -n "Aguardando"
TENTATIVAS=0
until docker exec "$NOME_CONTAINER" cqlsh -e "describe keyspaces" &> /dev/null; do
    echo -n "."
    sleep 5
    TENTATIVAS=$((TENTATIVAS+1))
    if [ $TENTATIVAS -gt 40 ]; then
        echo ""
        echo "AVISO: o Cassandra está demorando mais que o esperado."
        echo "Verifique os logs com: docker logs $NOME_CONTAINER --tail 30"
        break
    fi
done
echo ""
echo "Cassandra pronto (ou próximo disso)."

# --- 4. Ambiente Python -------------------------------------------
echo ""
echo "[4/6] Configurando ambiente Python..."
mkdir -p "$PASTA_PROJETO"
cd "$PASTA_PROJETO"

if ! command -v python3 &> /dev/null; then
    sudo apt install -y python3
fi

sudo apt install -y python3-venv python3-pip

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install flask cassandra-driver
deactivate

echo "Ambiente Python pronto em: $PASTA_PROJETO/venv"

# --- 5. Firewall ---------------------------------------------------
echo ""
echo "[5/6] Verificando firewall (ufw)..."
if command -v ufw &> /dev/null; then
    if sudo ufw status | grep -q "Status: active"; then
        sudo ufw allow 5000/tcp
        echo "Porta 5000 liberada no ufw."
    else
        echo "ufw está instalado mas inativo - nenhuma ação necessária."
    fi
else
    echo "ufw não encontrado - pulando (verifique manualmente se houver outro firewall)."
fi

# --- 6. Resumo final ------------------------------------------------
echo ""
echo "[6/6] Tudo pronto!"
echo "================================================"
echo " PRÓXIMOS PASSOS"
echo "================================================"
echo "1. Copie o arquivo lab_server_gamificado.py para:"
echo "   $PASTA_PROJETO/"
echo ""
echo "2. Para rodar o servidor:"
echo "   cd $PASTA_PROJETO"
echo "   source venv/bin/activate"
echo "   python3 lab_server_gamificado.py"
echo ""
echo "3. Descubra o IP desta máquina para os outros acessarem:"
echo "   hostname -I"
echo ""
echo "4. Jogadores acessam: http://SEU_IP:5000"
echo "   Projetor/telão acessa: http://SEU_IP:5000/projetor"
echo "================================================"
