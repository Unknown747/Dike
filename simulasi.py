#!/usr/bin/env python3
"""
DIKE - Simulasi Monte Carlo Strategi Dice
Mensimulasikan ribuan bet tanpa modal asli untuk mengukur efektivitas wager
"""

import random
import sys

# ─────────────────────────────────────────────
#  KONFIGURASI SIMULASI (sesuai setting.txt)
# ─────────────────────────────────────────────

CFG = {
    "base_bet":           100,       # IDR
    "default_win_chance": 49.50,     # %
    "delay_ms":           300,

    # Loss streak
    "ls3_increase_pct":   250.0,
    "ls3_win_chance":     92.00,
    "ls4_win_chance":     89.00,
    "ls5_win_chance":     94.01,
    "ls6_increase_pct":   300.0,
    "ls6_win_chance":     93.00,

    # Win streak
    "win_every_3_reset":  True,
    "ws2_decrease_pct":   70.0,
    "ws4_win_chance":     70.00,
    "ws6_win_chance":     65.00,

    # Reset
    "win_reset_win_chance": True,
    "every9_reset_chance":  True,

    # Safety stop
    "stop_loss":          5000,      # IDR
    "stop_loss_pause":    True,      # simulasikan reset setelah pause

    # Batas simulasi
    "max_bet":            0,         # 0 = bebas
    "start_balance":      100_000,   # saldo awal simulasi (IDR)
}

HOUSE_EDGE   = 0.01   # Stake.com house edge 1%
NUM_RUNS     = 5      # jumlah sesi simulasi
BETS_PER_RUN = 10_000 # bet per sesi

# ─────────────────────────────────────────────
#  SIMULASI SATU BET
# ─────────────────────────────────────────────

def simulate_bet(bet, win_chance):
    """
    Simulasi 1 bet dice.
    Menang: payout = bet * (99 / win_chance) - bet
    Kalah : loss   = bet
    """
    roll = random.uniform(0, 100)
    won  = roll > (100 - win_chance)   # condition: above

    if won:
        multiplier = 99.0 / win_chance
        payout     = bet * multiplier
        profit     = payout - bet
        return True, profit
    else:
        return False, -bet

# ─────────────────────────────────────────────
#  TERAPKAN ATURAN
# ─────────────────────────────────────────────

def apply_rules(cfg, state):
    bet        = state["bet"]
    win_chance = state["win_chance"]
    ls         = state["loss_streak"]
    ws         = state["win_streak"]

    if ls >= 6:
        bet        = bet * (1 + cfg["ls6_increase_pct"] / 100)
        win_chance = cfg["ls6_win_chance"]
    elif ls == 5:
        win_chance = cfg["ls5_win_chance"]
    elif ls == 4:
        win_chance = cfg["ls4_win_chance"]
    elif ls == 3:
        bet        = bet * (1 + cfg["ls3_increase_pct"] / 100)
        win_chance = cfg["ls3_win_chance"]

    if ws >= 6:
        win_chance = cfg["ws6_win_chance"]
    elif ws >= 4:
        win_chance = cfg["ws4_win_chance"]
    elif ws >= 2:
        bet = bet * (cfg["ws2_decrease_pct"] / 100)

    if cfg["win_every_3_reset"] and state["total_wins"] > 0 \
            and state["total_wins"] % 3 == 0 \
            and state.get("_last_reset_at") != state["total_wins"]:
        bet = cfg["base_bet"]
        state["_last_reset_at"] = state["total_wins"]

    if cfg["max_bet"] > 0:
        bet = min(bet, cfg["max_bet"])

    state["bet"]        = max(round(bet), 1)
    state["win_chance"] = round(win_chance, 4)
    return state

# ─────────────────────────────────────────────
#  SATU SESI SIMULASI
# ─────────────────────────────────────────────

def run_session(cfg, num_bets, start_balance, label=""):
    state = {
        "bet":            cfg["base_bet"],
        "win_chance":     cfg["default_win_chance"],
        "loss_streak":    0,
        "win_streak":     0,
        "total_wins":     0,
        "total_losses":   0,
        "total_bets":     0,
        "session_loss":   0.0,
        "_last_reset_at": -1,
    }

    balance       = start_balance
    total_wager   = 0.0
    total_profit  = 0.0
    max_drawdown  = 0.0
    peak_balance  = start_balance
    safety_stops  = 0
    max_loss_streak = 0
    max_win_streak  = 0
    max_single_bet  = 0
    bankrupt        = False

    for _ in range(num_bets):
        # Safety stop
        if state["session_loss"] >= cfg["stop_loss"]:
            safety_stops        += 1
            state["session_loss"] = 0.0
            state["bet"]          = cfg["base_bet"]
            state["win_chance"]   = cfg["default_win_chance"]
            state["loss_streak"]  = 0
            state["win_streak"]   = 0

        current_bet = int(state["bet"])

        # Cek saldo
        if balance < current_bet:
            bankrupt = True
            break

        max_single_bet  = max(max_single_bet, current_bet)
        total_wager    += current_bet
        state["total_bets"] += 1

        won, result = simulate_bet(current_bet, state["win_chance"])

        if won:
            balance               += result
            total_profit          += result
            state["total_wins"]   += 1
            state["win_streak"]   += 1
            state["loss_streak"]   = 0
            max_win_streak         = max(max_win_streak, state["win_streak"])
            if cfg["win_reset_win_chance"]:
                state["win_chance"] = cfg["default_win_chance"]
        else:
            balance                += result   # result negatif
            total_profit           += result
            state["session_loss"]  -= result   # result negatif → tambah loss
            state["total_losses"]  += 1
            state["loss_streak"]   += 1
            state["win_streak"]     = 0
            max_loss_streak         = max(max_loss_streak, state["loss_streak"])

        # Drawdown
        if balance > peak_balance:
            peak_balance = balance
        dd = peak_balance - balance
        if dd > max_drawdown:
            max_drawdown = dd

        # Reset win chance setiap 9 bet
        if cfg["every9_reset_chance"] and state["total_bets"] % 9 == 0:
            state["win_chance"] = cfg["default_win_chance"]

        state = apply_rules(cfg, state)

    win_rate = state["total_wins"] / state["total_bets"] * 100 if state["total_bets"] > 0 else 0
    roi      = total_profit / total_wager * 100 if total_wager > 0 else 0

    return {
        "label":          label,
        "bets":           state["total_bets"],
        "wins":           state["total_wins"],
        "losses":         state["total_losses"],
        "win_rate":       win_rate,
        "total_wager":    total_wager,
        "total_profit":   total_profit,
        "roi":            roi,
        "final_balance":  balance,
        "max_drawdown":   max_drawdown,
        "safety_stops":   safety_stops,
        "max_loss_streak":max_loss_streak,
        "max_win_streak": max_win_streak,
        "max_single_bet": max_single_bet,
        "bankrupt":       bankrupt,
    }

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def sep(char="─", n=62):
    print(char * n)

def main():
    random.seed()
    print()
    sep("═")
    print("  DIKE BOT — Simulasi Monte Carlo Strategi Dice")
    sep("═")
    print(f"  Saldo awal    : Rp {CFG['start_balance']:>12,.0f}")
    print(f"  Base bet      : Rp {CFG['base_bet']:>12,.0f}")
    print(f"  Win chance    : {CFG['default_win_chance']}%")
    print(f"  Stop loss     : Rp {CFG['stop_loss']:>12,.0f}")
    print(f"  Bet per sesi  : {BETS_PER_RUN:,}")
    print(f"  Jumlah sesi   : {NUM_RUNS}")
    sep()

    results       = []
    all_wager     = []
    all_profit    = []
    all_roi       = []
    all_winrate   = []
    bankrupt_count= 0

    for i in range(1, NUM_RUNS + 1):
        r = run_session(CFG, BETS_PER_RUN, CFG["start_balance"], label=f"Sesi {i}")
        results.append(r)
        all_wager.append(r["total_wager"])
        all_profit.append(r["total_profit"])
        all_roi.append(r["roi"])
        all_winrate.append(r["win_rate"])
        if r["bankrupt"]:
            bankrupt_count += 1

        status = "💀 BANGKRUT" if r["bankrupt"] else ("✓ PROFIT" if r["total_profit"] >= 0 else "✗ RUGI")
        sign   = "+" if r["total_profit"] >= 0 else ""
        print(f"\n  [{r['label']}] {status}")
        sep("─")
        print(f"    Total Bet        : {r['bets']:,}")
        print(f"    Total Menang     : {r['wins']:,}  ({r['win_rate']:.2f}%)")
        print(f"    Total Kalah      : {r['losses']:,}")
        print(f"    Total Wager      : Rp {r['total_wager']:>14,.0f}")
        print(f"    Total P/L        : Rp {sign}{r['total_profit']:>14,.0f}")
        print(f"    ROI              : {r['roi']:+.4f}%")
        print(f"    Saldo Akhir      : Rp {r['final_balance']:>14,.0f}")
        print(f"    Max Drawdown     : Rp {r['max_drawdown']:>14,.0f}")
        print(f"    Safety Stop      : {r['safety_stops']}x")
        print(f"    Max Loss Streak  : {r['max_loss_streak']}")
        print(f"    Max Win Streak   : {r['max_win_streak']}")
        print(f"    Bet Terbesar     : Rp {r['max_single_bet']:>14,.0f}")

    # ── RINGKASAN SEMUA SESI ──────────────────────
    print()
    sep("═")
    print("  RINGKASAN KESELURUHAN")
    sep("═")

    avg_wager   = sum(all_wager)   / NUM_RUNS
    avg_profit  = sum(all_profit)  / NUM_RUNS
    avg_roi     = sum(all_roi)     / NUM_RUNS
    avg_wr      = sum(all_winrate) / NUM_RUNS
    profit_sessions = sum(1 for r in results if r["total_profit"] >= 0 and not r["bankrupt"])

    print(f"  Rata-rata Wager/sesi : Rp {avg_wager:>14,.0f}")
    print(f"  Rata-rata P/L/sesi   : Rp {avg_profit:>+14,.0f}")
    print(f"  Rata-rata ROI        : {avg_roi:>+.4f}%")
    print(f"  Rata-rata Win Rate   : {avg_wr:.2f}%")
    print(f"  Sesi Profit          : {profit_sessions}/{NUM_RUNS}")
    print(f"  Sesi Bangkrut        : {bankrupt_count}/{NUM_RUNS}")
    print()

    # ── ANALISIS & SARAN ─────────────────────────
    sep("═")
    print("  ANALISIS STRATEGI")
    sep("═")

    total_wager_all = sum(all_wager)
    wager_per_hour  = (3600 / (CFG["delay_ms"] / 1000)) * CFG["base_bet"]
    wager_per_day   = wager_per_hour * 24

    print(f"  Estimasi Wager/jam   : Rp {wager_per_hour:>14,.0f}")
    print(f"  Estimasi Wager/hari  : Rp {wager_per_day:>14,.0f}")
    print(f"  Total Wager semua sesi: Rp {total_wager_all:>13,.0f}")
    print()

    # Penilaian
    print("  PENILAIAN:")
    if avg_roi > 0:
        print(f"  ✓ ROI rata-rata POSITIF ({avg_roi:+.4f}%) — strategi menguntungkan secara teoritis")
    else:
        print(f"  ! ROI rata-rata NEGATIF ({avg_roi:+.4f}%) — house edge menggerus modal jangka panjang")

    if avg_wr >= 49:
        print(f"  ✓ Win Rate {avg_wr:.2f}% — mendekati atau melebihi 49.5% target")
    else:
        print(f"  ! Win Rate {avg_wr:.2f}% — di bawah target, perlu evaluasi win chance")

    if bankrupt_count == 0:
        print(f"  ✓ Tidak ada sesi bangkrut dari {NUM_RUNS} simulasi")
    else:
        print(f"  ⚠ {bankrupt_count}/{NUM_RUNS} sesi berakhir bangkrut — pertimbangkan naikkan MIN_BALANCE")

    max_bet_seen = max(r["max_single_bet"] for r in results)
    if max_bet_seen > CFG["start_balance"] * 0.5:
        print(f"  ⚠ Bet terbesar mencapai Rp {max_bet_seen:,.0f} ({max_bet_seen/CFG['start_balance']*100:.0f}% saldo) — risiko tinggi!")
        print(f"     Saran: set MAX_BET_IDR di setting.txt")
    else:
        print(f"  ✓ Bet terbesar Rp {max_bet_seen:,.0f} — dalam batas wajar")

    sep("═")
    print()

if __name__ == "__main__":
    main()
