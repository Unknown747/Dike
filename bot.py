#!/usr/bin/env python3
"""
DIKE - Stake.com Dice Auto Bet Bot (IDR)
Dioptimalkan dari hasil simulasi Monte Carlo
"""

import time, sys, uuid, os, requests
from datetime import datetime, date

# Session HTTP persisten — reuse koneksi TCP/TLS antar bet (lebih cepat)
_http = requests.Session()

# ═══════════════════════════════════════════════
#  WARNA TERMINAL (ANSI)
# ═══════════════════════════════════════════════

def _supports_color():
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_COLOR = _supports_color()

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _COLOR else text

def green(t):   return _c("92", t)
def red(t):     return _c("91", t)
def yellow(t):  return _c("93", t)
def cyan(t):    return _c("96", t)
def magenta(t): return _c("95", t)
def blue(t):    return _c("94", t)
def white(t):   return _c("97", t)
def bold(t):    return _c("1",  t)
def dim(t):     return _c("2",  t)

# ═══════════════════════════════════════════════
#  LOG KE FILE + TERMINAL
# ═══════════════════════════════════════════════

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dike.log")

LEVEL_COLOR = {
    "INFO":     white,
    "WIN":      green,
    "LOSS":     red,
    "WARN":     yellow,
    "ERROR":    red,
    "RECOVERY": magenta,
    "RELOAD":   cyan,
    "STAT":     blue,
    "RULE":     dim,
    "STOP":     yellow,
    "SALDO":    cyan,
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
    """Print langsung tanpa level tag — untuk header/box."""
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(_strip_ansi(line) + "\n")

# ═══════════════════════════════════════════════
#  BOX DRAWING
# ═══════════════════════════════════════════════

W = 62  # lebar box

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
    visible = len(_strip_ansi(inner))          # panjang visual, tanpa ANSI
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
    # Coba baca dari environment variable jika setting.txt belum diisi
    if not api_token or api_token == "MASUKKAN_TOKEN_API_ANDA_DISINI":
        api_token = os.environ.get("STAKE_API_TOKEN", "")
    if not api_token:
        log("API_TOKEN belum diset di setting.txt atau STAKE_API_TOKEN env var!", "ERROR")
        sys.exit(1)
    return {
        "api_token":            api_token,
        "currency":             cfg.get("CURRENCY", "idr").lower(),
        "base_bet":             float(cfg.get("BASE_BET", "100")),
        "delay_ms":             float(cfg.get("CUSTOM_DELAY_MS", "300")),
        "default_win_chance":   float(cfg.get("DEFAULT_WIN_CHANCE", "49.50")),
        "max_bet":              float(cfg.get("MAX_BET_IDR", "3500")),
        "min_balance":          float(cfg.get("MIN_BALANCE_IDR", "50000")),
        "ls3_increase_pct":     float(cfg.get("LOSS_STREAK_3_INCREASE_BET_PERCENT", "250")),
        "ls3_win_chance":       float(cfg.get("LOSS_STREAK_3_WIN_CHANCE", "92.00")),
        "ls4_win_chance":       float(cfg.get("LOSS_STREAK_4_WIN_CHANCE", "89.00")),
        "ls5_win_chance":       float(cfg.get("LOSS_STREAK_5_WIN_CHANCE", "94.01")),
        "ls6_increase_pct":     float(cfg.get("LOSS_STREAK_6_INCREASE_BET_PERCENT", "300")),
        "ls6_win_chance":       float(cfg.get("LOSS_STREAK_6_WIN_CHANCE", "93.00")),
        "win_every_3_reset":    cfg.get("WIN_EVERY_3_RESET_BET", "true").lower() == "true",
        "ws2_decrease_pct":     float(cfg.get("WIN_STREAK_2_DECREASE_BET_PERCENT", "70")),
        "ws4_win_chance":       float(cfg.get("WIN_STREAK_4_WIN_CHANCE", "70.00")),
        "ws6_win_chance":       float(cfg.get("WIN_STREAK_6_WIN_CHANCE", "65.00")),
        "win_reset_win_chance": cfg.get("WIN_RESET_WIN_CHANCE", "true").lower() == "true",
        "every9_reset_chance":  cfg.get("EVERY_9_BETS_RESET_WIN_CHANCE", "true").lower() == "true",
        "stop_loss":            float(cfg.get("STOP_LOSS_IDR", "2000")),
        "stop_loss_pause_min":  float(cfg.get("STOP_LOSS_PAUSE_MINUTES", "2")),
        "recovery_mode":        cfg.get("RECOVERY_MODE", "true").lower() == "true",
        "recovery_win_chance":  float(cfg.get("RECOVERY_WIN_CHANCE", "90.00")),
        "recovery_bet_mult":    float(cfg.get("RECOVERY_BET_MULTIPLIER", "1.0")),
        "recovery_exit_pct":    float(cfg.get("RECOVERY_EXIT_PCT", "80")),
        "recovery_min_deficit": float(cfg.get("RECOVERY_MIN_DEFICIT", "0")),
        "target_wager":         float(cfg.get("TARGET_WAGER_IDR", "0")),
    }

def check_hot_reload(cfg):
    global _last_mtime
    try:
        mtime = os.path.getmtime(SETTING_FILE)
        if mtime != _last_mtime:
            _last_mtime = mtime
            if _last_mtime != 0:
                log("⟳  setting.txt berubah — reload konfigurasi...", "RELOAD")
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
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Origin": "https://stake.com",
        "Referer": "https://stake.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "x-access-token": api_token,
        "x-language": "en",
        "apollographql-client-name": "web",
        "apollographql-client-version": "1.0.0",
        "Connection": "keep-alive",
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
            "amount": amount, "target": target,
            "condition": "above", "currency": currency,
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
    return {"date": str(date.today()), "bets": 0, "wins": 0, "losses": 0,
            "profit": 0.0, "biggest_win": 0.0, "biggest_loss": 0.0,
            "recovery_bets": 0, "recovery_profit": 0.0}

def print_daily_stats(stats):
    raw_print()
    box_top("STATISTIK HARIAN")
    box_row("Tanggal",         stats["date"],                     cyan)
    box_row("Total Bet",       f"{stats['bets']:,}",              white)
    box_row("Total Menang",    f"{stats['wins']:,}",              green)
    box_row("Total Kalah",     f"{stats['losses']:,}",            red)
    wr = stats["wins"] / stats["bets"] * 100 if stats["bets"] else 0
    wr_color = green if wr >= 50 else yellow
    box_row("Win Rate",        f"{wr:.2f}%",                      wr_color)
    sign   = "+" if stats["profit"] >= 0 else ""
    pcol   = green if stats["profit"] >= 0 else red
    box_row("Total P/L",       f"Rp {sign}{stats['profit']:,.0f}", pcol)
    box_row("Win Terbesar",    f"Rp +{stats['biggest_win']:,.0f}", green)
    box_row("Kalah Terbesar",  f"Rp -{stats['biggest_loss']:,.0f}", red)
    if stats["recovery_bets"] > 0:
        box_sep()
        rsign = "+" if stats["recovery_profit"] >= 0 else ""
        rcol  = green if stats["recovery_profit"] >= 0 else red
        box_row("Bet Recovery",       f"{stats['recovery_bets']:,}",             magenta)
        box_row("P/L saat Recovery",  f"Rp {rsign}{stats['recovery_profit']:,.0f}", rcol)
    box_bottom()
    raw_print()

# ═══════════════════════════════════════════════
#  ATURAN BETTING
# ═══════════════════════════════════════════════

def apply_rules(cfg, state):
    bet        = state["bet"]
    win_chance = state["win_chance"]
    ls, ws     = state["loss_streak"], state["win_streak"]

    if ls >= 6:
        bet        = bet * (1 + cfg["ls6_increase_pct"] / 100)
        win_chance = cfg["ls6_win_chance"]
        log(f"  ▲ Loss streak {ls}: bet +{cfg['ls6_increase_pct']:.0f}%  chance → {win_chance}%", "RULE")
    elif ls == 5:
        win_chance = cfg["ls5_win_chance"]
        log(f"  ▲ Loss streak {ls}: chance → {win_chance}%", "RULE")
    elif ls == 4:
        win_chance = cfg["ls4_win_chance"]
        log(f"  ▲ Loss streak {ls}: chance → {win_chance}%", "RULE")
    elif ls == 3:
        bet        = bet * (1 + cfg["ls3_increase_pct"] / 100)
        win_chance = cfg["ls3_win_chance"]
        log(f"  ▲ Loss streak {ls}: bet +{cfg['ls3_increase_pct']:.0f}%  chance → {win_chance}%", "RULE")

    if ws >= 6:
        win_chance = cfg["ws6_win_chance"]
        log(f"  ▼ Win streak {ws}: chance → {win_chance}%", "RULE")
    elif ws >= 4:
        win_chance = cfg["ws4_win_chance"]
        log(f"  ▼ Win streak {ws}: chance → {win_chance}%", "RULE")
    elif ws >= 2:
        bet = bet * (cfg["ws2_decrease_pct"] / 100)
        log(f"  ▼ Win streak {ws}: bet -{100 - cfg['ws2_decrease_pct']:.0f}%", "RULE")

    if cfg["win_every_3_reset"] and state["total_wins"] > 0 \
            and state["total_wins"] % 3 == 0 \
            and state.get("_last_reset_at") != state["total_wins"]:
        bet = cfg["base_bet"]
        state["_last_reset_at"] = state["total_wins"]
        log(f"  ↺ {state['total_wins']} menang → reset bet ke Rp {cfg['base_bet']:,.0f}", "RULE")

    if cfg["max_bet"] > 0 and bet > cfg["max_bet"]:
        log(f"  ⊘ Bet dikunci pada MAX Rp {cfg['max_bet']:,.0f}", "RULE")
        bet = cfg["max_bet"]

    state["bet"]        = max(round(bet), 1)
    state["win_chance"] = round(win_chance, 4)
    return state

# ═══════════════════════════════════════════════
#  TAMPILAN HEADER STARTUP
# ═══════════════════════════════════════════════

def print_startup_banner(cfg, user, balance):
    raw_print()
    box_top("DIKE  ·  Stake.com Dice Auto Bet")
    box_line(f"User   : {user['name']}  (ID: {user['id']})", cyan)
    box_line(f"Saldo  : Rp {balance:,.2f}  [{cfg['currency'].upper()}]", green)
    box_mid()
    box_row("Base Bet",      f"Rp {cfg['base_bet']:,.0f}",              white)
    box_row("Max Bet",       f"Rp {cfg['max_bet']:,.0f}",               yellow)
    box_row("Min Saldo",     f"Rp {cfg['min_balance']:,.0f}",           yellow)
    box_row("Win Chance",    f"{cfg['default_win_chance']}%",           cyan)
    box_row("Delay",         f"{cfg['delay_ms']:.0f} ms",               white)
    box_row("Stop Loss",     f"Rp {cfg['stop_loss']:,.0f}  "
                             f"(pause {cfg['stop_loss_pause_min']:.0f} mnt)", red)
    if cfg["target_wager"] > 0:
        box_row("Target Wager", f"Rp {cfg['target_wager']:,.0f}", magenta)
    box_sep()
    rec_status = green("AKTIF ✓") if cfg["recovery_mode"] else dim("nonaktif")
    box_row("Recovery Mode", rec_status if _COLOR else
            ("AKTIF" if cfg["recovery_mode"] else "nonaktif"), white)
    if cfg["recovery_mode"]:
        box_row("  ↳ Win Chance",  f"{cfg['recovery_win_chance']}%",        magenta)
        box_row("  ↳ Exit Saat",   f"Pulih {cfg['recovery_exit_pct']:.0f}%", magenta)
    box_bottom()
    raw_print()

# ═══════════════════════════════════════════════
#  TAMPILAN SETIAP BET  (1 baris per bet)
# ═══════════════════════════════════════════════

def print_result(n, recovery, won, roll, net, balance, total_profit, tw, tl):
    """Satu baris ringkas per bet: nomor · hasil · roll · profit · saldo · P/L · skor."""
    num   = dim(f"#{n:<5}")
    mode  = magenta("⟳ ") if recovery else "  "
    icon  = green("✦") if won else red("✗")
    roll_ = white(f"{roll:.2f}")
    net_s = green(f"+Rp {net:>9,.0f}") if won else red(f"-Rp {abs(net):>9,.0f}")
    bal_s = cyan(f"Rp {balance:>13,.0f}")
    sign  = "+" if total_profit >= 0 else ""
    pcol  = green if total_profit >= 0 else red
    pl_s  = pcol(f"P/L {sign}Rp {total_profit:,.0f}")
    score = dim(f"[M:{tw} K:{tl}]")
    raw_print(f"  {num}{mode}{icon}  {roll_}  {net_s}  {bal_s}  {pl_s}  {score}")

def print_recovery_progress(recovered, target):
    pct  = min(recovered / target * 100, 100) if target > 0 else 0
    bars = int(pct / 5)
    bar  = magenta("█" * bars) + dim("░" * (20 - bars))
    raw_print(
        f"  {dim('  ')} {magenta('⟳ RECOVERY')}  "
        f"[{bar}] {magenta(f'{pct:.1f}%')}  "
        f"Rp {recovered:,.0f} / Rp {target:,.0f}"
    )

def print_safety_stop(session_loss, deficit, pause_min):
    raw_print()
    raw_print(yellow(f"  ┌{'─'*46}┐"))
    raw_print(yellow(f"  │  ⛔  SAFETY STOP") + " " * 29 + yellow("│"))
    raw_print(yellow(f"  │  Loss sesi  : Rp {session_loss:>12,.0f}") +
              " " * max(0, 17 - len(f"{session_loss:,.0f}")) + yellow("│"))
    raw_print(yellow(f"  │  Total def  : Rp {deficit:>12,.0f}") +
              " " * max(0, 17 - len(f"{deficit:,.0f}")) + yellow("│"))
    raw_print(yellow(f"  │  Pause      : {pause_min:.0f} menit") +
              " " * max(0, 31 - len(f"{pause_min:.0f} menit")) + yellow("│"))
    raw_print(yellow(f"  └{'─'*46}┘"))
    raw_print()

def print_recovery_start(bet, chance, target):
    raw_print()
    raw_print(magenta(f"  ┌{'─'*46}┐"))
    raw_print(magenta(f"  │  ✦ RECOVERY MODE AKTIF") + " " * 23 + magenta("│"))
    raw_print(magenta(f"  │  Bet : Rp {bet:,}  ·  Chance : {chance}%") +
              " " * max(0, 46 - len(f"  Bet : Rp {bet:,}  ·  Chance : {chance}%") - 1) + magenta("│"))
    raw_print(magenta(f"  │  Target pulih : Rp {target:,.0f}") +
              " " * max(0, 46 - len(f"  Target pulih : Rp {target:,.0f}") - 1) + magenta("│"))
    raw_print(magenta(f"  └{'─'*46}┘"))
    raw_print()

def print_recovery_done(base_bet):
    raw_print()
    raw_print(green(f"  ┌{'─'*46}┐"))
    raw_print(green(f"  │  ✓  RECOVERY SELESAI") + " " * 24 + green("│"))
    raw_print(green(f"  │  Kembali normal  ·  Bet: Rp {base_bet:,}") +
              " " * max(0, 46 - len(f"  Kembali normal  ·  Bet: Rp {base_bet:,}") - 1) + green("│"))
    raw_print(green(f"  └{'─'*46}┘"))
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
    global _last_mtime
    _last_mtime = 0

    cfg = load_config()
    _last_mtime = os.path.getmtime(SETTING_FILE)

    # Verifikasi akun & saldo awal
    try:
        user    = get_user_info(cfg["api_token"])
        balance = get_balance(cfg["api_token"], cfg["currency"])
    except Exception as e:
        log(f"Gagal verifikasi akun: {e}", "ERROR")
        sys.exit(1)

    print_startup_banner(cfg, user, balance)

    state = {
        "bet":            cfg["base_bet"],
        "win_chance":     cfg["default_win_chance"],
        "loss_streak":    0,
        "win_streak":     0,
        "total_wins":     0,
        "total_losses":   0,
        "total_bets":     0,
        "session_loss":   0.0,
        "total_profit":   0.0,
        "total_wager":    0.0,
        "_last_reset_at": -1,
    }

    recovery_active  = False
    total_deficit    = 0.0
    recovered_amount = 0.0

    daily         = make_daily_stats()
    today         = date.today()
    balance_check = 0

    while True:
        try:
            # ── HOT RELOAD ──────────────────────────────
            cfg = check_hot_reload(cfg)

            # ── GANTI HARI ───────────────────────────────
            if date.today() != today:
                print_daily_stats(daily)
                daily = make_daily_stats()
                today = date.today()
                log(f"☀  Hari baru: {today}")

            # ── CEK SALDO SETIAP 50 BET (sinkronisasi) ───
            balance_check += 1
            if balance_check >= 50:
                balance_check = 0
                try:
                    balance = get_balance(cfg["api_token"], cfg["currency"])
                    if cfg["min_balance"] > 0 and balance < cfg["min_balance"]:
                        log(f"⛔ Saldo Rp {balance:,.0f} < batas Rp {cfg['min_balance']:,.0f}. Bot berhenti!", "WARN")
                        print_daily_stats(daily)
                        sys.exit(0)
                    if balance < state["bet"]:
                        log(f"⚠  Saldo tidak cukup, reset bet ke Rp {cfg['base_bet']:,.0f}", "WARN")
                        state["bet"] = cfg["base_bet"]
                except Exception as e:
                    log(f"Gagal cek saldo: {e}", "WARN")

            # ── SAFETY STOP (dilewati saat recovery aktif) ───────
            if not recovery_active and state["session_loss"] >= cfg["stop_loss"]:
                total_deficit += state["session_loss"]
                print_safety_stop(state["session_loss"], total_deficit, cfg["stop_loss_pause_min"])
                time.sleep(cfg["stop_loss_pause_min"] * 60)

                state["session_loss"] = 0.0
                state["loss_streak"]  = 0
                state["win_streak"]   = 0

                if cfg["recovery_mode"] and total_deficit > cfg["recovery_min_deficit"]:
                    recovery_active  = True
                    recovered_amount = 0.0
                    rec_bet = max(round(cfg["base_bet"] * cfg["recovery_bet_mult"]), 1)
                    state["bet"]        = rec_bet
                    state["win_chance"] = cfg["recovery_win_chance"]
                    target = total_deficit * cfg["recovery_exit_pct"] / 100
                    print_recovery_start(rec_bet, cfg["recovery_win_chance"], target)
                else:
                    state["bet"]        = cfg["base_bet"]
                    state["win_chance"] = cfg["default_win_chance"]

            # ── BET ──────────────────────────────────────
            current_bet    = int(state["bet"])
            current_chance = state["win_chance"]

            result = roll_dice(cfg["api_token"], current_bet, current_chance, cfg["currency"])

            dice_result = result["state"]["result"]
            payout      = float(result["payout"])
            amount      = float(result["amount"])
            won         = payout > 0
            net         = payout - amount   # +profit atau -loss

            balance    += net
            state["total_bets"]   += 1
            state["total_wager"]  += amount
            daily["bets"]         += 1

            if won:
                state["total_profit"] += net
                state["total_wins"]   += 1
                state["win_streak"]   += 1
                state["loss_streak"]   = 0
                daily["wins"]         += 1
                daily["profit"]       += net
                daily["biggest_win"]   = max(daily["biggest_win"], net)

                print_result(state["total_bets"], recovery_active, True,
                             dice_result, net, balance,
                             state["total_profit"], state["total_wins"], state["total_losses"])

                if recovery_active:
                    recovered_amount         += net
                    daily["recovery_bets"]   += 1
                    daily["recovery_profit"] += net
                    target = total_deficit * cfg["recovery_exit_pct"] / 100
                    print_recovery_progress(recovered_amount, target)

                    if recovered_amount >= target:
                        recovery_active       = False
                        total_deficit         = 0.0
                        recovered_amount      = 0.0
                        state["bet"]          = cfg["base_bet"]
                        state["win_chance"]   = cfg["default_win_chance"]
                        state["loss_streak"]  = 0
                        state["win_streak"]   = 0
                        state["session_loss"] = 0.0
                        print_recovery_done(cfg["base_bet"])
                else:
                    if cfg["win_reset_win_chance"]:
                        state["win_chance"] = cfg["default_win_chance"]

            else:
                state["session_loss"] += amount
                state["total_profit"] -= amount
                state["total_losses"] += 1
                state["loss_streak"]  += 1
                state["win_streak"]    = 0
                daily["losses"]       += 1
                daily["profit"]       -= amount
                daily["biggest_loss"]  = max(daily["biggest_loss"], amount)

                if recovery_active:
                    total_deficit            += amount
                    daily["recovery_bets"]   += 1
                    daily["recovery_profit"] -= amount

                print_result(state["total_bets"], recovery_active, False,
                             dice_result, net, balance,
                             state["total_profit"], state["total_wins"], state["total_losses"])

            # ── TARGET WAGER TERCAPAI ────────────────────
            if cfg["target_wager"] > 0 and state["total_wager"] >= cfg["target_wager"]:
                print_target_reached(state["total_wager"], cfg["target_wager"])
                log(f"🎯 Target wager Rp {cfg['target_wager']:,.0f} tercapai "
                    f"(total Rp {state['total_wager']:,.0f}). Bot berhenti.", "STOP")
                print_daily_stats(daily)
                sys.exit(0)

            # ── RESET SETIAP 9 BET ───────────────────────
            if not recovery_active and cfg["every9_reset_chance"] \
                    and state["total_bets"] % 9 == 0:
                state["win_chance"] = cfg["default_win_chance"]
                log(f"  ↺ Setiap 9 bet: reset chance → {cfg['default_win_chance']}%", "RULE")

            # ── TERAPKAN ATURAN ──────────────────────────
            if not recovery_active:
                state = apply_rules(cfg, state)

            time.sleep(cfg["delay_ms"] / 1000.0)

        except KeyboardInterrupt:
            raw_print()
            log("Bot dihentikan.", "STOP")
            print_daily_stats(daily)
            sys.exit(0)

        except RateLimitError:
            raw_print(f"  {yellow('  ↻ rate limit — tunggu 5 detik...')}")
            time.sleep(5)

        except requests.exceptions.ConnectionError:
            raw_print(f"  {yellow('  ↻ koneksi terputus — retry 10 detik...')}")
            time.sleep(10)
            # Resync saldo — hasil bet saat koneksi putus bisa ambigu
            try:
                balance = get_balance(cfg["api_token"], cfg["currency"])
            except Exception:
                pass

        except requests.exceptions.Timeout:
            raw_print(f"  {yellow('  ↻ timeout — retry 10 detik...')}")
            time.sleep(10)
            try:
                balance = get_balance(cfg["api_token"], cfg["currency"])
            except Exception:
                pass

        except Exception as e:
            raw_print(f"  {red(f'  ✖ error: {e} — retry 15 detik...')}")
            log(f"Error: {e}", "ERROR")
            time.sleep(15)

if __name__ == "__main__":
    run_bot()
