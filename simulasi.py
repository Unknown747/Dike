#!/usr/bin/env python3
"""
DIKE - Simulasi Strategi Dice Bot
Membaca konfigurasi dari setting.txt secara otomatis.

Penggunaan:
  python3 simulasi.py
  python3 simulasi.py --runs 100 --balance 1000000
  python3 simulasi.py --seed 42
  python3 simulasi.py --seed 42 --output hasil.csv
"""

import random, sys, os, csv, argparse

# Import parser konfigurasi dari bot.py (tidak menjalankan bot)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bot import parse_setting, SETTING_FILE

# ─────────────────────────────────────────────
#  ARGPARSE
# ─────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="DIKE — Simulasi strategi dice bot")
    p.add_argument("--runs",    type=int,   default=50,
                   help="Jumlah sesi simulasi (default: 50)")
    p.add_argument("--balance", type=float, default=500_000,
                   help="Saldo awal virtual IDR (default: 500000)")
    p.add_argument("--seed",    type=int,   default=None,
                   help="Seed random untuk hasil reproducible (default: acak)")
    p.add_argument("--output",  type=str,   default=None,
                   help="Simpan hasil ke file CSV, contoh: hasil.csv")
    return p.parse_args()

# ─────────────────────────────────────────────
#  BACA SETTING DARI setting.txt
# ─────────────────────────────────────────────
def load_sim_cfg():
    raw = parse_setting(SETTING_FILE)
    return {
        "base_bet"        : float(raw.get("BASE_BET", "200")),
        "win_chance"      : float(raw.get("DEFAULT_WIN_CHANCE", "98.00")),
        "on_win_pct"      : float(raw.get("ON_WIN_INCREASE_PCT", "15")),
        "on_loss_pct"     : float(raw.get("ON_LOSS_INCREASE_PCT", "0")),
        "max_bet"         : float(raw.get("MAX_BET_IDR", "5000")),
        "stop_profit"     : float(raw.get("STOP_PROFIT_IDR", "0")),
        "daily_loss_limit": float(raw.get("DAILY_LOSS_LIMIT_IDR", "0")),
    }

# ─────────────────────────────────────────────
#  ROUNDING — identik dengan bot.py
# ─────────────────────────────────────────────
def round_bet(bet, max_bet, balance):
    """Bulatkan ke kelipatan 200 (half-up), terapkan max_bet, clamp ke saldo."""
    bet = max(int(bet / 200 + 0.5) * 200, 200)
    if max_bet > 0 and bet > max_bet:
        bet = max((int(max_bet) // 200) * 200, 200)
    if bet > balance:
        bet = (int(balance) // 200) * 200
    return int(bet)

# ─────────────────────────────────────────────
#  SIMULASI SATU SESI
# ─────────────────────────────────────────────
def run_session(cfg, start_balance):
    """
    Satu sesi berakhir saat:
    - Martingale mode (on_loss_pct > 0): bet menyentuh max_bet → sesi berakhir
    - Normal mode (on_loss_pct = 0): pertama kali kalah → sesi berakhir
    - Stop profit tercapai
    - Bankrupt (saldo < 200)

    Payout: bet × (99 / win_chance) — standar Stake dice (house edge 1%).
    """
    bet        = float(cfg["base_bet"])
    balance    = float(start_balance)
    profit     = 0.0
    wager      = 0.0
    wins       = 0
    losses     = 0
    total_lost = 0.0  # sum of all losing bet amounts this session

    while True:
        current_bet = round_bet(bet, cfg["max_bet"], balance)

        if current_bet < 200 or balance < 200:
            return dict(wins=wins, losses=losses, loss_bet=0, profit=profit,
                        wager=wager, balance=balance, total_lost=total_lost,
                        stop_reason="bankrupt")

        # Stake dice payout: multiplier = 99 / win_chance (house edge 1%)
        won = random.uniform(0, 100) < cfg["win_chance"]
        wager += current_bet

        if won:
            net      = current_bet * (99.0 / cfg["win_chance"]) - current_bet
            balance += net
            profit  += net
            wins    += 1
            bet      = current_bet * (1 + cfg["on_win_pct"] / 100)
            if cfg["stop_profit"] > 0 and profit >= cfg["stop_profit"]:
                return dict(wins=wins, losses=losses, loss_bet=0, profit=profit,
                            wager=wager, balance=balance, total_lost=total_lost,
                            stop_reason="profit")
        else:
            balance    -= current_bet
            profit     -= current_bet
            losses     += 1
            total_lost += current_bet

            if cfg["on_loss_pct"] > 0 and cfg["max_bet"] > 0:
                # Martingale: naik bet, lanjut sesi
                new_bet = max(int(current_bet * (1 + cfg["on_loss_pct"] / 100) / 200 + 0.5) * 200, 200)
                if new_bet > cfg["max_bet"]:
                    new_bet = max((int(cfg["max_bet"]) // 200) * 200, 200)

                if new_bet >= cfg["max_bet"]:
                    # Bet menyentuh max → akhiri sesi
                    return dict(wins=wins, losses=losses, loss_bet=current_bet,
                                profit=profit, wager=wager, balance=balance,
                                total_lost=total_lost, stop_reason="max_bet")
                else:
                    bet = float(new_bet)
                    # Lanjut sesi dengan bet yang naik
            else:
                # Mode normal: stop saat pertama kalah
                return dict(wins=wins, losses=losses, loss_bet=current_bet,
                            profit=profit, wager=wager, balance=balance,
                            total_lost=total_lost, stop_reason="loss")

# ─────────────────────────────────────────────
#  HELPER
# ─────────────────────────────────────────────
def fmt_rp(v):
    sign = "+" if v >= 0 else ""
    return f"Rp {sign}{v:,.0f}"

def avg(lst):
    return sum(lst) / len(lst) if lst else 0.0

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    args = parse_args()
    random.seed(args.seed)

    cfg           = load_sim_cfg()
    NUM_RUNS      = args.runs
    START_BALANCE = args.balance

    # Hitung berapa kemenangan agar bet capai MAX
    bets_to_max = 0
    b = cfg["base_bet"]
    while b < cfg["max_bet"]:
        b *= (1 + cfg["on_win_pct"] / 100)
        bets_to_max += 1

    seed_str = f"seed={args.seed}" if args.seed is not None else "seed=acak"

    print()
    print("=" * 72)
    print("  DIKE — Simulasi: Auto-restart Berhenti Saat Kalah")
    print("=" * 72)
    print(f"  Konfigurasi     : {SETTING_FILE}")
    print(f"  Win chance      : {cfg['win_chance']}%")
    print(f"  Base bet        : Rp {cfg['base_bet']:,.0f}  (dibulatkan ke kelipatan 200)")
    print(f"  Naik tiap menang: +{cfg['on_win_pct']:.0f}%  →  "
          f"capai Rp {cfg['max_bet']:,.0f} setelah ±{bets_to_max} menang")
    if cfg["on_loss_pct"] > 0:
        print(f"  Saat kalah      : Naik {cfg['on_loss_pct']:.0f}% (martingale) → berhenti di max bet Rp {cfg['max_bet']:,.0f}")
    else:
        print(f"  Saat kalah      : AUTO-RESTART")
    if cfg["stop_profit"] > 0:
        print(f"  Stop profit     : Rp {cfg['stop_profit']:,.0f}  (lalu restart)")
    if cfg["daily_loss_limit"] > 0:
        print(f"  Daily loss limit: Rp {cfg['daily_loss_limit']:,.0f}")
    print(f"  Saldo awal      : Rp {START_BALANCE:,.0f}")
    print(f"  Jumlah sesi     : {NUM_RUNS}  ({seed_str})")
    print("=" * 72)

    show_dl = cfg["daily_loss_limit"] > 0
    if show_dl:
        print(f"\n  {'#':>3}  {'Menang':>7}  {'Bet saat kalah':>16}  "
              f"{'P/L sesi':>14}  {'Saldo':>13}  {'Daily Loss':>14}  Ket")
        print("  " + "-" * 83)
    else:
        print(f"\n  {'#':>3}  {'Menang':>7}  {'Bet saat kalah':>16}  "
              f"{'P/L sesi':>14}  {'Saldo':>13}  Ket")
        print("  " + "-" * 68)

    profits      = []
    wins_lst     = []
    loss_bets    = []
    bankrupts    = 0
    balance      = START_BALANCE
    daily_loss   = 0.0
    daily_hit    = False
    csv_rows     = []

    for i in range(1, NUM_RUNS + 1):
        if daily_hit:
            break

        r = run_session(cfg, balance)

        profits.append(r["profit"])
        wins_lst.append(r["wins"])
        if r["stop_reason"] in ("loss", "max_bet", "bankrupt"):
            if r["loss_bet"] > 0:
                loss_bets.append(r["loss_bet"])
            daily_loss += r.get("total_lost", r["loss_bet"])
        if r["stop_reason"] == "bankrupt":
            bankrupts += 1

        balance = r["balance"]

        ket_map  = {
            "bankrupt": "BANGKRUT",
            "profit"  : "PROFIT ✓",
            "loss"    : "LOSS",
            "max_bet" : "MAX BET ⛔",
        }
        ket      = ket_map.get(r["stop_reason"], "?")
        loss_str = f"Rp {r['loss_bet']:>6,.0f}" if r["stop_reason"] in ("loss", "max_bet") else "       -  "
        pl_str   = fmt_rp(r["profit"])

        if show_dl:
            dl_pct = min(daily_loss / cfg["daily_loss_limit"] * 100, 100) if cfg["daily_loss_limit"] > 0 else 0
            dl_flag = " ⚠" if dl_pct >= 80 else ""
            dl_str  = f"Rp {daily_loss:>8,.0f}{dl_flag}"
            print(f"  {i:>3}  {r['wins']:>7,}  {loss_str:>16}  "
                  f"{pl_str:>14}  Rp {balance:>9,.0f}  {dl_str:>14}  {ket}")
        else:
            print(f"  {i:>3}  {r['wins']:>7,}  {loss_str:>16}  "
                  f"{pl_str:>14}  Rp {balance:>9,.0f}  {ket}")

        csv_rows.append({
            "sesi"      : i,
            "menang"    : r["wins"],
            "bet_kalah" : r["loss_bet"],
            "profit"    : round(r["profit"], 2),
            "saldo"     : round(balance, 2),
            "daily_loss": round(daily_loss, 2),
            "keterangan": ket,
        })

        if cfg["daily_loss_limit"] > 0 and daily_loss >= cfg["daily_loss_limit"]:
            print(f"\n  ⛔  Daily loss limit Rp {cfg['daily_loss_limit']:,.0f} tercapai "
                  f"pada sesi #{i} — simulasi dihentikan.")
            daily_hit = True

    actual = len(profits)
    profitable = sum(1 for p in profits if p > 0)
    total_profit = sum(profits)

    # ── RINGKASAN ──────────────────────────────────
    print()
    print("=" * 72)
    print("  RINGKASAN")
    print("-" * 72)
    print(f"  Sesi dijalankan               : {actual}")
    print(f"  Rata-rata menang per sesi     : {avg(wins_lst):.1f} bet")
    if loss_bets:
        print(f"  Rata-rata bet saat kalah      : Rp {avg(loss_bets):,.0f}")
    print(f"  Rata-rata P/L per sesi        : {fmt_rp(avg(profits))}")
    print(f"  Total P/L kumulatif           : {fmt_rp(total_profit)}")
    print(f"  Saldo akhir                   : Rp {balance:,.0f}")
    print(f"  Sesi profit / total           : {profitable}/{actual}")
    print(f"  Sesi bangkrut                 : {bankrupts}/{actual}")
    if cfg["daily_loss_limit"] > 0:
        status = "LIMIT TERCAPAI" if daily_hit else "dalam limit"
        print(f"  Total rugi harian             : Rp {daily_loss:,.0f}  ({status})")

    # ── PERTUMBUHAN BET ────────────────────────────
    print()
    print("-" * 72)
    print(f"  PERTUMBUHAN BET  "
          f"(Rp {cfg['base_bet']:,.0f} → max Rp {cfg['max_bet']:,.0f}  naik {cfg['on_win_pct']:.0f}%/menang)")
    print("-" * 72)
    b     = float(cfg["base_bet"])
    step  = 0
    milestones = [m for m in [500, 1000, 2000, 3000, 5000, 10000] if cfg["base_bet"] < m <= cfg["max_bet"]]
    m_idx = 0
    while m_idx < len(milestones) and b < cfg["max_bet"] * 1.01:
        if b >= milestones[m_idx]:
            rounded = round_bet(b, cfg["max_bet"], 999_999_999)
            print(f"  Menang ke-{step:>2}  →  Bet: Rp {rounded:>8,}")
            m_idx += 1
        b *= (1 + cfg["on_win_pct"] / 100)
        step += 1
    print(f"  Menang ke-{bets_to_max:>2}  →  Bet: Rp {cfg['max_bet']:>8,.0f}  (MAX)")

    # Estimasi NET satu siklus penuh
    b2 = float(cfg["base_bet"])
    total_win_profit = 0.0
    for _ in range(bets_to_max + 1):
        bet_i = round_bet(b2, cfg["max_bet"], 999_999_999)
        if bet_i < 200:
            break
        total_win_profit += bet_i * (99.0 / cfg["win_chance"]) - bet_i
        b2 *= (1 + cfg["on_win_pct"] / 100)
    net  = total_win_profit - cfg["max_bet"]
    sign = "+" if net >= 0 else ""
    print()
    print(f"  Jika menang {bets_to_max} kali tanpa kalah:")
    print(f"    Profit total dari kemenangan  : Rp {total_win_profit:,.0f}")
    print(f"    Kerugian jika kalah di max bet: Rp {cfg['max_bet']:,.0f}")
    print(f"    NET satu siklus penuh         : Rp {sign}{net:,.0f}")

    print()
    print("=" * 72)
    print()

    # ── CSV EXPORT ──────────────────────────────────
    if args.output and csv_rows:
        try:
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
                writer.writeheader()
                writer.writerows(csv_rows)
            print(f"  ✓ Hasil disimpan ke: {args.output}")
            print()
        except Exception as e:
            print(f"  ✗ Gagal simpan CSV: {e}")

if __name__ == "__main__":
    main()
