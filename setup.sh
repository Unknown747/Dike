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

setup_systemd() {
    echo ""
    echo -e "${BOLD}[4/5] Setup Systemd Service (auto-restart)...${NC}"

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
        info "Lalu jalankan  : systemctl start ${SERVICE_NAME}"
        return
    fi

    systemctl restart "${SERVICE_NAME}"
    sleep 2
    STATUS=$(systemctl is-active "${SERVICE_NAME}")

    if [ "$STATUS" = "active" ]; then
        ok "Bot berjalan! (PID: $(systemctl show -p MainPID --value ${SERVICE_NAME}))"
    else
        err "Bot gagal start. Lihat log: journalctl -u ${SERVICE_NAME} -n 30"
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
    echo -e "  ${CYAN}Lihat status bot${NC}"
    echo -e "    systemctl status ${SERVICE_NAME}"
    echo ""
    echo -e "  ${CYAN}Lihat log live${NC}"
    echo -e "    tail -f ${BOT_DIR}/dike.log"
    echo ""
    echo -e "  ${CYAN}Stop bot${NC}"
    echo -e "    systemctl stop ${SERVICE_NAME}"
    echo ""
    echo -e "  ${CYAN}Restart bot${NC}"
    echo -e "    systemctl restart ${SERVICE_NAME}"
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
setup_systemd
start_bot
print_summary
