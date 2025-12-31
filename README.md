#!/bin/bash

# --- PREVENÇÃO DE ERROS ---
set +m  # Remove mensagens de job
set +H  # Remove erro de '!/bin/bash event not found'
export DEBIAN_FRONTEND=noninteractive

# Log
LOG="/var/log/vpspack_install.log"
rm -f $LOG

# Cores
C_CYAN="\033[1;36m"
C_GREEN="\033[1;32m"
C_WHITE="\033[1;37m"
C_RED="\033[1;31m"
C_RESET="\033[0m"

# --- BARRA DE PROGRESSO ---
function show_progress() {
    local percent=$1
    local message="$2"
    local bar_size=40
    local filled_len=$(( (percent * bar_size) / 100 ))
    local empty_len=$(( bar_size - filled_len ))
    local bar_filled=$(printf "%0.s█" $(seq 1 $filled_len))
    local bar_empty=$(printf "%0.s░" $(seq 1 $empty_len))
    echo -ne "\r${C_WHITE} [${C_CYAN}${bar_filled}${C_RESET}${C_WHITE}${bar_empty}] ${percent}% - ${message} ${C_RESET}"
}

# --- EXECUTOR ---
function run_task() {
    local percent=$1
    local message="$2"
    local command="$3"
    show_progress "$percent" "$message"
    eval "$command" >> $LOG 2>&1
    local status=$?
    if [ $status -ne 0 ]; then
        echo ""
        echo -e "${C_RED}✖ Erro na etapa: $message${C_RESET}"
        sleep 1
    fi
}

# --- INÍCIO ---
clear
echo -e "${C_CYAN}"
echo "   VPSPACK SURREAL MANAGER - INSTALADOR v7.0   "
echo "   =========================================   "
echo -e "${C_RESET}"

# 1. ATUALIZAÇÃO (0-20%)
run_task 10 "Atualizando repositórios..." "apt-get update -y"
run_task 20 "Instalando ferramentas..." "apt-get install -y git python3 python3-pip sqlite3 dos2unix"

# 2. DEPENDÊNCIAS (20-50%)
run_task 35 "Instalando Flask (Web)..." "pip3 install flask --break-system-packages"
run_task 50 "Limpando ambiente antigo..." "rm -rf /opt/vpspack"

# 3. DOWNLOAD E SETUP (50-70%)
run_task 60 "Baixando do GitHub..." "git clone https://github.com/ColtSeals/vpspack-surreal.git /opt/vpspack"
run_task 70 "Aplicando correções..." "cd /opt/vpspack && dos2unix *.py templates/*.html && chmod +x app.py core.py menu.py"

# 4. SERVIÇOS (70-90%)
cat > /etc/systemd/system/vpspack.service <<EOF
[Unit]
Description=VPSPack Surreal
After=network.target
[Service]
User=root
WorkingDirectory=/opt/vpspack
ExecStart=/usr/bin/python3 app.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF

run_task 80 "Registrando serviço..." "systemctl daemon-reload && systemctl enable vpspack"
run_task 90 "Iniciando Painel..." "systemctl restart vpspack"

# 5. ATALHO (90-100%) - AQUI ESTAVA O ERRO, CORRIGIDO COM PRINTF
cmd_shortcut="rm -f /usr/bin/vpspack && printf '#!/bin/bash\ncd /opt/vpspack\npython3 menu.py\n' > /usr/bin/vpspack && chmod +x /usr/bin/vpspack"
run_task 95 "Criando comando 'vpspack'..." "$cmd_shortcut"

# FIM
show_progress 100 "Instalação Concluída!"
echo ""
echo ""

# --- RESUMO ---
IP=$(hostname -I | awk '{print $1}')
echo -e "${C_GREEN}✔ SUCESSO ABSOLUTO!${C_RESET}"
echo "------------------------------------------------"
echo -e " 🌎 Painel Web:  ${C_CYAN}http://$IP:5000${C_RESET}"
echo -e " 👤 Login:       ${C_WHITE}admin${C_RESET} / ${C_WHITE}admin${C_RESET}"
echo -e " 💻 Terminal:    Digite ${C_CYAN}vpspack${C_RESET}"
echo "------------------------------------------------"
