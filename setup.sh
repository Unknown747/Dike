#!/bin/bash
# ============================================================
#   DIKE BOT - Setup Otomatis untuk VPS
#   Jalankan: bash setup.sh
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="dike"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON_BIN="$(which python3)"

header() {
    echo ""
    echo -e "${CYAN}${BOLD}============================================================${NC}"
    echo -e "${CYAN}${BOLD}   DIKE BOT - Setup Otomatis${NC}"
    echo -e "${CYAN}${BOLD}============================================================${NC}"
    echo ""
}

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${BLUE}→${NC} $1"; }

check_root() {
    if [ "$EUID" -ne 0 ]; then
        err "Script harus dijalankan sebagai root."
        echo "     Gunakan: sudo bash setup.sh"
        exit 1
    fi
}

check_python() {
    echo -e "${BOLD}[1/5] Memeriksa Python...${NC}"
    if ! command -v python3 &>/dev/null; then
        warn "Python3 tidak ditemukan. Menginstall..."
        apt update -y && apt install python3 python3-pip -y
    fi
    PYTHON_BIN="$(which python3)"
    PY_VER=$($PYTHON_BIN --version 2>&1)
    ok "Python ditemukan: $PY_VER"
}

install_deps() {
    echo ""
    echo -e "${BOLD}[2/5] Menginstall dependensi Python...${NC}"
    if ! command -v pip3 &>/dev/null; then
        apt install python3-pip -y
    fi
    pip3 install -r "${BOT_DIR}/requirements.txt" -q
    ok "Dependensi berhasil diinstall"
}

setup_token() {
    echo ""
    echo -e "${BOLD}[3/5] Konfigurasi API Token...${NC}"

    CURRENT_TOKEN=$(grep "^API_TOKEN" "${BOT_DIR}/setting.txt" | cut -d'=' -f2 | tr -d ' ')

    if [ "$CURRENT_TOKEN" = "MASUKKAN_TOKEN_API_ANDA_DISINI" ] || [ -z "$CURRENT_TOKEN" ]; then
        echo ""
        warn "API Token belum diset!"
        echo ""
        echo -e "     Cara mendapatkan token:"
        echo -e "     1. Login ke ${CYAN}Stake.com${NC}"
        echo -e "     2. Klik foto profil → ${BOLD}Settings${NC}"
        echo -e "     3. Pilih tab ${BOLD}API${NC}"
        echo -e "     4. Klik ${BOLD}Create API Key${NC} → salin token"
        echo ""
        read -rp "     Masukkan API Token Anda: " TOKEN_INPUT
        echo ""

        if [ -z "$TOKEN_INPUT" ]; then
            warn "Token kosong. Anda bisa edit manual di: ${BOT_DIR}/setting.txt"
        else
            sed -i "s|API_TOKEN = .*|API_TOKEN = ${TOKEN_INPUT}|" "${BOT_DIR}/setting.txt"
            ok "API Token berhasil disimpan"
        fi
    else
        ok "API Token sudah diset"
    fi
}

choose_run_mode() {
    echo ""
    echo -e "${BOLD}[4/5] Pilih mode jalan bot...${NC}"
    echo ""
    echo -e "     1) Systemd (auto-restart, jalan di background, aktif saat reboot)"
    echo -e "     2) Manual / screen (kamu jalankan sendiri, cocok jika pakai 'screen')"
    echo ""
    read -rp "     Pilih mode [1/2] (default 1): " MODE_INPUT
    echo ""

    if [ "$MODE_INPUT" = "2" ]; then
        RUN_MODE="manual"
    else
        RUN_MODE="systemd"
    fi
}

setup_systemd() {
    echo -e "${BOLD}     Setup Systemd Service (auto-restart)...${NC}"

    cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=DIKE - Stake.com Dice Auto Bet Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${BOT_DIR}
ExecStart=${PYTHON_BIN} ${BOT_DIR}/bot.py
Restart=always
RestartSec=10
StandardOutput=append:${BOT_DIR}/dike.log
StandardError=append:${BOT_DIR}/dike.log

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}" &>/dev/null
    ok "Service systemd terpasang & aktif saat boot"
}

start_bot() {
    echo ""
    echo -e "${BOLD}[5/5] Menjalankan bot...${NC}"

    CURRENT_TOKEN=$(grep "^API_TOKEN" "${BOT_DIR}/setting.txt" | cut -d'=' -f2 | tr -d ' ')
    if [ "$CURRENT_TOKEN" = "MASUKKAN_TOKEN_API_ANDA_DISINI" ] || [ -z "$CURRENT_TOKEN" ]; then
        warn "API Token belum diset. Bot tidak dijalankan."
        info "Edit token dulu: nano ${BOT_DIR}/setting.txt"
        if [ "$RUN_MODE" = "systemd" ]; then
            info "Lalu jalankan  : systemctl start ${SERVICE_NAME}"
        else
            info "Lalu jalankan  : screen -S dike -dm python3 ${BOT_DIR}/bot.py"
        fi
        return
    fi

    if [ "$RUN_MODE" = "systemd" ]; then
        systemctl restart "${SERVICE_NAME}"
        sleep 2
        STATUS=$(systemctl is-active "${SERVICE_NAME}")
        if [ "$STATUS" = "active" ]; then
            ok "Bot berjalan! (PID: $(systemctl show -p MainPID --value ${SERVICE_NAME}))"
        else
            err "Bot gagal start. Lihat log: journalctl -u ${SERVICE_NAME} -n 30"
        fi
    else
        if ! command -v screen &>/dev/null; then
            warn "'screen' belum terinstall. Menginstall..."
            apt install screen -y
        fi
        # Pastikan tidak ada instance lama bertabrakan
        pkill -f "python3 ${BOT_DIR}/bot.py" 2>/dev/null
        systemctl stop "${SERVICE_NAME}" 2>/dev/null
        systemctl disable "${SERVICE_NAME}" 2>/dev/null

        screen -S dike -dm "${PYTHON_BIN}" "${BOT_DIR}/bot.py"
        sleep 2
        if screen -list | grep -q "dike"; then
            ok "Bot berjalan di dalam screen session 'dike'"
        else
            err "Gagal start di screen. Coba manual: screen -S dike ${PYTHON_BIN} ${BOT_DIR}/bot.py"
        fi
    fi
}

print_summary() {
    echo ""
    echo -e "${CYAN}${BOLD}============================================================${NC}"
    echo -e "${GREEN}${BOLD}   Setup Selesai!${NC}"
    echo -e "${CYAN}${BOLD}============================================================${NC}"
    echo ""
    echo -e "  ${BOLD}Perintah berguna:${NC}"
    echo ""

    if [ "$RUN_MODE" = "systemd" ]; then
        echo -e "  ${CYAN}Lihat status bot${NC}"
        echo -e "    systemctl status ${SERVICE_NAME}"
        echo ""
        echo -e "  ${CYAN}Stop bot${NC}"
        echo -e "    systemctl stop ${SERVICE_NAME}"
        echo ""
        echo -e "  ${CYAN}Restart bot${NC}"
        echo -e "    systemctl restart ${SERVICE_NAME}"
    else
        echo -e "  ${CYAN}Lihat bot yang jalan (masuk ke screen)${NC}"
        echo -e "    screen -r dike"
        echo ""
        echo -e "  ${CYAN}Keluar dari screen tanpa stop bot${NC}"
        echo -e "    tekan  Ctrl+A  lalu  D"
        echo ""
        echo -e "  ${CYAN}Stop bot${NC}"
        echo -e "    screen -S dike -X quit"
        echo ""
        echo -e "  ${CYAN}Jalankan ulang manual${NC}"
        echo -e "    screen -S dike -dm ${PYTHON_BIN} ${BOT_DIR}/bot.py"
    fi

    echo ""
    echo -e "  ${CYAN}Lihat log live${NC}"
    echo -e "    tail -f ${BOT_DIR}/dike.log"
    echo ""
    echo -e "  ${CYAN}Edit konfigurasi (hot reload, tidak perlu restart)${NC}"
    echo -e "    nano ${BOT_DIR}/setting.txt"
    echo ""
}

# ── JALANKAN ──────────────────────────────────────────────
header
check_root
check_python
install_deps
setup_token
choose_run_mode
if [ "$RUN_MODE" = "systemd" ]; then
    setup_systemd
fi
start_bot
print_summary
