#!/bin/bash
# ============================================================
#   DIKE BOT - Clear Log
#   Aman dijalankan saat bot sedang berjalan (truncate, bukan delete)
#   Jalankan: bash clear_log.sh
# ============================================================

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="${BOT_DIR}/dike.log"
BACKUP_DIR="${BOT_DIR}/log_backup"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

echo ""
echo -e "${CYAN}${BOLD}============================================================${NC}"
echo -e "${CYAN}${BOLD}   DIKE BOT - Clear Log${NC}"
echo -e "${CYAN}${BOLD}============================================================${NC}"
echo ""

# Cek apakah log file ada
if [ ! -f "$LOG_FILE" ]; then
    warn "Log file tidak ditemukan: $LOG_FILE"
    exit 0
fi

# Hitung ukuran saat ini
LOG_SIZE=$(du -sh "$LOG_FILE" 2>/dev/null | cut -f1)
LOG_LINES=$(wc -l < "$LOG_FILE" 2>/dev/null)
info "Log saat ini: ${LOG_SIZE} (${LOG_LINES} baris)"

# Buat folder backup jika belum ada
mkdir -p "$BACKUP_DIR"

# Backup dengan timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/dike_${TIMESTAMP}.log"
cp "$LOG_FILE" "$BACKUP_FILE"
ok "Backup disimpan: ${BACKUP_FILE}"

# Truncate — AMAN saat bot jalan (tidak menutup file descriptor bot)
> "$LOG_FILE"
ok "Log berhasil dikosongkan"

echo ""
echo -e "  ${BOLD}Backup log tersimpan di:${NC} ${BACKUP_DIR}/"
echo -e "  ${BOLD}Lihat log live:${NC}          tail -f ${LOG_FILE}"
echo ""
