#!/usr/bin/env python3
"""
DIKE - Simulasi Strategi On-Win / On-Loss
Strategi: win chance 98%, base bet Rp 100
  - Setiap MENANG : bet naik 15%
  - Setiap KALAH  : bet dobel (naik 100%)
  - Berhenti saat total kerugian sesi >= STOP_LOSS
"""

import random

# ─────────────────────────────────────────────
#  SETTING STRATEGI (harus sama dengan setting.txt)
# ─────────────────────────────────────────────
CFG = {
    "base_bet"       : 100,
    "win_chance"     : 98.00,
    "on_win_pct"     : 15.0,    # naik 15% tiap menang
    "on_loss_pct"    : 100.0,   # dobel tiap kalah
    "max_bet"        : 0,       # 0 = tidak ada batas
    "stop_loss"      : 5000,    # berhenti saat rugi >= Rp 5.000
}

# ─────────────────────────────────────────────
#  PARAMETER SIMULASI
# ─────────────────────────────────────────────
NUM_RUNS      = 30          # jumlah sesi simulasi
MAX_BETS      = 100_000     # batas bet per sesi (pengaman infinite loop)
START_BALANCE = 500_000     # saldo awal simulasi (Rp)

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def sim_roll(win_chance):
    """Simulasi satu dadu: return True jika menang."""
    return random.uniform(0, 100) > (100.0 - win_chance)

def calc_payout(bet, win_chance):
    """Payout bersih saat menang (Stake house edge ~1%)."""
    return bet * (99.0 / win_chance) - bet

def run_session(cfg, start_balance):
    """
    Jalankan satu sesi sampai stop_loss terpicu atau MAX_BETS habis.
    Return: dict statistik sesi.
    """
    bet          = float(cfg["base_bet"])
    balance      = float(start_balance)
    session_loss = 0.0
    total_profit = 0.0
    total_wager  = 0.0
    wins         = 0
    losses       = 0
    bets         = 0
    peak         = balance
    max_dd       = 0.0
    max_bet_seen = 0.0
    max_ls       = 0
    cur_ls       = 0
    stop_reason  = "stop_loss"

    while bets < MAX_BETS:
        # Preflight: bet tidak boleh melebihi saldo
        if bet > balance:
            bet = cfg["base_bet"]
        bet = max(round(bet), 1)

        # Max bet cap
        if cfg["max_bet"] > 0:
            bet = min(bet, cfg["max_bet"])

        max_bet_seen = max(max_bet_seen, bet)
        current_bet  = int(bet)

        if balance < current_bet:
            stop_reason = "bangkrut"
            break

        # Roll
        won = sim_roll(cfg["win_chance"])
        bets += 1

        if won:
            net           = calc_payout(current_bet, cfg["win_chance"])
            balance      += net
            total_profit += net
            total_wager  += current_bet
            session_loss  = max(0.0, session_loss - net)   # kurangi deficit jika menang
            wins         += 1
            cur_ls        = 0
            # Naik bet sesuai on_win_pct
            bet = current_bet * (1 + cfg["on_win_pct"] / 100)
        else:
            net           = -current_bet
            balance      += net
            total_profit += net
            total_wager  += current_bet
            session_loss += current_bet
            losses       += 1
            cur_ls       += 1
            max_ls        = max(max_ls, cur_ls)
            # Dobel bet sesuai on_loss_pct
            bet = current_bet * (1 + cfg["on_loss_pct"] / 100)

        peak   = max(peak, balance)
        max_dd = max(max_dd, peak - balance)

        # Cek stop loss
        if session_loss >= cfg["stop_loss"]:
            stop_reason = "stop_loss"
            break

    wr  = wins / bets * 100 if bets else 0
    roi = total_profit / total_wager * 100 if total_wager else 0

    return {
        "bets"        : bets,
        "wins"        : wins,
        "losses"      : losses,
        "win_rate"    : wr,
        "wager"       : total_wager,
        "profit"      : total_profit,
        "roi"         : roi,
        "balance"     : balance,
        "max_dd"      : max_dd,
        "max_ls"      : max_ls,
        "max_bet"     : max_bet_seen,
        "stop_reason" : stop_reason,
    }

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def avg(lst): return sum(lst) / len(lst) if lst else 0

def main():
    random.seed()

    print()
    print("=" * 68)
    print("  DIKE — Simulasi Strategi On-Win / On-Loss")
    print("=" * 68)
    print(f"  Saldo awal    : Rp {START_BALANCE:,}")
    print(f"  Jumlah sesi   : {NUM_RUNS}")
    print(f"  Base bet      : Rp {CFG['base_bet']:,}")
    print(f"  Win chance    : {CFG['win_chance']}%")
    print(f"  Saat menang   : bet naik {CFG['on_win_pct']:.0f}%")
    print(f"  Saat kalah    : bet naik {CFG['on_loss_pct']:.0f}% (dobel)")
    print(f"  Stop loss     : Rp {CFG['stop_loss']:,}")
    print("=" * 68)

    # Header tabel
    print(f"\n  {'#':>3}  {'Bet':>5}  {'Menang':>7}  {'Kalah':>7}  "
          f"{'Win%':>6}  {'P/L':>12}  {'Saldo':>12}  {'MaxDD':>10}  Stop")
    print("  " + "-" * 66)

    profits  = []
    wagers   = []
    ddowns   = []
    max_bets = []
    max_lss  = []
    stops    = {"stop_loss": 0, "bangkrut": 0, "limit": 0}

    for i in range(1, NUM_RUNS + 1):
        r = run_session(CFG, START_BALANCE)

        profits.append(r["profit"])
        wagers.append(r["wager"])
        ddowns.append(r["max_dd"])
        max_bets.append(r["max_bet"])
        max_lss.append(r["max_ls"])
        stops[r["stop_reason"] if r["stop_reason"] in stops else "limit"] += 1

        sign = "+" if r["profit"] >= 0 else ""
        stop_icon = {
            "stop_loss" : "STOP",
            "bangkrut"  : "BANGKRUT",
        }.get(r["stop_reason"], "LIMIT")

        print(f"  {i:>3}  "
              f"{r['bets']:>5,}  "
              f"{r['wins']:>7,}  "
              f"{r['losses']:>7,}  "
              f"{r['win_rate']:>5.1f}%  "
              f"Rp {sign}{r['profit']:>8,.0f}  "
              f"Rp {r['balance']:>8,.0f}  "
              f"Rp {r['max_dd']:>7,.0f}  "
              f"{stop_icon}")

    # ── RINGKASAN ──────────────────────────────────────────
    print()
    print("=" * 68)
    print("  RINGKASAN")
    print("-" * 68)

    profitable = sum(1 for p in profits if p >= 0)
    avg_pl     = avg(profits)
    avg_wr     = avg(wagers)
    avg_dd     = avg(ddowns)
    avg_mb     = avg(max_bets)
    avg_mls    = avg(max_lss)
    avg_roi    = avg_pl / avg_wr * 100 if avg_wr else 0

    sign = "+" if avg_pl >= 0 else ""

    print(f"  Rata-rata P/L        : Rp {sign}{avg_pl:,.0f}")
    print(f"  Rata-rata ROI        : {avg_roi:.4f}%")
    print(f"  Rata-rata Drawdown   : Rp {avg_dd:,.0f}")
    print(f"  Rata-rata Bet Max    : Rp {avg_mb:,.0f}")
    print(f"  Rata-rata Loss Streak: {avg_mls:.1f}")
    print(f"  Sesi profit          : {profitable}/{NUM_RUNS}")
    print(f"  Sesi bangkrut        : {stops['bangkrut']}/{NUM_RUNS}")
    print(f"  Sesi stop loss       : {stops['stop_loss']}/{NUM_RUNS}")

    # ── ESTIMASI SEBERAPA CEPAT STOP LOSS TERPICU ─────────
    print()
    print("-" * 68)
    print("  ANALISIS RISIKO")
    print("-" * 68)

    # Berapa bet rata-rata sebelum stop loss?
    avg_bets_per_session = avg([r["bets"] for r in
                                [run_session(CFG, START_BALANCE) for _ in range(10)]])
    delay_sec = 0.3
    est_menit = avg_bets_per_session * delay_sec / 60

    print(f"  Rata-rata durasi sesi     : ~{est_menit:.0f} menit "
          f"({avg_bets_per_session:.0f} bet @ {delay_sec*1000:.0f}ms delay)")

    # Worst case: berapa kalah berturut-turut sebelum saldo habis?
    # Base 100, dobel setiap kalah: 100→200→400→800→1600→3200→6400 > 5000 stop
    worst = []
    bet = CFG["base_bet"]
    total = 0
    n = 0
    while total < CFG["stop_loss"]:
        total += bet
        bet   *= 2
        n     += 1
    worst_ls = n

    print(f"  Kalah streak utk stop loss : {worst_ls} kali berturut-turut")
    print(f"  (100→200→400→...→stop jika total rugi >= Rp {CFG['stop_loss']:,})")
    print()
    print(f"  KESIMPULAN:")
    if profitable >= NUM_RUNS * 0.5:
        print(f"  Strategi menghasilkan profit di {profitable}/{NUM_RUNS} sesi ({profitable/NUM_RUNS*100:.0f}%).")
    else:
        print(f"  Strategi rugi di mayoritas sesi. House edge 98% win chance = "
              f"{99/98*100-100:.2f}% payout lebih rendah dari 1:1.")
    print(f"  Dengan stop loss Rp {CFG['stop_loss']:,}, risiko per sesi terbatas.")
    print("=" * 68)
    print()

if __name__ == "__main__":
    main()
