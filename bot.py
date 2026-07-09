#!/usr/bin/env python3
"""
DIKE - Stake.com Dice Auto Bet Bot (IDR)
Strategi:
  - Setiap MENANG : bet naik ON_WIN_INCREASE_PCT %
  - Setiap KALAH  : bot berhenti otomatis
"""

import time, sys, uuid, os, requests, random
from datetime import datetime, date

_http   = requests.Session()
DRY_RUN = "--dry-run" in sys.argv

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

LOG_FILE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dike.log")
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

def _rotate_log():
    """Pindahkan dike.log → dike.log.bak jika ukurannya >= 5 MB."""
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) >= LOG_MAX_BYTES:
            bak = LOG_FILE + ".bak"
            os.replace(LOG_FILE, bak)
            with open(LOG_FILE, "a") as f:
                f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [INFO] "
                        f"Log dirotasi — file lama disimpan ke dike.log.bak\n")
    except Exception:
        pass

LEVEL_COLOR = {
    "INFO":  white,
    "WIN":   green,
    "LOSS":  red,
    "WARN":  yellow,
    "ERROR": red,
    "RULE":  dim,
    "STOP":  yellow,
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
    if not api_token and not DRY_RUN:
        log("API_TOKEN belum diset di setting.txt atau env var STAKE_API_TOKEN!", "ERROR")
        sys.exit(1)
    if not api_token:
        api_token = "dry-run"
    d_min = max(0.0, float(cfg.get("DELAY_MIN_MS", "200")))
    d_max = max(0.0, float(cfg.get("DELAY_MAX_MS", "500")))
    if d_min > d_max:
        d_min, d_max = d_max, d_min
    return {
        "api_token"        : api_token,
        "currency"         : cfg.get("CURRENCY", "idr").lower(),
        "base_bet"         : float(cfg.get("BASE_BET", "100")),
        "delay_min_ms"     : d_min,
        "delay_max_ms"     : d_max,
        "win_chance"       : float(cfg.get("DEFAULT_WIN_CHANCE", "98.00")),
        "max_bet"          : float(cfg.get("MAX_BET_IDR", "5000")),
        "min_balance"      : float(cfg.get("MIN_BALANCE_IDR", "0")),
        "on_win_pct"       : float(cfg.get("ON_WIN_INCREASE_PCT", "15")),
        "stop_pause_sec"   : float(cfg.get("STOP_PAUSE_SECONDS", "10")),
        "stop_profit"      : float(cfg.get("STOP_PROFIT_IDR", "0")),
        "target_wager"     : float(cfg.get("TARGET_WAGER_IDR", "0")),
        "daily_loss_limit"       : float(cfg.get("DAILY_LOSS_LIMIT_IDR", "0")),
        "stop_loss_session"      : float(cfg.get("STOP_LOSS_SESSION_IDR", "0")),
        "loss_streak_threshold"  : int(float(cfg.get("LOSS_STREAK_THRESHOLD", "5"))),
        "loss_streak_extra_pause": float(cfg.get("LOSS_STREAK_EXTRA_PAUSE", "120")),
        "disable_colors"         : cfg.get("DISABLE_COLORS", "false").lower() == "true",
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
        "Content-Type"                : "application/json",
        "Accept"                      : "*/*",
        "Accept-Language"             : "en-US,en;q=0.9",
        "Accept-Encoding"             : "gzip, deflate",
        "Origin"                      : "https://stake.com",
        "Referer"                     : "https://stake.com/",
        "User-Agent"                  : (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "x-access-token"              : api_token,
        "x-language"                  : "en",
        "apollographql-client-name"   : "web",
        "apollographql-client-version": "1.0.0",
        "Connection"                  : "keep-alive",
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
    pass

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
#  STATISTIK SESI
# ═══════════════════════════════════════════════

def make_stats():
    return {
        "date"        : str(date.today()),
        "bets"        : 0,
        "wins"        : 0,
        "losses"      : 0,
        "profit"      : 0.0,
        "biggest_win" : 0.0,
        "loss_amount" : 0.0,
    }

def print_stats(stats, label="STATISTIK SESI"):
    raw_print()
    box_top(label)
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
    if stats["losses"] > 0:
        box_row("Kalah (berhenti)", f"Rp -{stats['loss_amount']:,.0f}", red)
    box_bottom()
    raw_print()

# ═══════════════════════════════════════════════
#  TAMPILAN STARTUP
# ═══════════════════════════════════════════════

def print_startup_banner(cfg, user, balance):
    raw_print()
    title = "DIKE  ·  DRY-RUN MODE" if DRY_RUN else "DIKE  ·  Stake.com Dice Auto Bet"
    box_top(title)
    if DRY_RUN:
        box_line("⚠  DRY-RUN — tidak ada bet nyata ke Stake.com", yellow)
        box_mid()
    box_line(f"User   : {user['name']}  (ID: {user['id']})", cyan)
    box_line(f"Saldo  : Rp {balance:,.2f}  [{cfg['currency'].upper()}]", green)
    box_mid()
    box_row("Base Bet",    f"Rp {cfg['base_bet']:,.0f}",                        white)
    box_row("Max Bet",     f"Rp {cfg['max_bet']:,.0f}",                         yellow)
    box_row("Win Chance",  f"{cfg['win_chance']}%",                             cyan)
    box_row("Saat Menang", f"Bet naik {cfg['on_win_pct']:.0f}%",                green)
    box_row("Saat Kalah",  f"Auto-restart ({cfg['stop_pause_sec']:.0f}s)",      red)
    if cfg["stop_profit"] > 0:
        box_row("Stop Profit",    f"Rp {cfg['stop_profit']:,.0f}",              green)
    if cfg["daily_loss_limit"] > 0:
        box_row("Daily Loss Limit", f"Rp {cfg['daily_loss_limit']:,.0f}",       red)
    if cfg["stop_loss_session"] > 0:
        box_row("Stop Loss Sesi", f"Rp {cfg['stop_loss_session']:,.0f} → jeda ekstra", yellow)
    if cfg["loss_streak_threshold"] > 0:
        box_row("Streak Protect", f"{cfg['loss_streak_threshold']}× kalah → +{cfg['loss_streak_extra_pause']:.0f}s", yellow)
    box_row("Cooldown",    f"{cfg['delay_min_ms']:.0f}–{cfg['delay_max_ms']:.0f} ms (acak)", white)
    if cfg["target_wager"] > 0:
        box_row("Target Wager", f"Rp {cfg['target_wager']:,.0f}",              blue)
    box_bottom()
    raw_print()

# ═══════════════════════════════════════════════
#  TAMPILAN TIAP BET
# ═══════════════════════════════════════════════

def print_result(n, won, roll, bet, net, balance, start_bal, total_wager, tw, tl,
                 daily_loss=0.0, daily_limit=0.0):
    num    = dim(f"#{n:<4}")
    icon   = green("WIN ") if won else red("LOSS")
    roll_  = white(f"{roll:>5.2f}")
    bet_s  = white(f"Bet:{bet:>7,}")
    wag_s  = dim(f"Wager:{total_wager:>10,.0f}")
    bal_s  = cyan(f"Saldo:{balance:>12,.0f}")
    diff   = balance - start_bal
    dsign  = "+" if diff >= 0 else ""
    dcol   = green if diff >= 0 else red
    diff_s = dcol(f"({dsign}{diff:,.0f})")
    score  = dim(f"W:{tw} K:{tl}")
    if daily_limit > 0:
        dl_pct = min(daily_loss / daily_limit * 100, 100)
        dl_col = red if dl_pct >= 80 else (yellow if dl_pct >= 50 else dim)
        dl_s   = dl_col(f"DL:{daily_loss:,.0f}/{daily_limit:,.0f}")
        raw_print(f"  {num} {icon}  {roll_}  {bet_s}  {wag_s}  {bal_s} {diff_s}  {score}  {dl_s}")
    else:
        raw_print(f"  {num} {icon}  {roll_}  {bet_s}  {wag_s}  {bal_s} {diff_s}  {score}")

def print_loss_stop(bet, loss_amount, pause_sec):
    raw_print()
    raw_print(red(f"  ┌{'─'*46}┐"))
    raw_print(red(f"  │  ⛔  KALAH — Bot berhenti") + " " * 20 + red("│"))
    raw_print(red(f"  │  Bet saat kalah : Rp {bet:>10,.0f}") +
              " " * max(0, 12 - len(f"{bet:,.0f}")) + red("│"))
    raw_print(red(f"  │  Kerugian       : Rp {loss_amount:>10,.0f}") +
              " " * max(0, 12 - len(f"{loss_amount:,.0f}")) + red("│"))
    raw_print(red(f"  │  Berhenti dalam {pause_sec:.0f} detik...") +
              " " * max(0, 27 - len(f"{pause_sec:.0f} detik...")) + red("│"))
    raw_print(red(f"  └{'─'*46}┘"))
    raw_print()

def _print_cumulative(cum, balance):
    sign = "+" if cum["total_profit"] >= 0 else ""
    pcol = green if cum["total_profit"] >= 0 else red
    raw_print(dim(f"  ── Kumulatif {cum['sessions']} sesi ──  "
                  f"Wager: Rp {cum['total_wager']:,.0f}  "
                  f"P/L: ") + pcol(f"Rp {sign}{cum['total_profit']:,.0f}") +
              dim(f"  Saldo: Rp {balance:,.0f}"))

def print_target_reached(total_wager, target):
    raw_print()
    raw_print(green(f"  ┌{'─'*46}┐"))
    raw_print(green(f"  │  🎯  TARGET WAGER TERCAPAI!") + " " * 18 + green("│"))
    raw_print(green(f"  │  Wager  : Rp {total_wager:>14,.0f}") +
              " " * max(0, 17 - len(f"{total_wager:,.0f}")) + green("│"))
    raw_print(green(f"  │  Target : Rp {target:>14,.0f}") +
              " " * max(0, 17 - len(f"{target:,.0f}")) + green("│"))
    raw_print(green(f"  └{'─'*46}┘"))
    raw_print()

# ═══════════════════════════════════════════════
#  DRY-RUN MODE — mock API tanpa bet nyata
# ═══════════════════════════════════════════════

if DRY_RUN:
    _dr_balance = {}

    def get_user_info(api_token):          # noqa: F811
        return {"id": "dry-run", "name": "DryRunUser",
                "balances": [{"available": {"amount": "1000000", "currency": "idr"}}]}

    def get_balance(api_token, currency):  # noqa: F811
        return _dr_balance.get(currency.lower(), 1_000_000.0)

    def roll_dice(api_token, amount, win_chance, currency):  # noqa: F811
        won = random.uniform(0, 100) < win_chance
        payout = round(amount * (99.0 / win_chance), 8) if won else 0.0
        return {
            "id"      : str(uuid.uuid4()),
            "amount"  : float(amount),
            "payout"  : payout,
            "currency": currency,
            "state"   : {
                "result"   : round(random.uniform(0, 100), 2),
                "target"   : round(100.0 - win_chance, 4),
                "condition": "above",
            },
        }

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

    try:
        user    = get_user_info(cfg["api_token"])
        balance = get_balance(cfg["api_token"], cfg["currency"])
    except Exception as e:
        log(f"Gagal verifikasi akun: {e}", "ERROR")
        sys.exit(1)

    print_startup_banner(cfg, user, balance)

    def new_session_state():
        return {
            "bet"          : cfg["base_bet"],
            "total_bets"   : 0,
            "total_wins"   : 0,
            "total_losses" : 0,
            "total_profit" : 0.0,
            "total_wager"  : 0.0,
        }

    state               = new_session_state()
    stats               = make_stats()
    session_start_bal   = balance   # saldo awal sesi pertama

    # Statistik kumulatif lintas sesi
    cum = {
        "sessions"    : 1,
        "total_wager" : 0.0,
        "total_profit": 0.0,
    }

    balance_check = 0
    loss_streak   = 0   # sesi kalah berturut-turut

    # Pelacak rugi harian
    daily_loss      = 0.0
    daily_date      = str(date.today())

    _rotate_log()

    while True:
        try:
            # ── HOT RELOAD ──────────────────────────────
            cfg = check_hot_reload(cfg)
            if cfg["disable_colors"]:
                _COLOR = False

            # ── RESET RUGI HARIAN JIKA HARI BARU ────────
            today = str(date.today())
            if today != daily_date:
                log(f"Hari baru ({today}) — reset daily loss counter.", "INFO")
                daily_loss = 0.0
                daily_date = today

            # ── CEK SALDO SETIAP 50 BET ──────────────────
            balance_check += 1
            if balance_check >= 50:
                balance_check = 0
                try:
                    balance = get_balance(cfg["api_token"], cfg["currency"])
                    if cfg["min_balance"] > 0 and balance < cfg["min_balance"]:
                        log(f"Saldo Rp {balance:,.0f} < batas Rp {cfg['min_balance']:,.0f}. Bot berhenti!", "WARN")
                        print_stats(stats)
                        sys.exit(0)
                except Exception as e:
                    log(f"Gagal cek saldo: {e}", "WARN")

            # ── HARD STOP: saldo < bet minimum efektif (200) → tidak bisa lanjut ─
            effective_min = max(cfg["base_bet"], 200)
            if balance < effective_min:
                log(f"Saldo Rp {balance:,.0f} < base bet Rp {cfg['base_bet']:,.0f}. Bot berhenti!", "WARN")
                cum["total_wager"]  += state["total_wager"]
                cum["total_profit"] += state["total_profit"]
                print_stats(stats)
                _print_cumulative(cum, balance)
                sys.exit(0)

            # ── BULATKAN KE KELIPATAN 200 TERDEKAT (half-up), MIN 200 ─
            state["bet"] = max(int(state["bet"] / 200 + 0.5) * 200, 200)
            # ── TERAPKAN MAX BET (floor ke kelipatan 200 ≤ max_bet) ──
            if cfg["max_bet"] > 0 and state["bet"] > cfg["max_bet"]:
                state["bet"] = max((int(cfg["max_bet"]) // 200) * 200, 200)
            # ── CLAMP AKHIR: bet tidak boleh melebihi saldo ──────────
            if state["bet"] > balance:
                # Floor ke kelipatan 200 ≤ balance
                floored = (int(balance) // 200) * 200
                if floored < 200:
                    log(f"Saldo Rp {balance:,.0f} tidak cukup untuk bet minimum Rp 200. Bot berhenti!", "WARN")
                    cum["total_wager"]  += state["total_wager"]
                    cum["total_profit"] += state["total_profit"]
                    print_stats(stats)
                    _print_cumulative(cum, balance)
                    sys.exit(0)
                log(f"Bet diclamp dari Rp {state['bet']:,} → Rp {floored:,} (sesuai saldo)", "WARN")
                state["bet"] = floored

            # ── BET ──────────────────────────────────────
            current_bet = int(state["bet"])
            result = roll_dice(cfg["api_token"], current_bet, cfg["win_chance"], cfg["currency"])

            dice_result = result["state"]["result"]
            payout      = float(result["payout"])
            amount      = float(result["amount"])
            won         = payout > 0
            net         = payout - amount

            balance              += net
            state["total_bets"]  += 1
            state["total_wager"] += amount
            stats["bets"]        += 1

            if won:
                state["total_profit"] += net
                state["total_wins"]   += 1
                stats["wins"]         += 1
                stats["profit"]       += net
                stats["biggest_win"]   = max(stats["biggest_win"], net)

                print_result(state["total_bets"], True, dice_result,
                             current_bet, net, balance, session_start_bal,
                             state["total_wager"],
                             state["total_wins"], state["total_losses"],
                             daily_loss, cfg["daily_loss_limit"])

                # Naikkan bet
                state["bet"] = current_bet * (1 + cfg["on_win_pct"] / 100)

            else:
                # ── KALAH → AUTO-RESTART ──────────────────
                state["total_profit"] -= amount
                state["total_losses"] += 1
                stats["losses"]       += 1
                stats["profit"]       -= amount
                stats["loss_amount"]   = amount
                daily_loss            += amount
                loss_streak           += 1
                # state["total_wager"] sudah mencakup losing bet (ditambah line di atas)
                cum["total_wager"]    += state["total_wager"]
                cum["total_profit"]   += state["total_profit"]

                # ── HITUNG JEDA (sebelum print agar pause_sec tampil benar) ──
                pause_sec = cfg["stop_pause_sec"]
                if cfg["loss_streak_threshold"] > 0 and loss_streak >= cfg["loss_streak_threshold"]:
                    pause_sec += cfg["loss_streak_extra_pause"]
                elif cfg["stop_loss_session"] > 0 and amount >= cfg["stop_loss_session"]:
                    pause_sec += cfg["stop_pause_sec"]   # double pause untuk bet besar

                print_result(state["total_bets"], False, dice_result,
                             current_bet, net, balance, session_start_bal,
                             state["total_wager"],
                             state["total_wins"], state["total_losses"],
                             daily_loss, cfg["daily_loss_limit"])

                print_loss_stop(current_bet, amount, pause_sec)
                print_stats(stats)
                _print_cumulative(cum, balance)

                # ── CEK DAILY LOSS LIMIT ──────────────────
                if cfg["daily_loss_limit"] > 0 and daily_loss >= cfg["daily_loss_limit"]:
                    log(f"Daily loss limit tercapai: Rp {daily_loss:,.0f} / Rp {cfg['daily_loss_limit']:,.0f} — bot berhenti hari ini!", "STOP")
                    sys.exit(0)

                # ── LOG STREAK / BIG LOSS ─────────────────
                if cfg["loss_streak_threshold"] > 0 and loss_streak >= cfg["loss_streak_threshold"]:
                    log(f"Streak kalah {loss_streak}× berturut — jeda ekstra {cfg['loss_streak_extra_pause']:.0f}s", "WARN")
                elif cfg["stop_loss_session"] > 0 and amount >= cfg["stop_loss_session"]:
                    log(f"Bet besar kalah Rp {amount:,.0f} — jeda tambahan {cfg['stop_pause_sec']:.0f}s", "WARN")

                # ── REFRESH SALDO DARI API ────────────────
                if not DRY_RUN:
                    try:
                        balance = get_balance(cfg["api_token"], cfg["currency"])
                    except Exception as e:
                        log(f"Gagal refresh saldo setelah kalah: {e}", "WARN")

                time.sleep(pause_sec)

                # Mulai sesi baru
                cum["sessions"] += 1
                state             = new_session_state()
                stats             = make_stats()
                session_start_bal = balance
                _rotate_log()
                log(f"Sesi #{cum['sessions']} dimulai.", "INFO")
                continue

            # ── STOP PROFIT TERCAPAI → AUTO-RESTART ──────
            if cfg["stop_profit"] > 0 and stats["profit"] >= cfg["stop_profit"]:
                cum["total_wager"]  += state["total_wager"]
                cum["total_profit"] += state["total_profit"]
                raw_print()
                log(f"Profit Rp {cfg['stop_profit']:,.0f} tercapai — sesi #{cum['sessions']} selesai.", "STOP")
                print_stats(stats, "STATISTIK SESI — PROFIT TARGET")
                _print_cumulative(cum, balance)
                time.sleep(cfg["stop_pause_sec"])

                cum["sessions"] += 1
                state             = new_session_state()
                stats             = make_stats()
                session_start_bal = balance
                loss_streak       = 0   # reset karena sesi berakhir profit
                _rotate_log()
                log(f"Sesi #{cum['sessions']} dimulai.", "INFO")
                continue

            # ── TARGET WAGER TERCAPAI → BERHENTI TOTAL ───
            if cfg["target_wager"] > 0 and cum["total_wager"] + state["total_wager"] >= cfg["target_wager"]:
                cum["total_wager"]  += state["total_wager"]
                cum["total_profit"] += state["total_profit"]
                print_target_reached(cum["total_wager"], cfg["target_wager"])
                print_stats(stats, "STATISTIK SESI TERAKHIR")
                _print_cumulative(cum, balance)
                sys.exit(0)

            delay_sec = random.uniform(cfg["delay_min_ms"], cfg["delay_max_ms"]) / 1000.0
            time.sleep(delay_sec)

        except KeyboardInterrupt:
            raw_print()
            log("Bot dihentikan oleh user.", "STOP")
            print_stats(stats)
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
