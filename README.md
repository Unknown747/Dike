# DIKE - Stake.com Dice Auto Bet Bot

Bot auto bet untuk game Dice di Stake.com, berjalan 24/7 di VPS.

---

## Cara Setup di VPS

### 1. Install Python & dependensi
```bash
sudo apt update && sudo apt install python3 python3-pip -y
pip3 install -r requirements.txt
```

### 2. Dapatkan API Token Stake.com
1. Login ke **Stake.com**
2. Klik foto profil → **Settings**
3. Pilih tab **API**
4. Klik **Create API Key** → salin token

### 3. Edit `setting.txt`
Buka file `setting.txt` lalu ganti baris berikut:
```
API_TOKEN = MASUKKAN_TOKEN_API_ANDA_DISINI
```
Menjadi token Anda, contoh:
```
API_TOKEN = abc123xyz...
```

Sesuaikan juga mata uang:
```
CURRENCY = ltc   # bisa: btc, eth, ltc, doge, xrp, trx, eos, bch
```

Dan sesuaikan `BASE_BET` dengan saldo Anda (dalam satuan kripto, bukan IDR).

### 4. Jalankan bot
```bash
python3 bot.py
```

---

## Jalankan 24/7 dengan `screen` (rekomendasi)
```bash
# Install screen
sudo apt install screen -y

# Buat sesi baru
screen -S dikebot

# Jalankan bot
python3 bot.py

# Keluar dari screen tanpa menghentikan bot
# Tekan: Ctrl + A, lalu D

# Lihat bot lagi kapan saja
screen -r dikebot
```

## Alternatif: Jalankan dengan `nohup`
```bash
nohup python3 bot.py > dike.log 2>&1 &
# Lihat log
tail -f dike.log
```

---

## Konfigurasi `setting.txt`

| Parameter | Keterangan |
|---|---|
| `API_TOKEN` | Token API dari Stake.com |
| `CURRENCY` | Mata uang kripto (ltc, btc, dll) |
| `BASE_BET` | Taruhan awal (satuan kripto) |
| `CUSTOM_DELAY_MS` | Jeda antar bet dalam milidetik |
| `DEFAULT_WIN_CHANCE` | Peluang menang default (%) |
| `STOP_LOSS_AMOUNT` | Batas kerugian sesi sebelum bot pause |
| `STOP_LOSS_PAUSE_MINUTES` | Lama pause setelah stop loss |

---

## Hentikan Bot
```bash
# Jika pakai screen
screen -r dikebot
# lalu tekan Ctrl + C

# Jika pakai nohup
kill $(pgrep -f bot.py)
```
