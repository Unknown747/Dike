#!/usr/bin/env python3
"""
DIKE - Stake.com Dice Auto Bet Bot (IDR)
Strategi: Simple On-Win / On-Loss
"""

import time, sys, uuid, os, requests
from datetime import datetime, date

# Session HTTP persisten
_http = requests.Session()

# ═══════════════════════════════════════════════
#  WARNA TERMINAL (ANSI)
# ═══════════════════════════════════════════════

def _supports_color():
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_COLOR = _supports_color()

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _COLOR else text

def green(t):  return _c("92", t)
def red(t):    return _c("91", t)
def yellow(t): return _c("93", t)
def cyan(t):   return _c("96", t)
def blue(t):   return _c("94", t)
def white(t):  return _c("97", t)
def bold(t):   return _c("1",  t)
def dim(t):    return _c("2",  t)

# ═══════════════════════════════════════════════
#  LOG KE FILE + TERMINAL
# ═══════════════════════════════════════════════

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dike.log")

LEVEL_COLOR = {
    "INFO":  white,
    "WIN":   green,
    "LOSS":  red,
    "WARN":  yellow,
    "ERROR": red,
    "RULE":  dim,
    "STOP":  yellow,
    "SALDO": cyan,
    "STAT":  blue,
}

import re as _re
_ANSI_RE = _re.compile(r"\033\[[0-9;]*m")

def _strip_ansi(text):
    return _ANSI_RE.sub("", text)

def log(msg, level="INFO"):
    now   = datetime.now()
    color = LEVEL_COLOR.get(level, white)
    tag   = f"[{now.strftime('%H:%M:%S')}]"
    print(f"{dim(tag)} {color(msg)}", flush=True)
    plain = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(plain + "\n")

def raw_print(line=""):
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(_strip_ansi(line) + "\n")

# ═══════════════════════════════════════════════
#  BOX DRAWING
# ═══════════════════════════════════════════════

W = 62

def box_top(title=""):
    if title:
        pad  = W - len(title) - 4
        l, r = pad // 2, pad - pad // 2
        line = f"╔{'═'*l}  {title}  {'═'*r}╗"
    else:
        line = f"╔{'═'*W}╗"
    raw_print(bold(cyan(line)))

def box_mid():
    raw_print(bold(cyan(f"╠{'═'*W}╣")))

def box_sep():
    raw_print(dim(cyan(f"║{'─'*W}║")))

def box_row(label, value, color_fn=white, width=W):
    inner   = f"  {label:<22}{value}"
    visible = len(_strip_ansi(inner))
    pad     = width - visible
    raw_print(bold(cyan("║")) + color_fn(inner) + " " * max(pad, 1) + bold(cyan("║")))

def box_bottom():
    raw_print(bold(cyan(f"╚{'═'*W}╝")))

def box_line(text="", color_fn=white):
    inner   = f"  {text}"
    visible = len(_strip_ansi(inner))
    pad     = W - visible
    raw_print(bold(cyan("║")) + color_fn(inner) + " " * max(pad, 1) + bold(cyan("║")))

# ═══════════════════════════════════════════════
#  BACA KONFIGURASI (HOT RELOAD)
# ═══════════════════════════════════════════════

SETTING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setting.txt")
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
        api_token = os.environ.get("STAKE_API_TOKEN", "")
    if not api_token:
        log("API_TOKEN belum diset di setting.txt atau env var STAKE_API_TOKEN!", "ERROR")
        sys.exit(1)
    return {
        "api_token"         : api_token,
        "currency"          : cfg.get("CURRENCY", "idr").lower(),
        "base_bet"          : float(cfg.get("BASE_BET", "100")),
        "delay_ms"          : float(cfg.get("CUSTOM_DELAY_MS", "300")),
        "win_chance"        : float(cfg.get("DEFAULT_WIN_CHANCE", "98.00")),
        "max_bet"           : float(cfg.get("MAX_BET_IDR", "0")),
        "min_balance"       : float(cfg.get("MIN_BALANCE_IDR", "0")),
        "on_win_pct"        : float(cfg.get("ON_WIN_INCREASE_PCT", "15")),
        "on_loss_pct"       : float(cfg.get("ON_LOSS_INCREASE_PCT", "100")),
        "stop_loss"         : float(cfg.get("STOP_LOSS_IDR", "5000")),
        "stop_loss_pause_sec": float(cfg.get("STOP_LOSS_PAUSE_SECONDS", "10")),
        "target_wager"      : float(cfg.get("TARGET_WAGER_IDR", "0")),
        "disable_colors"    : cfg.get("DISABLE_COLORS", "false").lower() == "true",
    }

def check_hot_reload(cfg):
    global _last_mtime
    try:
        mtime = os.path.getmtime(SETTING_FILE)
        if mtime != _last_mtime:
            _last_mtime = mtime
            if _last_mtime != 0:
                log("setting.txt berubah — reload konfigurasi...", "WARN")
            return load_config()
    except Exception as e:
        log(f"Gagal reload config: {e}", "WARN")
    return cfg

# ═══════════════════════════════════════════════
#  STAKE.COM GRAPHQL API
# ═══════════════════════════════════════════════

GRAPHQL_URL = "https://stake.com/_api/graphql"

DICE_ROLL_MUTATION = """
mutation DiceRoll($amount: Float!, $target: Float!, $condition: CasinoGameDiceConditionEnum!, $currency: CurrencyEnum!, $identifier: String!) {
  diceRoll(amount: $amount, target: $target, condition: $condition, currency: $currency, identifier: $identifier) {
    id
    amount
    payout
    currency
    state {
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
    return {
        "Content-Type"              : "application/json",
        "Accept"                    : "*/*",
        "Accept-Language"           : "en-US,en;q=0.9",
        "Accept-Encoding"           : "gzip, deflate",
        "Origin"                    : "https://stake.com",
        "Referer"                   : "https://stake.com/",
        "User-Agent"                : (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "x-access-token"            : api_token,
        "x-language"                : "en",
        "apollographql-client-name" : "web",
        "apollographql-client-version": "1.0.0",
        "Connection"                : "keep-alive",
    }

def get_user_info(api_token):
    resp = _http.post(GRAPHQL_URL, json={"query": USER_QUERY},
                      headers=make_headers(api_token), timeout=15)
    if not resp.ok:
        raise Exception(f"HTTP {resp.status_code}: {resp.text[:300]!r}")
    try:
        data = resp.json()
    except Exception:
        raise Exception(f"Respons bukan JSON (HTTP {resp.status_code}): {resp.text[:300]!r}")
    if "errors" in data:
        raise Exception(f"API Error: {data['errors']}")
    return data["data"]["user"]

def get_balance(api_token, currency):
    user = get_user_info(api_token)
    for bal in user["balances"]:
        if bal["available"]["currency"].lower() == currency:
            return float(bal["available"]["amount"])
    return 0.0

class RateLimitError(Exception):
    """Stake.com 'Please slow down' / parallelCasinoBet."""

def roll_dice(api_token, amount, win_chance, currency):
    target  = round(100.0 - win_chance, 4)
    payload = {
        "query": DICE_ROLL_MUTATION,
        "variables": {
            "amount"    : amount,
            "target"    : target,
            "condition" : "above",
            "currency"  : currency,
            "identifier": str(uuid.uuid4()),
        },
    }
    resp = _http.post(GRAPHQL_URL, json=payload,
                      headers=make_headers(api_token), timeout=15)
    if not resp.ok:
        raise Exception(f"HTTP {resp.status_code}: {resp.text[:400]!r}")
    try:
        data = resp.json()
    except Exception:
        raise Exception(f"Respons bukan JSON (HTTP {resp.status_code}): {resp.text[:300]!r}")
    if "errors" in data:
        errs     = data["errors"]
        messages = "; ".join(e.get("message", str(e)) for e in errs)
        err_type = errs[0].get("errorType", "") if errs else ""
        if err_type == "parallelCasinoBet" or "slow down" in messages.lower():
            raise RateLimitError(messages)
        raise Exception(f"API Error: {messages}")
    return data["data"]["diceRoll"]

# ═══════════════════════════════════════════════
#  STATISTIK HARIAN
# ═══════════════════════════════════════════════

def make_daily_stats():
    return {
        "date"       : str(date.today()),
        "bets"       : 0,
        "wins"       : 0,
        "losses"     : 0,
        "profit"     : 0.0,
        "biggest_win": 0.0,
        "biggest_loss": 0.0,
    }

def print_daily_stats(stats):
    raw_print()
    box_top("STATISTIK HARIAN")
    box_row("Tanggal",      stats["date"],                      cyan)
    box_row("Total Bet",    f"{stats['bets']:,}",               white)
    box_row("Menang",       f"{stats['wins']:,}",               green)
    box_row("Kalah",        f"{stats['losses']:,}",             red)
    wr = stats["wins"] / stats["bets"] * 100 if stats["bets"] else 0
    box_row("Win Rate",     f"{wr:.2f}%",                       green if wr >= 50 else yellow)
    sign = "+" if stats["profit"] >= 0 else ""
    pcol = green if stats["profit"] >= 0 else red
    box_row("Total P/L",    f"Rp {sign}{stats['profit']:,.0f}", pcol)
    box_row("Win Terbesar", f"Rp +{stats['biggest_win']:,.0f}", green)
    box_row("Kalah Terbesar",f"Rp -{stats['biggest_loss']:,.0f}", red)
    box_bottom()
    raw_print()

# ═══════════════════════════════════════════════
#  TAMPILAN STARTUP
# ═══════════════════════════════════════════════

def print_startup_banner(cfg, user, balance):
    raw_print()
    box_top("DIKE  ·  Stake.com Dice Auto Bet")
    box_line(f"User   : {user['name']}  (ID: {user['id']})", cyan)
    box_line(f"Saldo  : Rp {balance:,.2f}  [{cfg['currency'].upper()}]", green)
    box_mid()
    box_row("Base Bet",      f"Rp {cfg['base_bet']:,.0f}",        white)
    box_row("Win Chance",    f"{cfg['win_chance']}%",             cyan)
    box_row("Saat Menang",   f"Bet naik {cfg['on_win_pct']:.0f}%", green)
    box_row("Saat Kalah",    f"Bet naik {cfg['on_loss_pct']:.0f}% (dobel)", red)
    box_row("Stop Loss",     f"Rp {cfg['stop_loss']:,.0f}  "
                             f"(jeda {cfg['stop_loss_pause_sec']:.0f} detik)", yellow)
    if cfg["max_bet"] > 0:
        box_row("Max Bet",   f"Rp {cfg['max_bet']:,.0f}", yellow)
    if cfg["min_balance"] > 0:
        box_row("Min Saldo", f"Rp {cfg['min_balance']:,.0f}", yellow)
    if cfg["target_wager"] > 0:
        box_row("Target Wager", f"Rp {cfg['target_wager']:,.0f}", blue)
    box_row("Delay",         f"{cfg['delay_ms']:.0f} ms",         white)
    box_bottom()
    raw_print()

# ═══════════════════════════════════════════════
#  TAMPILAN TIAP BET
# ═══════════════════════════════════════════════

def print_result(n, won, roll, net, balance, total_profit, tw, tl):
    num   = dim(f"#{n:<5}")
    icon  = green("WIN ") if won else red("LOSS")
    roll_ = white(f"{roll:.2f}")
    net_s = green(f"+Rp {net:>9,.0f}") if won else red(f"-Rp {abs(net):>9,.0f}")
    bal_s = cyan(f"Rp {balance:>13,.0f}")
    sign  = "+" if total_profit >= 0 else ""
    pcol  = green if total_profit >= 0 else red
    pl_s  = pcol(f"P/L {sign}Rp {total_profit:,.0f}")
    score = dim(f"[M:{tw} K:{tl}]")
    raw_print(f"  {num} {icon}  {roll_}  {net_s}  {bal_s}  {pl_s}  {score}")

def print_stop(session_loss, pause_sec):
    raw_print()
    raw_print(yellow(f"  ┌{'─'*46}┐"))
    raw_print(yellow(f"  │  ⛔  BERHENTI SAAT KALAH") + " " * 21 + yellow("│"))
    raw_print(yellow(f"  │  Kerugian sesi : Rp {session_loss:>10,.0f}") +
              " " * max(0, 14 - len(f"{session_loss:,.0f}")) + yellow("│"))
    raw_print(yellow(f"  │  Berhenti dalam {pause_sec:.0f} detik...") +
              " " * max(0, 27 - len(f"{pause_sec:.0f} detik...")) + yellow("│"))
    raw_print(yellow(f"  └{'─'*46}┘"))
    raw_print()

def print_target_reached(total_wager, target):
    raw_print()
    raw_print(green(f"  ┌{'─'*46}┐"))
    raw_print(green(f"  │  🎯  TARGET WAGER TERCAPAI!") + " " * 18 + green("│"))
    raw_print(green(f"  │  Wager  : Rp {total_wager:>14,.0f}") +
              " " * max(0, 17 - len(f"{total_wager:,.0f}")) + green("│"))
    raw_print(green(f"  │  Target : Rp {target:>14,.0f}") +
              " " * max(0, 17 - len(f"{target:,.0f}")) + green("│"))
    raw_print(green(f"  │  Bot dihentikan otomatis.") + " " * 20 + green("│"))
    raw_print(green(f"  └{'─'*46}┘"))
    raw_print()

# ═══════════════════════════════════════════════
#  LOOP UTAMA
# ═══════════════════════════════════════════════

def run_bot():
    global _last_mtime, _COLOR
    _last_mtime = 0

    cfg = load_config()
    _last_mtime = os.path.getmtime(SETTING_FILE)

    if cfg["disable_colors"]:
        _COLOR = False

    # Verifikasi akun & saldo awal
    try:
        user    = get_user_info(cfg["api_token"])
        balance = get_balance(cfg["api_token"], cfg["currency"])
    except Exception as e:
        log(f"Gagal verifikasi akun: {e}", "ERROR")
        sys.exit(1)

    print_startup_banner(cfg, user, balance)

    state = {
        "bet"          : cfg["base_bet"],
        "total_bets"   : 0,
        "total_wins"   : 0,
        "total_losses" : 0,
        "session_loss" : 0.0,
        "total_profit" : 0.0,
        "total_wager"  : 0.0,
    }

    daily         = make_daily_stats()
    today         = date.today()
    balance_check = 0

    while True:
        try:
            # ── HOT RELOAD ──────────────────────────────
            cfg = check_hot_reload(cfg)
            if cfg["disable_colors"]:
                _COLOR = False

            # ── GANTI HARI ───────────────────────────────
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
                    if cfg["min_balance"] > 0 and balance < cfg["min_balance"]:
                        log(f"Saldo Rp {balance:,.0f} < batas Rp {cfg['min_balance']:,.0f}. Bot berhenti!", "WARN")
                        print_daily_stats(daily)
                        sys.exit(0)
                except Exception as e:
                    log(f"Gagal cek saldo: {e}", "WARN")

            # ── PREFLIGHT: pastikan bet tidak melebihi saldo ──
            if state["bet"] > balance and balance > 0:
                log(f"Bet Rp {round(state['bet']):,} > saldo Rp {balance:,.0f} → reset ke base", "WARN")
                state["bet"] = cfg["base_bet"]

            # Terapkan max bet dan bulatkan
            if cfg["max_bet"] > 0 and state["bet"] > cfg["max_bet"]:
                state["bet"] = cfg["max_bet"]
            state["bet"] = max(round(state["bet"]), 1)

            # ── BET ──────────────────────────────────────
            current_bet = int(state["bet"])
            result = roll_dice(cfg["api_token"], current_bet, cfg["win_chance"], cfg["currency"])

            dice_result = result["state"]["result"]
            payout      = float(result["payout"])
            amount      = float(result["amount"])
            won         = payout > 0
            net         = payout - amount

            balance               += net
            state["total_bets"]   += 1
            state["total_wager"]  += amount
            daily["bets"]         += 1

            if won:
                state["total_profit"] += net
                state["total_wins"]   += 1
                daily["wins"]         += 1
                daily["profit"]       += net
                daily["biggest_win"]   = max(daily["biggest_win"], net)

                # Naikkan bet saat menang
                state["bet"] = current_bet * (1 + cfg["on_win_pct"] / 100)

                print_result(state["total_bets"], True, dice_result, net,
                             balance, state["total_profit"],
                             state["total_wins"], state["total_losses"])

            else:
                state["total_profit"] -= amount
                state["total_losses"] += 1
                state["session_loss"] += amount
                daily["losses"]       += 1
                daily["profit"]       -= amount
                daily["biggest_loss"]  = max(daily["biggest_loss"], amount)

                # Dobel bet saat kalah
                state["bet"] = current_bet * (1 + cfg["on_loss_pct"] / 100)

                print_result(state["total_bets"], False, dice_result, net,
                             balance, state["total_profit"],
                             state["total_wins"], state["total_losses"])

            # ── BERHENTI SAAT KALAH ──────────────────────
            if state["session_loss"] >= cfg["stop_loss"]:
                print_stop(state["session_loss"], cfg["stop_loss_pause_sec"])
                print_daily_stats(daily)
                time.sleep(cfg["stop_loss_pause_sec"])
                log("Bot berhenti. Jalankan ulang jika ingin mulai sesi baru.", "STOP")
                sys.exit(0)

            # ── TARGET WAGER TERCAPAI ────────────────────
            if cfg["target_wager"] > 0 and state["total_wager"] >= cfg["target_wager"]:
                print_target_reached(state["total_wager"], cfg["target_wager"])
                print_daily_stats(daily)
                sys.exit(0)

            time.sleep(cfg["delay_ms"] / 1000.0)

        except KeyboardInterrupt:
            raw_print()
            log("Bot dihentikan oleh user.", "STOP")
            print_daily_stats(daily)
            sys.exit(0)

        except RateLimitError:
            raw_print(f"  {yellow('rate limit — tunggu 5 detik...')}")
            time.sleep(5)

        except requests.exceptions.ConnectionError:
            raw_print(f"  {yellow('koneksi terputus — retry 10 detik...')}")
            _http.close()
            time.sleep(10)
            try:
                balance = get_balance(cfg["api_token"], cfg["currency"])
            except Exception:
                pass

        except requests.exceptions.Timeout:
            raw_print(f"  {yellow('timeout — retry 10 detik...')}")
            time.sleep(10)
            try:
                balance = get_balance(cfg["api_token"], cfg["currency"])
            except Exception:
                pass

        except Exception as e:
            err_msg = str(e).lower()
            # Saldo tidak cukup → reset bet ke base sebelum retry
            if any(k in err_msg for k in ("insufficient", "amount", "balance", "funds")):
                log(f"Saldo tidak cukup — reset bet ke Rp {cfg['base_bet']:,.0f}", "WARN")
                state["bet"] = cfg["base_bet"]
                try:
                    balance = get_balance(cfg["api_token"], cfg["currency"])
                except Exception:
                    pass
                time.sleep(5)
            else:
                raw_print(f"  {red(f'error: {e} — retry 15 detik...')}")
                log(f"Error: {e}", "ERROR")
                time.sleep(15)

if __name__ == "__main__":
    run_bot()
