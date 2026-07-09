# DIKE — Stake.com Dice Auto Bet Bot (IDR)

Bot auto bet untuk game Dice di Stake.com menggunakan Python.

## Stack
- Python 3.11
- `requests` — HTTP client untuk Stake.com GraphQL API

## Cara Jalankan di Replit
1. Set secret `STAKE_API_TOKEN` dengan API token dari Stake.com
   - Login Stake.com → Settings → API → Create API Key
2. Edit `setting.txt` sesuai strategi (base bet, stop loss, dll)
3. Jalankan workflow **Start application** (`python bot.py`)

## Cara Jalankan di VPS
```bash
# Install dependensi
pip3 install -r requirements.txt

# Set token di setting.txt
nano setting.txt  # ganti API_TOKEN = <token kamu>

# Install & aktifkan service systemd
cp dike.service /etc/systemd/system/dike.service
# Edit path jika folder bukan /root/dike
nano /etc/systemd/system/dike.service

systemctl daemon-reload
systemctl enable dike
systemctl start dike

# Monitor
journalctl -u dike -f     # live log via systemd
tail -f /root/dike/dike.log  # atau langsung dari file
```

## Konfigurasi (`setting.txt`)
Semua setting ada di `setting.txt` — bot hot-reload otomatis tanpa restart.
| Key | Keterangan |
|-----|-----------|
| `API_TOKEN` | Token API Stake.com (wajib di VPS; Replit pakai secret) |
| `Set Base Bet` | Taruhan awal (IDR) |
| `STOP_LOSS_IDR` | Batas rugi per sesi sebelum pause |
| `MIN_BALANCE_IDR` | Bot berhenti jika saldo di bawah nilai ini |
| `TARGET_WAGER_IDR` | Bot berhenti otomatis setelah total wager tercapai |
| `RECOVERY_MODE` | Aktifkan mode recovery setelah safety stop |

## Perubahan dari Repo Asli
- Header HTTP diperbaiki agar mirip browser (fix 400 Bad Request Stake.com)
- `Accept-Encoding: br` dihapus (requests tidak support Brotli)
- GraphQL field `result` → `state` (schema Stake.com sudah diupdate)
- ANSI strip saat tulis ke log file
- Safety stop tidak interrupt recovery mode
- `session_loss` direset saat recovery selesai (cegah immediate safety stop)
- `dike.service` tidak lagi double-write ke log file

## User Preferences
- Bahasa komunikasi: Indonesia
