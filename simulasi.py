#!/usr/bin/env python3
"""
DIKE - Simulasi Strategi Berhenti Saat Kalah
  - Win chance : 98%
  - Setiap MENANG : bet naik 15% (maks Rp 5.000)
  - Saat KALAH    : sesi selesai (bot berhenti)
"""

import random

# ─────────────────────────────────────────────
#  SETTING (sama dengan setting.txt)
# ─────────────────────────────────────────────
CFG = {
    "base_bet"   : 200,
    "win_chance" : 65.00,
    "on_win_pct" : 15.0,
    "max_bet"    : 5000,
    "stop_profit": 500,   # berhenti jika profit sesi >= Rp 500
}

NUM_RUNS      = 50       # jumlah sesi simulasi
START_BALANCE = 500_000  # saldo awal virtual (Rp)

# ─────────────────────────────────────────────
#  SIMULASI SATU SESI
#  Sesi berakhir saat pertama kali KALAH
# ─────────────────────────────────────────────

def run_session(cfg, start_balance):
    bet     = float(cfg["base_bet"])
    balance = float(start_balance)
    profit  = 0.0
    wager   = 0.0
    wins    = 0

    while True:
        # Terapkan max bet
        if cfg["max_bet"] > 0:
            bet = min(bet, cfg["max_bet"])
        bet = max(round(bet), 1)
        current_bet = int(bet)

        if balance < current_bet:
            return dict(wins=wins, loss_bet=0, profit=profit,
                        wager=wager, balance=balance,
                        bankrupt=True, stop_reason="bankrupt")

        # Roll
        won = random.uniform(0, 100) > (100.0 - cfg["win_chance"])
        wager += current_bet

        if won:
            net      = current_bet * (99.0 / cfg["win_chance"]) - current_bet
            balance += net
            profit  += net
            wins    += 1
            bet      = current_bet * (1 + cfg["on_win_pct"] / 100)
            # Cek stop profit
            stop_p = cfg.get("stop_profit", 0)
            if stop_p > 0 and profit >= stop_p:
                return dict(wins=wins, loss_bet=0, profit=profit,
                            wager=wager, balance=balance,
                            bankrupt=False, stop_reason="profit")
        else:
            balance -= current_bet
            profit  -= current_bet
            return dict(wins=wins, loss_bet=current_bet, profit=profit,
                        wager=wager, balance=balance,
                        bankrupt=False, stop_reason="loss")

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def fmt_rp(v):
    sign = "+" if v >= 0 else ""
    return f"Rp {sign}{v:,.0f}"

def main():
    random.seed()

    # Hitung bet ke-N dari base 100 naik 15%
    bets_to_max = 0
    b = CFG["base_bet"]
    while b < CFG["max_bet"]:
        b *= (1 + CFG["on_win_pct"] / 100)
        bets_to_max += 1

    print()
    print("=" * 68)
    print("  DIKE — Simulasi: Berhenti Saat Kalah")
    print("=" * 68)
    print(f"  Win chance     : {CFG['win_chance']}%")
    print(f"  Base bet       : Rp {CFG['base_bet']:,}")
    print(f"  Naik tiap menang: {CFG['on_win_pct']:.0f}%  →  "
          f"capai Rp {CFG['max_bet']:,} setelah ±{bets_to_max} menang")
    print(f"  Saat kalah     : BERHENTI")
    print(f"  Stop profit    : Rp {CFG.get('stop_profit', 0):,}")
    print(f"  Saldo awal     : Rp {START_BALANCE:,}")
    print(f"  Jumlah sesi    : {NUM_RUNS}")
    print("=" * 68)

    print(f"\n  {'#':>3}  {'Menang':>7}  {'Bet saat kalah':>16}  "
          f"{'P/L sesi':>14}  {'Saldo':>13}  Ket")
    print("  " + "-" * 65)

    profits  = []
    wins_lst = []
    loss_bets = []
    bankrupts = 0
    balance  = START_BALANCE

    for i in range(1, NUM_RUNS + 1):
        r = run_session(CFG, balance)

        profits.append(r["profit"])
        wins_lst.append(r["wins"])
        if not r["bankrupt"] and r.get("stop_reason") == "loss":
            loss_bets.append(r["loss_bet"])

        balance = r["balance"]
        if r["bankrupt"]:
            bankrupts += 1

        stop_reason = r.get("stop_reason", "loss")
        if r["bankrupt"]:
            ket = "BANGKRUT"
        elif stop_reason == "profit":
            ket = "PROFIT ✓"
        else:
            ket = "LOSS"

        loss_str = f"Rp {r['loss_bet']:>6,.0f}" if stop_reason == "loss" else "       -  "
        pl_str   = fmt_rp(r["profit"])

        print(f"  {i:>3}  "
              f"{r['wins']:>7,}  "
              f"{loss_str:>16}  "
              f"{pl_str:>14}  "
              f"Rp {balance:>9,.0f}  "
              f"{ket}")

    # ── RINGKASAN ──────────────────────────────────────
    def avg(lst): return sum(lst) / len(lst) if lst else 0

    avg_wins    = avg(wins_lst)
    avg_profit  = avg(profits)
    avg_loss_bet = avg(loss_bets) if loss_bets else 0
    profitable  = sum(1 for p in profits if p > 0)
    total_profit = sum(profits)

    print()
    print("=" * 68)
    print("  RINGKASAN")
    print("-" * 68)
    print(f"  Rata-rata menang per sesi     : {avg_wins:.1f} bet")
    print(f"  Rata-rata bet saat kalah      : Rp {avg_loss_bet:,.0f}")
    print(f"  Rata-rata P/L per sesi        : {fmt_rp(avg_profit)}")
    print(f"  Total P/L kumulatif ({NUM_RUNS} sesi) : {fmt_rp(total_profit)}")
    print(f"  Saldo akhir                   : Rp {balance:,.0f}")
    print(f"  Sesi profit                   : {profitable}/{NUM_RUNS}")
    print(f"  Sesi bangkrut                 : {bankrupts}/{NUM_RUNS}")

    # ── ANALISIS PERTUMBUHAN BET ────────────────────────
    print()
    print("-" * 68)
    print("  PERTUMBUHAN BET (100 → maks 5.000 naik 15%/menang)")
    print("-" * 68)
    b = float(CFG["base_bet"])
    step = 0
    milestones = [500, 1000, 2000, 3000, 5000]
    m_idx = 0
    while m_idx < len(milestones) and b < CFG["max_bet"] * 1.01:
        if b >= milestones[m_idx]:
            print(f"  Menang ke-{step:>2}  →  Bet: Rp {round(b):>6,}")
            m_idx += 1
        b *= (1 + CFG["on_win_pct"] / 100)
        step += 1
    print(f"  Menang ke-{bets_to_max:>2}  →  Bet: Rp {CFG['max_bet']:>6,}  (MAX — tidak naik lagi)")

    # Estimasi profit jika menang terus sampai maks
    b2 = float(CFG["base_bet"])
    total_win_profit = 0.0
    for _ in range(bets_to_max + 1):
        bet_i = min(round(b2), CFG["max_bet"])
        total_win_profit += bet_i * (99.0 / CFG["win_chance"]) - bet_i
        b2 *= (1 + CFG["on_win_pct"] / 100)
    print()
    print(f"  Jika menang {bets_to_max} kali tanpa kalah:")
    print(f"    Total profit dari kemenangan  : Rp {total_win_profit:,.0f}")
    print(f"    Kerugian jika kalah di max bet: Rp {CFG['max_bet']:,}")
    net = total_win_profit - CFG["max_bet"]
    sign = "+" if net >= 0 else ""
    print(f"    NET satu siklus penuh         : Rp {sign}{net:,.0f}")

    print()
    print("=" * 68)
    print()

if __name__ == "__main__":
    main()
