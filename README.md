# DIKE - Stake.com Dice Auto Bet Bot (IDR)

Bot auto bet untuk game Dice di Stake.com, berjalan 24/7 di VPS.

## Fitur
- Taruhan otomatis menggunakan IDR
- Semua aturan dari `setting.txt` (loss/win streak, safety stop)
- **Cek Saldo Otomatis** — berhenti jika saldo tidak cukup
- **Hot Reload Config** — edit `setting.txt` tanpa restart bot
- **Statistik Harian** — ringkasan P/L otomatis setiap pergantian hari
- **Log ke File** — semua aktivitas tersimpan di `dike.log`
- **Auto-restart via Systemd** — bot otomatis hidup kembali jika crash

---

## Setup di VPS

### 1. Upload file ke VPS
```bash
# Dari komputer lokal
scp -r ./dike root@IP_VPS_ANDA:/root/dike

# Atau clone dari git
git clone <repo_url> /root/dike
```

### 2. Install Python & dependensi
```bash
sudo apt update && sudo apt install python3 python3-pip -y
pip3 install -r /root/dike/requirements.txt
```

### 3. Dapatkan API Token Stake.com
1. Login ke **Stake.com**
2. Klik foto profil → **Settings**
3. Pilih tab **API**
4. Klik **Create API Key** → salin token

### 4. Edit `setting.txt`
```bash
nano /root/dike/setting.txt
```
Ganti:
```
API_TOKEN = MASUKKAN_TOKEN_API_ANDA_DISINI
```
Menjadi token Anda.

---

## Auto-restart via Systemd

### Install service
```bash
# Salin file service
cp /root/dike/dike.service /etc/systemd/system/dike.service

# Jika folder bot bukan /root/dike, edit path dulu
nano /etc/systemd/system/dike.service
# Ubah WorkingDirectory dan ExecStart sesuai lokasi folder bot

# Aktifkan & jalankan
systemctl daemon-reload
systemctl enable dike
systemctl start dike
```

### Perintah penting systemd
```bash
# Lihat status bot
systemctl status dike

# Lihat log live
journalctl -u dike -f

# Atau lihat file log langsung
tail -f /root/dike/dike.log

# Stop bot
systemctl stop dike

# Restart bot
systemctl restart dike

# Nonaktifkan auto-start
systemctl disable dike
```

---

## Hot Reload Config
Edit `setting.txt` kapan saja **tanpa perlu restart bot**.
Bot akan otomatis mendeteksi perubahan dan menerapkan konfigurasi baru pada bet berikutnya.

```bash
nano /root/dike/setting.txt
# Simpan → bot langsung pakai config baru
```

---

## Cek Saldo Otomatis
Bot mengecek saldo setiap **50 bet**:
- Jika saldo < nilai bet saat ini → reset ke base bet
- Jika saldo < `MIN_BALANCE_IDR` → bot berhenti otomatis

Atur di `setting.txt`:
```
MIN_BALANCE_IDR = 10000   # bot berhenti jika saldo < Rp 10.000
MAX_BET_IDR     = 5000    # bet tidak akan melebihi Rp 5.000
```
Nilai `0` = tidak ada batas.

---

## Statistik Harian
Setiap pergantian hari (00:00), bot mencetak ringkasan otomatis ke log:
```
[STAT] ==========================================
[STAT]   STATISTIK HARIAN — 2025-01-15
[STAT]   Total Bet    : 1440
[STAT]   Total Menang : 712
[STAT]   Total Kalah  : 728
[STAT]   Win Rate     : 49.4%
[STAT]   Total P/L    : Rp +12.500
[STAT]   Menang Terbesar : Rp +4.750
[STAT]   Kalah Terbesar  : Rp -2.350
[STAT] ==========================================
```

---

## Konfigurasi `setting.txt`

| Parameter | Keterangan | Default |
|---|---|---|
| `API_TOKEN` | Token API dari Stake.com | wajib diisi |
| `CURRENCY` | Mata uang | `idr` |
| `Set Base Bet` | Taruhan awal (IDR) | `100` |
| `CUSTOM_DELAY_MS` | Jeda antar bet (ms) | `300` |
| `DEFAULT_WIN_CHANCE` | Peluang menang default (%) | `49.50` |
| `MAX_BET_IDR` | Batas bet maksimum (0=bebas) | `0` |
| `MIN_BALANCE_IDR` | Batas saldo minimum (0=bebas) | `0` |
| `STOP_LOSS_IDR` | Batas rugi per sesi | `5000` |
| `STOP_LOSS_PAUSE_MINUTES` | Lama pause setelah stop loss | `2` |
