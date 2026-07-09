#!/usr/bin/env python3
"""
DIKE - Stake.com Dice Auto Bet Bot
Berjalan 24/7 di VPS, membaca konfigurasi dari setting.txt
"""

import time
import sys
import os
import requests
from datetime import datetime

# ─────────────────────────────────────────────
#  BACA KONFIGURASI DARI setting.txt
# ─────────────────────────────────────────────

def parse_setting(filepath="setting.txt"):
    cfg = {}
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                cfg[key.strip()] = val.strip()
    return cfg

def load_config():
    cfg = parse_setting()

    api_token = cfg.get("API_TOKEN", "")
    if not api_token or api_token == "MASUKKAN_TOKEN_API_ANDA_DISINI":
        print("[ERROR] API_TOKEN belum diset di setting.txt!")
        sys.exit(1)

    return {
        "api_token":              api_token,
        "currency":               cfg.get("CURRENCY", "ltc").lower(),
        "base_bet":               float(cfg.get("BASE_BET", "0.00000100")),
        "delay_ms":               float(cfg.get("CUSTOM_DELAY_MS", "300")),
        "default_win_chance":     float(cfg.get("DEFAULT_WIN_CHANCE", "49.50")),

        # Loss streak rules
        "ls3_increase_pct":       float(cfg.get("LOSS_STREAK_3_INCREASE_BET_PERCENT", "250")),
        "ls3_win_chance":         float(cfg.get("LOSS_STREAK_3_WIN_CHANCE", "92.00")),
        "ls4_win_chance":         float(cfg.get("LOSS_STREAK_4_WIN_CHANCE", "89.00")),
        "ls5_win_chance":         float(cfg.get("LOSS_STREAK_5_WIN_CHANCE", "94.01")),
        "ls6_increase_pct":       float(cfg.get("LOSS_STREAK_6_INCREASE_BET_PERCENT", "300")),
        "ls6_win_chance":         float(cfg.get("LOSS_STREAK_6_WIN_CHANCE", "93.00")),

        # Win streak rules
        "win_every_3_reset":      cfg.get("WIN_EVERY_3_RESET_BET", "true").lower() == "true",
        "ws2_decrease_pct":       float(cfg.get("WIN_STREAK_2_DECREASE_BET_PERCENT", "70")),
        "ws4_win_chance":         float(cfg.get("WIN_STREAK_4_WIN_CHANCE", "70.00")),
        "ws6_win_chance":         float(cfg.get("WIN_STREAK_6_WIN_CHANCE", "65.00")),

        # Reset & safety
        "win_reset_win_chance":   cfg.get("WIN_RESET_WIN_CHANCE", "true").lower() == "true",
        "every9_reset_chance":    cfg.get("EVERY_9_BETS_RESET_WIN_CHANCE", "true").lower() == "true",
        "stop_loss_amount":       float(cfg.get("STOP_LOSS_AMOUNT", "0.00005000")),
        "stop_loss_pause_min":    float(cfg.get("STOP_LOSS_PAUSE_MINUTES", "2")),
    }

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

USER_QUERY = """
{
  user {
    id
    name
    balances {
      available {
        amount
        currency
      }
    }
  }
}
"""

def make_headers(api_token):
    return {
        "Content-Type": "application/json",
        "x-access-token": api_token,
    }

def get_user_info(api_token):
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": USER_QUERY},
        headers=make_headers(api_token),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise Exception(f"API Error: {data['errors']}")
    return data["data"]["user"]

def roll_dice(api_token, amount, win_chance, currency):
    """
    Taruhan Dice di Stake.com.
    win_chance = persentase peluang menang (mis. 49.50)
    condition  = 'above' → target = 100 - win_chance
    """
    import uuid
    target = round(100.0 - win_chance, 4)
    condition = "above"

    payload = {
        "query": DICE_ROLL_MUTATION,
        "variables": {
            "amount":     amount,
            "target":     target,
            "condition":  condition,
            "currency":   currency,
            "identifier": str(uuid.uuid4()),
        },
    }

    resp = requests.post(
        GRAPHQL_URL,
        json=payload,
        headers=make_headers(api_token),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        raise Exception(f"API Error: {data['errors']}")

    return data["data"]["diceRoll"]

# ─────────────────────────────────────────────
#  LOGIKA BOT
# ─────────────────────────────────────────────

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def apply_rules(cfg, state):
    """
    Terapkan semua aturan dari setting.txt ke state saat ini.
    state keys: bet, win_chance, loss_streak, win_streak, total_wins, total_bets, session_loss
    """
    bet        = state["bet"]
    win_chance = state["win_chance"]
    ls         = state["loss_streak"]
    ws         = state["win_streak"]

    # ── LOSS STREAK ──────────────────────────────
    if ls >= 6:
        bet        = bet * (1 + cfg["ls6_increase_pct"] / 100)
        win_chance = cfg["ls6_win_chance"]
        log(f"  [RULE] Loss streak {ls}: bet naik 300%, win_chance → {win_chance}%")
    elif ls >= 5:
        win_chance = cfg["ls5_win_chance"]
        log(f"  [RULE] Loss streak {ls}: win_chance → {win_chance}%")
    elif ls >= 4:
        win_chance = cfg["ls4_win_chance"]
        log(f"  [RULE] Loss streak {ls}: win_chance → {win_chance}%")
    elif ls >= 3:
        bet        = bet * (1 + cfg["ls3_increase_pct"] / 100)
        win_chance = cfg["ls3_win_chance"]
        log(f"  [RULE] Loss streak {ls}: bet naik 250%, win_chance → {win_chance}%")

    # ── WIN STREAK ───────────────────────────────
    if ws >= 6:
        win_chance = cfg["ws6_win_chance"]
        log(f"  [RULE] Win streak {ws}: win_chance → {win_chance}%")
    elif ws >= 4:
        win_chance = cfg["ws4_win_chance"]
        log(f"  [RULE] Win streak {ws}: win_chance → {win_chance}%")
    elif ws >= 2:
        bet = bet * (cfg["ws2_decrease_pct"] / 100)
        log(f"  [RULE] Win streak {ws}: bet turun 70%")

    # ── RESET BET SETIAP 3 TOTAL MENANG ──────────
    if cfg["win_every_3_reset"] and state["total_wins"] > 0 and state["total_wins"] % 3 == 0:
        bet = cfg["base_bet"]
        log(f"  [RULE] Total {state['total_wins']} menang: reset bet ke base")

    state["bet"]        = max(bet, cfg["base_bet"])
    state["win_chance"] = win_chance
    return state

def run_bot():
    cfg = load_config()

    log("=" * 55)
    log("  DIKE - Stake.com Dice Auto Bet Bot")
    log("=" * 55)

    # Verifikasi akun
    try:
        user = get_user_info(cfg["api_token"])
        log(f"Login sebagai: {user['name']} (ID: {user['id']})")
        for bal in user["balances"]:
            av = bal["available"]
            log(f"  Saldo {av['currency'].upper()}: {av['amount']}")
    except Exception as e:
        log(f"[ERROR] Gagal verifikasi akun: {e}")
        sys.exit(1)

    log(f"\nKonfigurasi aktif:")
    log(f"  Base Bet    : {cfg['base_bet']} {cfg['currency'].upper()}")
    log(f"  Win Chance  : {cfg['default_win_chance']}%")
    log(f"  Delay       : {cfg['delay_ms']} ms")
    log(f"  Stop Loss   : {cfg['stop_loss_amount']} {cfg['currency'].upper()}")
    log(f"  Pause Saat Stop Loss: {cfg['stop_loss_pause_min']} menit")
    log("")

    # State bot
    state = {
        "bet":          cfg["base_bet"],
        "win_chance":   cfg["default_win_chance"],
        "loss_streak":  0,
        "win_streak":   0,
        "total_wins":   0,
        "total_losses": 0,
        "total_bets":   0,
        "session_loss": 0.0,
        "total_profit": 0.0,
    }

    # ── LOOP UTAMA ────────────────────────────────
    while True:
        try:
            # ── SAFETY STOP ──
            if state["session_loss"] >= cfg["stop_loss_amount"]:
                pause_sec = cfg["stop_loss_pause_min"] * 60
                log(f"[SAFETY STOP] Total loss {state['session_loss']:.8f} >= limit. "
                    f"Pause {cfg['stop_loss_pause_min']} menit...")
                time.sleep(pause_sec)
                state["session_loss"] = 0.0
                state["bet"]          = cfg["base_bet"]
                state["win_chance"]   = cfg["default_win_chance"]
                state["loss_streak"]  = 0
                state["win_streak"]   = 0
                log("[SAFETY STOP] Resume betting...")

            current_bet        = round(state["bet"], 8)
            current_win_chance = round(state["win_chance"], 4)

            log(f"Bet #{state['total_bets']+1} | "
                f"Bet: {current_bet:.8f} {cfg['currency'].upper()} | "
                f"Chance: {current_win_chance}% | "
                f"Loss streak: {state['loss_streak']} | Win streak: {state['win_streak']}")

            result = roll_dice(cfg["api_token"], current_bet, current_win_chance, cfg["currency"])

            dice_result = result["result"]["result"]
            payout      = float(result["payout"])
            amount      = float(result["amount"])
            won         = payout > 0

            state["total_bets"] += 1

            if won:
                profit = payout - amount
                state["total_profit"] += profit
                state["total_wins"]   += 1
                state["win_streak"]   += 1
                state["loss_streak"]   = 0
                log(f"  ✓ MENANG | Roll: {dice_result} | Payout: {payout:.8f} | "
                    f"Profit: +{profit:.8f}")

                # Reset win chance setiap menang
                if cfg["win_reset_win_chance"]:
                    state["win_chance"] = cfg["default_win_chance"]

            else:
                loss_amount = amount
                state["session_loss"] += loss_amount
                state["total_profit"] -= loss_amount
                state["total_losses"] += 1
                state["loss_streak"]  += 1
                state["win_streak"]    = 0
                log(f"  ✗ KALAH  | Roll: {dice_result} | Loss: -{loss_amount:.8f} | "
                    f"Session loss: {state['session_loss']:.8f}")

            # Reset win chance setiap 9 bet
            if cfg["every9_reset_chance"] and state["total_bets"] % 9 == 0:
                state["win_chance"] = cfg["default_win_chance"]
                log(f"  [RULE] Setiap 9 bet: reset win_chance → {cfg['default_win_chance']}%")

            # Terapkan semua aturan
            state = apply_rules(cfg, state)

            log(f"  Total P/L: {state['total_profit']:+.8f} | "
                f"Menang: {state['total_wins']} | Kalah: {state['total_losses']}")

            time.sleep(cfg["delay_ms"] / 1000.0)

        except KeyboardInterrupt:
            log("\n[STOP] Bot dihentikan oleh user.")
            log(f"Statistik akhir:")
            log(f"  Total Bet  : {state['total_bets']}")
            log(f"  Total Menang: {state['total_wins']}")
            log(f"  Total Kalah : {state['total_losses']}")
            log(f"  Total P/L   : {state['total_profit']:+.8f} {cfg['currency'].upper()}")
            sys.exit(0)

        except requests.exceptions.ConnectionError:
            log("[ERROR] Koneksi terputus. Coba lagi 10 detik...")
            time.sleep(10)

        except requests.exceptions.Timeout:
            log("[ERROR] Request timeout. Coba lagi 10 detik...")
            time.sleep(10)

        except Exception as e:
            log(f"[ERROR] {e}. Coba lagi 15 detik...")
            time.sleep(15)

if __name__ == "__main__":
    run_bot()
