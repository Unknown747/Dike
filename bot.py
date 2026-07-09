#!/usr/bin/env python3
"""
DIKE - Stake.com Dice Auto Bet Bot (IDR)
Dioptimalkan dari hasil simulasi Monte Carlo
Fitur: Cek Saldo, Hot Reload, Statistik Harian, Recovery Mode, Log File, Systemd
"""

import time
import sys
import uuid
import os
import requests
from datetime import datetime, date

# ─────────────────────────────────────────────
#  LOG KE FILE + TERMINAL
# ─────────────────────────────────────────────

LOG_FILE = "dike.log"

def log(msg, level="INFO"):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# ─────────────────────────────────────────────
#  BACA KONFIGURASI (HOT RELOAD)
# ─────────────────────────────────────────────

SETTING_FILE = "setting.txt"
_last_mtime  = 0

def parse_setting(filepath=SETTING_FILE):
    cfg = {}
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "Set Base Bet" in line:
                cfg["BASE_BET"] = line.split("=")[-1].strip()
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                cfg[key.strip()] = val.strip()
    return cfg

def load_config():
    cfg = parse_setting()

    api_token = cfg.get("API_TOKEN", "")
    if not api_token or api_token == "MASUKKAN_TOKEN_API_ANDA_DISINI":
        log("API_TOKEN belum diset di setting.txt!", "ERROR")
        sys.exit(1)

    return {
        "api_token":              api_token,
        "currency":               cfg.get("CURRENCY", "idr").lower(),
        "base_bet":               float(cfg.get("BASE_BET", "100")),
        "delay_ms":               float(cfg.get("CUSTOM_DELAY_MS", "300")),
        "default_win_chance":     float(cfg.get("DEFAULT_WIN_CHANCE", "49.50")),
        "max_bet":                float(cfg.get("MAX_BET_IDR", "3500")),
        "min_balance":            float(cfg.get("MIN_BALANCE_IDR", "50000")),

        # Loss streak
        "ls3_increase_pct":       float(cfg.get("LOSS_STREAK_3_INCREASE_BET_PERCENT", "250")),
        "ls3_win_chance":         float(cfg.get("LOSS_STREAK_3_WIN_CHANCE", "92.00")),
        "ls4_win_chance":         float(cfg.get("LOSS_STREAK_4_WIN_CHANCE", "89.00")),
        "ls5_win_chance":         float(cfg.get("LOSS_STREAK_5_WIN_CHANCE", "94.01")),
        "ls6_increase_pct":       float(cfg.get("LOSS_STREAK_6_INCREASE_BET_PERCENT", "300")),
        "ls6_win_chance":         float(cfg.get("LOSS_STREAK_6_WIN_CHANCE", "93.00")),

        # Win streak
        "win_every_3_reset":      cfg.get("WIN_EVERY_3_RESET_BET", "true").lower() == "true",
        "ws2_decrease_pct":       float(cfg.get("WIN_STREAK_2_DECREASE_BET_PERCENT", "70")),
        "ws4_win_chance":         float(cfg.get("WIN_STREAK_4_WIN_CHANCE", "70.00")),
        "ws6_win_chance":         float(cfg.get("WIN_STREAK_6_WIN_CHANCE", "65.00")),

        # Reset & safety
        "win_reset_win_chance":   cfg.get("WIN_RESET_WIN_CHANCE", "true").lower() == "true",
        "every9_reset_chance":    cfg.get("EVERY_9_BETS_RESET_WIN_CHANCE", "true").lower() == "true",
        "stop_loss":              float(cfg.get("STOP_LOSS_IDR", "2000")),
        "stop_loss_pause_min":    float(cfg.get("STOP_LOSS_PAUSE_MINUTES", "2")),

        # Recovery mode
        "recovery_mode":          cfg.get("RECOVERY_MODE", "true").lower() == "true",
        "recovery_win_chance":    float(cfg.get("RECOVERY_WIN_CHANCE", "90.00")),
        "recovery_bet_mult":      float(cfg.get("RECOVERY_BET_MULTIPLIER", "1.0")),
        "recovery_exit_pct":      float(cfg.get("RECOVERY_EXIT_PCT", "80")),
        "recovery_min_deficit":   float(cfg.get("RECOVERY_MIN_DEFICIT", "0")),
    }

def check_hot_reload(cfg):
    global _last_mtime
    try:
        mtime = os.path.getmtime(SETTING_FILE)
        if mtime != _last_mtime:
            _last_mtime = mtime
            if _last_mtime != 0:
                log("setting.txt berubah — reload konfigurasi...", "RELOAD")
            return load_config()
    except Exception as e:
        log(f"Gagal reload config: {e}", "WARN")
    return cfg

# ─────────────────────────────────────────────
#  STAKE.COM GRAPHQL API
# ─────────────────────────────────────────────

GRAPHQL_URL = "https://api.stake.com/graphql"

DICE_ROLL_MUTATION = """
mutation DiceRoll($amount: Float!, $target: Float!, $condition: CasinoGameDiceConditionEnum!, $currency: CurrencyEnum!, $identifier: String!) {
  diceRoll(amount: $amount, target: $target, condition: $condition, currency: $currency, identifier: $identifier) {
    id
    active
    payoutMultiplier
    amountMultiplier
    amount
    payout
    updatedAt
    currency
    result {
      ... on CasinoGameDice {
        result
        target
        condition
      }
    }
  }
}
"""

USER_QUERY = """{ user { id name balances { available { amount currency } } } }"""

def make_headers(api_token):
    return {"Content-Type": "application/json", "x-access-token": api_token}

def get_user_info(api_token):
    resp = requests.post(GRAPHQL_URL, json={"query": USER_QUERY},
                         headers=make_headers(api_token), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise Exception(f"API Error: {data['errors']}")
    return data["data"]["user"]

def get_balance(api_token, currency):
    user = get_user_info(api_token)
    for bal in user["balances"]:
        if bal["available"]["currency"].lower() == currency:
            return float(bal["available"]["amount"])
    return 0.0

def roll_dice(api_token, amount, win_chance, currency):
    target  = round(100.0 - win_chance, 4)
    payload = {
        "query": DICE_ROLL_MUTATION,
        "variables": {
            "amount": amount, "target": target,
            "condition": "above", "currency": currency,
            "identifier": str(uuid.uuid4()),
        },
    }
    resp = requests.post(GRAPHQL_URL, json=payload,
                         headers=make_headers(api_token), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise Exception(f"API Error: {data['errors']}")
    return data["data"]["diceRoll"]

# ─────────────────────────────────────────────
#  STATISTIK HARIAN
# ─────────────────────────────────────────────

def make_daily_stats():
    return {"date": str(date.today()), "bets": 0, "wins": 0, "losses": 0,
            "profit": 0.0, "biggest_win": 0.0, "biggest_loss": 0.0,
            "recovery_bets": 0, "recovery_profit": 0.0}

def print_daily_stats(stats):
    log("=" * 58, "STAT")
    log(f"  STATISTIK HARIAN — {stats['date']}", "STAT")
    log(f"  Total Bet         : {stats['bets']}", "STAT")
    log(f"  Total Menang      : {stats['wins']}", "STAT")
    log(f"  Total Kalah       : {stats['losses']}", "STAT")
    wr = (stats['wins'] / stats['bets'] * 100) if stats['bets'] > 0 else 0
    log(f"  Win Rate          : {wr:.1f}%", "STAT")
    sign = "+" if stats["profit"] >= 0 else ""
    log(f"  Total P/L         : Rp {sign}{stats['profit']:,.0f}", "STAT")
    log(f"  Win Terbesar      : Rp +{stats['biggest_win']:,.0f}", "STAT")
    log(f"  Kalah Terbesar    : Rp -{stats['biggest_loss']:,.0f}", "STAT")
    if stats["recovery_bets"] > 0:
        rsign = "+" if stats["recovery_profit"] >= 0 else ""
        log(f"  Bet Recovery      : {stats['recovery_bets']}", "STAT")
        log(f"  P/L saat Recovery : Rp {rsign}{stats['recovery_profit']:,.0f}", "STAT")
    log("=" * 58, "STAT")

# ─────────────────────────────────────────────
#  ATURAN BETTING
# ─────────────────────────────────────────────

def apply_rules(cfg, state):
    bet        = state["bet"]
    win_chance = state["win_chance"]
    ls, ws     = state["loss_streak"], state["win_streak"]

    if ls >= 6:
        bet        = bet * (1 + cfg["ls6_increase_pct"] / 100)
        win_chance = cfg["ls6_win_chance"]
        log(f"  [RULE] Loss streak {ls}: bet naik {cfg['ls6_increase_pct']}%, chance → {win_chance}%")
    elif ls == 5:
        win_chance = cfg["ls5_win_chance"]
        log(f"  [RULE] Loss streak {ls}: chance → {win_chance}%")
    elif ls == 4:
        win_chance = cfg["ls4_win_chance"]
        log(f"  [RULE] Loss streak {ls}: chance → {win_chance}%")
    elif ls == 3:
        bet        = bet * (1 + cfg["ls3_increase_pct"] / 100)
        win_chance = cfg["ls3_win_chance"]
        log(f"  [RULE] Loss streak {ls}: bet naik {cfg['ls3_increase_pct']}%, chance → {win_chance}%")

    if ws >= 6:
        win_chance = cfg["ws6_win_chance"]
        log(f"  [RULE] Win streak {ws}: chance → {win_chance}%")
    elif ws >= 4:
        win_chance = cfg["ws4_win_chance"]
        log(f"  [RULE] Win streak {ws}: chance → {win_chance}%")
    elif ws >= 2:
        bet = bet * (cfg["ws2_decrease_pct"] / 100)
        log(f"  [RULE] Win streak {ws}: bet turun {cfg['ws2_decrease_pct']}%")

    if cfg["win_every_3_reset"] and state["total_wins"] > 0 \
            and state["total_wins"] % 3 == 0 \
            and state.get("_last_reset_at") != state["total_wins"]:
        bet = cfg["base_bet"]
        state["_last_reset_at"] = state["total_wins"]
        log(f"  [RULE] Total {state['total_wins']} menang: reset bet → Rp {cfg['base_bet']:,.0f}")

    # Terapkan batas bet maksimum
    if cfg["max_bet"] > 0 and bet > cfg["max_bet"]:
        log(f"  [RULE] Bet Rp {bet:,.0f} melebihi MAX_BET, dikunci → Rp {cfg['max_bet']:,.0f}")
        bet = cfg["max_bet"]

    state["bet"]        = max(round(bet), 1)
    state["win_chance"] = round(win_chance, 4)
    return state

# ─────────────────────────────────────────────
#  LOOP UTAMA
# ─────────────────────────────────────────────

def run_bot():
    global _last_mtime
    _last_mtime = 0

    cfg = load_config()
    _last_mtime = os.path.getmtime(SETTING_FILE)

    log("=" * 60)
    log("  DIKE - Stake.com Dice Auto Bet Bot  [IDR]")
    log("  Versi: Optimized (Hasil Simulasi Monte Carlo)")
    log("=" * 60)

    # Verifikasi akun & saldo awal
    try:
        user    = get_user_info(cfg["api_token"])
        balance = get_balance(cfg["api_token"], cfg["currency"])
        log(f"Login sebagai    : {user['name']} (ID: {user['id']})")
        log(f"Saldo {cfg['currency'].upper()}         : Rp {balance:,.2f}")
    except Exception as e:
        log(f"Gagal verifikasi akun: {e}", "ERROR")
        sys.exit(1)

    log(f"\nKonfigurasi aktif:")
    log(f"  Base Bet         : Rp {cfg['base_bet']:,.0f}")
    log(f"  Max Bet          : Rp {cfg['max_bet']:,.0f}")
    log(f"  Min Saldo        : Rp {cfg['min_balance']:,.0f}")
    log(f"  Win Chance       : {cfg['default_win_chance']}%")
    log(f"  Stop Loss/sesi   : Rp {cfg['stop_loss']:,.0f}")
    log(f"  Pause            : {cfg['stop_loss_pause_min']} menit")
    log(f"  Recovery Mode    : {'AKTIF ✓' if cfg['recovery_mode'] else 'NONAKTIF'}")
    if cfg["recovery_mode"]:
        log(f"  Recovery Chance  : {cfg['recovery_win_chance']}%")
        log(f"  Recovery Exit    : {cfg['recovery_exit_pct']}% deficit terpulihkan")
    log("")

    state = {
        "bet":              cfg["base_bet"],
        "win_chance":       cfg["default_win_chance"],
        "loss_streak":      0,
        "win_streak":       0,
        "total_wins":       0,
        "total_losses":     0,
        "total_bets":       0,
        "session_loss":     0.0,
        "total_profit":     0.0,
        "_last_reset_at":   -1,
    }

    # State recovery
    recovery_active    = False
    total_deficit      = 0.0
    recovered_amount   = 0.0

    daily         = make_daily_stats()
    today         = date.today()
    balance_check = 0

    while True:
        try:
            # ── HOT RELOAD ──────────────────────────────
            cfg = check_hot_reload(cfg)

            # ── GANTI HARI → CETAK STATISTIK ────────────
            if date.today() != today:
                print_daily_stats(daily)
                daily = make_daily_stats()
                today = date.today()
                log(f"Hari baru: {today}")

            # ── CEK SALDO SETIAP 50 BET ──────────────────
            balance_check += 1
            if balance_check >= 50:
                balance_check = 0
                try:
                    balance = get_balance(cfg["api_token"], cfg["currency"])
                    log(f"[CEK SALDO] Rp {balance:,.2f}")
                    if cfg["min_balance"] > 0 and balance < cfg["min_balance"]:
                        log(f"[CEK SALDO] Saldo Rp {balance:,.0f} di bawah batas "
                            f"Rp {cfg['min_balance']:,.0f}. Bot berhenti!", "WARN")
                        print_daily_stats(daily)
                        sys.exit(0)
                    if balance < state["bet"]:
                        log(f"[CEK SALDO] Saldo tidak cukup untuk bet "
                            f"Rp {state['bet']:,.0f}, reset ke base bet.", "WARN")
                        state["bet"] = cfg["base_bet"]
                except Exception as e:
                    log(f"Gagal cek saldo: {e}", "WARN")

            # ── SAFETY STOP ──────────────────────────────
            if state["session_loss"] >= cfg["stop_loss"]:
                pause_sec    = cfg["stop_loss_pause_min"] * 60
                total_deficit += state["session_loss"]
                log(f"[SAFETY STOP] Loss Rp {state['session_loss']:,.0f} >= batas. "
                    f"Pause {cfg['stop_loss_pause_min']} menit... "
                    f"(Total deficit: Rp {total_deficit:,.0f})", "WARN")
                time.sleep(pause_sec)

                state["session_loss"] = 0.0
                state["loss_streak"]  = 0
                state["win_streak"]   = 0

                # Masuk recovery mode jika aktif & ada deficit
                if cfg["recovery_mode"] and total_deficit > cfg["recovery_min_deficit"]:
                    recovery_active  = True
                    recovered_amount = 0.0
                    rec_bet = max(round(cfg["base_bet"] * cfg["recovery_bet_mult"]), 1)
                    state["bet"]        = rec_bet
                    state["win_chance"] = cfg["recovery_win_chance"]
                    log(f"[RECOVERY] Mode aktif | Bet: Rp {rec_bet:,.0f} | "
                        f"Win chance: {cfg['recovery_win_chance']}% | "
                        f"Target pulih: Rp {total_deficit * cfg['recovery_exit_pct']/100:,.0f}", "RECOVERY")
                else:
                    state["bet"]        = cfg["base_bet"]
                    state["win_chance"] = cfg["default_win_chance"]

                log("[SAFETY STOP] Bot lanjut betting...")

            # ── TENTUKAN BET & CHANCE ────────────────────
            current_bet        = int(state["bet"])
            current_win_chance = state["win_chance"]

            mode_label = "[RECOVERY]" if recovery_active else "[NORMAL]  "
            log(f"{mode_label} Bet #{state['total_bets']+1} | "
                f"Rp {current_bet:,} | Chance: {current_win_chance}% | "
                f"Streak K:{state['loss_streak']} M:{state['win_streak']}")

            result = roll_dice(cfg["api_token"], current_bet, current_win_chance, cfg["currency"])

            dice_result = result["result"]["result"]
            payout      = float(result["payout"])
            amount      = float(result["amount"])
            won         = payout > 0

            state["total_bets"] += 1
            daily["bets"]       += 1

            if won:
                profit = payout - amount
                state["total_profit"]  += profit
                state["total_wins"]    += 1
                state["win_streak"]    += 1
                state["loss_streak"]    = 0
                daily["wins"]          += 1
                daily["profit"]        += profit
                daily["biggest_win"]    = max(daily["biggest_win"], profit)

                log(f"  ✓ MENANG  | Roll: {dice_result:.2f} | "
                    f"Payout: Rp {payout:,.0f} | Profit: +Rp {profit:,.0f}")

                if recovery_active:
                    recovered_amount         += profit
                    daily["recovery_bets"]   += 1
                    daily["recovery_profit"] += profit

                    target = total_deficit * (cfg["recovery_exit_pct"] / 100)
                    log(f"  [RECOVERY] Terpulihkan: Rp {recovered_amount:,.0f} / "
                        f"Rp {target:,.0f} ({recovered_amount/target*100:.1f}%)", "RECOVERY")

                    if recovered_amount >= target:
                        recovery_active  = False
                        total_deficit    = 0.0
                        recovered_amount = 0.0
                        state["bet"]        = cfg["base_bet"]
                        state["win_chance"] = cfg["default_win_chance"]
                        state["loss_streak"] = 0
                        state["win_streak"]  = 0
                        log(f"[RECOVERY] Selesai! Kembali ke mode normal. "
                            f"Base bet: Rp {cfg['base_bet']:,.0f}", "RECOVERY")
                else:
                    if cfg["win_reset_win_chance"]:
                        state["win_chance"] = cfg["default_win_chance"]

            else:
                state["session_loss"]  += amount
                state["total_profit"]  -= amount
                state["total_losses"]  += 1
                state["loss_streak"]   += 1
                state["win_streak"]     = 0
                daily["losses"]        += 1
                daily["profit"]        -= amount
                daily["biggest_loss"]   = max(daily["biggest_loss"], amount)

                if recovery_active:
                    total_deficit            += amount
                    daily["recovery_bets"]   += 1
                    daily["recovery_profit"] -= amount

                log(f"  ✗ KALAH   | Roll: {dice_result:.2f} | "
                    f"Loss: -Rp {amount:,.0f} | "
                    f"Session loss: Rp {state['session_loss']:,.0f}")

            # Reset win chance setiap 9 bet (hanya di mode normal)
            if not recovery_active and cfg["every9_reset_chance"] \
                    and state["total_bets"] % 9 == 0:
                state["win_chance"] = cfg["default_win_chance"]
                log(f"  [RULE] Setiap 9 bet: reset chance → {cfg['default_win_chance']}%")

            # Terapkan aturan (hanya di mode normal)
            if not recovery_active:
                state = apply_rules(cfg, state)

            sign = "+" if state["total_profit"] >= 0 else ""
            log(f"  Total P/L : Rp {sign}{state['total_profit']:,.0f} | "
                f"M: {state['total_wins']} K: {state['total_losses']}"
                + (f" | Deficit: Rp {total_deficit:,.0f}" if recovery_active else ""))

            time.sleep(cfg["delay_ms"] / 1000.0)

        except KeyboardInterrupt:
            log("\nBot dihentikan.", "STOP")
            print_daily_stats(daily)
            sign = "+" if state["total_profit"] >= 0 else ""
            log(f"  Total Bet    : {state['total_bets']}")
            log(f"  Total Menang : {state['total_wins']}")
            log(f"  Total Kalah  : {state['total_losses']}")
            log(f"  Total P/L    : Rp {sign}{state['total_profit']:,.0f}")
            sys.exit(0)

        except requests.exceptions.ConnectionError:
            log("Koneksi terputus. Retry 10 detik...", "ERROR")
            time.sleep(10)

        except requests.exceptions.Timeout:
            log("Request timeout. Retry 10 detik...", "ERROR")
            time.sleep(10)

        except Exception as e:
            log(f"{e}. Retry 15 detik...", "ERROR")
            time.sleep(15)

if __name__ == "__main__":
    run_bot()
