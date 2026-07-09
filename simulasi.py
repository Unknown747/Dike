#!/usr/bin/env python3
"""
DIKE - Simulasi Monte Carlo + Mode Recovery
Membandingkan strategi normal vs strategi dengan recovery otomatis
"""

import random

# ─────────────────────────────────────────────
#  KONFIGURASI
# ─────────────────────────────────────────────

CFG = {
    "base_bet":           100,
    "default_win_chance": 49.50,
    "ls3_increase_pct":   250.0,
    "ls3_win_chance":     92.00,
    "ls4_win_chance":     89.00,
    "ls5_win_chance":     94.01,
    "ls6_increase_pct":   300.0,
    "ls6_win_chance":     93.00,
    "win_every_3_reset":  True,
    "ws2_decrease_pct":   70.0,
    "ws4_win_chance":     70.00,
    "ws6_win_chance":     65.00,
    "win_reset_win_chance": True,
    "every9_reset_chance":  True,
    "stop_loss":          5000,
    "max_bet":            0,
    "start_balance":      100_000,
}

# ─────────────────────────────────────────────
#  RECOVERY CONFIG
# ─────────────────────────────────────────────

RECOVERY_CFG = {
    # Setelah stop loss, naikkan base bet berdasarkan total deficit
    # Tier 1: deficit < 10% saldo → base bet x1.5
    # Tier 2: deficit 10-25% saldo → base bet x2.0
    # Tier 3: deficit > 25% saldo → base bet x2.5
    "tier1_threshold_pct":  10.0,
    "tier2_threshold_pct":  25.0,
    "tier1_multiplier":     1.5,
    "tier2_multiplier":     2.0,
    "tier3_multiplier":     2.5,

    # Win chance saat recovery mode (lebih konservatif = aman)
    "recovery_win_chance":  55.0,

    # Keluar dari recovery mode jika deficit sudah terpulihkan 80%
    "recovery_exit_pct":    80.0,

    # Batas recovery bet (tidak lebih dari X kali base bet)
    "max_recovery_multiplier": 3.0,
}

NUM_RUNS     = 10
BETS_PER_RUN = 10_000

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def simulate_bet(bet, win_chance):
    roll = random.uniform(0, 100)
    won  = roll > (100 - win_chance)
    if won:
        profit = bet * (99.0 / win_chance) - bet
        return True, profit
    return False, -bet

def apply_rules(cfg, state):
    bet        = state["bet"]
    win_chance = state["win_chance"]
    ls, ws     = state["loss_streak"], state["win_streak"]

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

def get_recovery_base_bet(cfg, rcfg, deficit, balance):
    """Hitung base bet recovery berdasarkan deficit."""
    deficit_pct = (deficit / balance * 100) if balance > 0 else 0
    if deficit_pct <= 0:
        return cfg["base_bet"]
    elif deficit_pct < rcfg["tier1_threshold_pct"]:
        mult = rcfg["tier1_multiplier"]
    elif deficit_pct < rcfg["tier2_threshold_pct"]:
        mult = rcfg["tier2_multiplier"]
    else:
        mult = rcfg["tier3_multiplier"]
    mult = min(mult, rcfg["max_recovery_multiplier"])
    return max(round(cfg["base_bet"] * mult), 1)

# ─────────────────────────────────────────────
#  SESI NORMAL (tanpa recovery)
# ─────────────────────────────────────────────

def run_normal(cfg, num_bets, start_balance):
    state = {
        "bet": cfg["base_bet"], "win_chance": cfg["default_win_chance"],
        "loss_streak": 0, "win_streak": 0, "total_wins": 0,
        "total_losses": 0, "total_bets": 0, "session_loss": 0.0,
        "_last_reset_at": -1,
    }
    balance = start_balance
    total_wager = total_profit = max_drawdown = 0.0
    peak = start_balance
    safety_stops = bankrupt = 0
    max_loss_streak = 0

    for _ in range(num_bets):
        if state["session_loss"] >= cfg["stop_loss"]:
            safety_stops += 1
            state.update({"session_loss": 0.0, "bet": cfg["base_bet"],
                          "win_chance": cfg["default_win_chance"],
                          "loss_streak": 0, "win_streak": 0})

        cb = int(state["bet"])
        if balance < cb:
            bankrupt = 1
            break

        total_wager += cb
        state["total_bets"] += 1
        won, result = simulate_bet(cb, state["win_chance"])

        if won:
            balance += result; total_profit += result
            state["total_wins"] += 1; state["win_streak"] += 1
            state["loss_streak"] = 0
            if cfg["win_reset_win_chance"]:
                state["win_chance"] = cfg["default_win_chance"]
        else:
            balance += result; total_profit += result
            state["session_loss"] -= result
            state["total_losses"] += 1; state["loss_streak"] += 1
            state["win_streak"] = 0
            max_loss_streak = max(max_loss_streak, state["loss_streak"])

        peak = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)
        if cfg["every9_reset_chance"] and state["total_bets"] % 9 == 0:
            state["win_chance"] = cfg["default_win_chance"]
        state = apply_rules(cfg, state)

    wr  = state["total_wins"] / state["total_bets"] * 100 if state["total_bets"] else 0
    roi = total_profit / total_wager * 100 if total_wager else 0
    return dict(bets=state["total_bets"], wins=state["total_wins"],
                win_rate=wr, total_wager=total_wager, total_profit=total_profit,
                roi=roi, final_balance=balance, max_drawdown=max_drawdown,
                safety_stops=safety_stops, max_loss_streak=max_loss_streak,
                bankrupt=bankrupt)

# ─────────────────────────────────────────────
#  SESI RECOVERY (dengan mode recovery)
# ─────────────────────────────────────────────

def run_recovery(cfg, rcfg, num_bets, start_balance):
    state = {
        "bet": cfg["base_bet"], "win_chance": cfg["default_win_chance"],
        "loss_streak": 0, "win_streak": 0, "total_wins": 0,
        "total_losses": 0, "total_bets": 0, "session_loss": 0.0,
        "_last_reset_at": -1,
    }
    balance      = start_balance
    total_wager  = total_profit = max_drawdown = 0.0
    peak         = start_balance
    safety_stops = bankrupt = 0
    max_loss_streak = 0
    total_deficit   = 0.0       # akumulasi semua kerugian sesi
    recovery_mode   = False
    recovery_bets   = 0
    recovered_amount= 0.0

    for _ in range(num_bets):
        if state["session_loss"] >= cfg["stop_loss"]:
            safety_stops  += 1
            total_deficit += state["session_loss"]
            state["session_loss"] = 0.0
            state["loss_streak"]  = 0
            state["win_streak"]   = 0

            # Masuk recovery mode
            if total_deficit > 0:
                recovery_mode = True
                rec_base = get_recovery_base_bet(cfg, rcfg, total_deficit, balance)
                state["bet"]        = rec_base
                state["win_chance"] = rcfg["recovery_win_chance"]
            else:
                state["bet"]        = cfg["base_bet"]
                state["win_chance"] = cfg["default_win_chance"]

        cb = int(state["bet"])
        if balance < cb:
            bankrupt = 1
            break

        total_wager         += cb
        state["total_bets"] += 1
        won, result          = simulate_bet(cb, state["win_chance"])

        if won:
            balance            += result
            total_profit       += result
            state["total_wins"] += 1
            state["win_streak"] += 1
            state["loss_streak"] = 0

            if recovery_mode:
                recovered_amount += result
                recovery_bets    += 1
                # Cek apakah sudah cukup terpulihkan
                if recovered_amount >= total_deficit * (rcfg["recovery_exit_pct"] / 100):
                    recovery_mode    = False
                    total_deficit    = 0.0
                    recovered_amount = 0.0
                    state["bet"]        = cfg["base_bet"]
                    state["win_chance"] = cfg["default_win_chance"]
            else:
                if cfg["win_reset_win_chance"]:
                    state["win_chance"] = cfg["default_win_chance"]
        else:
            balance             += result
            total_profit        += result
            state["session_loss"] -= result
            state["total_losses"] += 1
            state["loss_streak"]  += 1
            state["win_streak"]    = 0
            max_loss_streak        = max(max_loss_streak, state["loss_streak"])

            if recovery_mode:
                # Deficit naik lagi, update bet recovery
                total_deficit -= result  # result negatif jadi deficit naik
                rec_base = get_recovery_base_bet(cfg, rcfg, total_deficit, balance)
                # Jangan ubah bet di tengah streak (biarkan apply_rules yang kelola)

        peak         = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)

        if not recovery_mode:
            if cfg["every9_reset_chance"] and state["total_bets"] % 9 == 0:
                state["win_chance"] = cfg["default_win_chance"]
            state = apply_rules(cfg, state)

    wr  = state["total_wins"] / state["total_bets"] * 100 if state["total_bets"] else 0
    roi = total_profit / total_wager * 100 if total_wager else 0
    return dict(bets=state["total_bets"], wins=state["total_wins"],
                win_rate=wr, total_wager=total_wager, total_profit=total_profit,
                roi=roi, final_balance=balance, max_drawdown=max_drawdown,
                safety_stops=safety_stops, max_loss_streak=max_loss_streak,
                recovery_bets=recovery_bets, bankrupt=bankrupt)

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def avg(lst): return sum(lst) / len(lst) if lst else 0

def sep(c="─", n=65): print(c * n)

def print_row(label, normal, recovery, fmt=","):
    if fmt == "pct":
        print(f"  {label:<24} {normal:>10.2f}%   {recovery:>10.2f}%")
    elif fmt == "idr":
        sign_n = "+" if normal >= 0 else ""
        sign_r = "+" if recovery >= 0 else ""
        print(f"  {label:<24} Rp {sign_n}{normal:>10,.0f}   Rp {sign_r}{recovery:>10,.0f}")
    elif fmt == "roi":
        print(f"  {label:<24} {normal:>10.4f}%   {recovery:>10.4f}%")
    elif fmt == "int":
        print(f"  {label:<24} {normal:>13,.0f}   {recovery:>13,.0f}")
    else:
        print(f"  {label:<24} {normal:>13}   {recovery:>13}")

def main():
    random.seed()
    print()
    sep("═")
    print("  DIKE BOT — Simulasi Recovery Saldo")
    sep("═")
    print(f"  Saldo awal      : Rp {CFG['start_balance']:,}")
    print(f"  Base Bet        : Rp {CFG['base_bet']:,}")
    print(f"  Stop Loss/sesi  : Rp {CFG['stop_loss']:,}")
    print(f"  Bet per sesi    : {BETS_PER_RUN:,}  |  Jumlah sesi: {NUM_RUNS}")
    print()
    print(f"  Recovery Tier 1 (<{RECOVERY_CFG['tier1_threshold_pct']:.0f}% deficit) : base bet × {RECOVERY_CFG['tier1_multiplier']}")
    print(f"  Recovery Tier 2 (<{RECOVERY_CFG['tier2_threshold_pct']:.0f}% deficit) : base bet × {RECOVERY_CFG['tier2_multiplier']}")
    print(f"  Recovery Tier 3 (>={RECOVERY_CFG['tier2_threshold_pct']:.0f}% deficit): base bet × {RECOVERY_CFG['tier3_multiplier']}")
    print(f"  Win Chance saat Recovery : {RECOVERY_CFG['recovery_win_chance']}%")
    print(f"  Exit Recovery jika sudah pulih : {RECOVERY_CFG['recovery_exit_pct']:.0f}%")
    sep()

    n_profits  = []; n_wagers   = []; n_rois     = []; n_wrs      = []
    n_draws    = []; n_bankrupt = 0
    r_profits  = []; r_wagers   = []; r_rois     = []; r_wrs      = []
    r_draws    = []; r_bankrupt = 0

    print(f"\n  {'Sesi':<6} {'Normal P/L':>16} {'Recovery P/L':>16} {'Selisih':>16}")
    sep("─")

    for i in range(1, NUM_RUNS + 1):
        seed = random.randint(0, 999999)

        random.seed(seed)
        n = run_normal(CFG, BETS_PER_RUN, CFG["start_balance"])

        random.seed(seed)
        r = run_recovery(CFG, RECOVERY_CFG, BETS_PER_RUN, CFG["start_balance"])

        n_profits.append(n["total_profit"]); n_wagers.append(n["total_wager"])
        n_rois.append(n["roi"]); n_wrs.append(n["win_rate"])
        n_draws.append(n["max_drawdown"])
        if n["bankrupt"]: n_bankrupt += 1

        r_profits.append(r["total_profit"]); r_wagers.append(r["total_wager"])
        r_rois.append(r["roi"]); r_wrs.append(r["win_rate"])
        r_draws.append(r["max_drawdown"])
        if r["bankrupt"]: r_bankrupt += 1

        diff  = r["total_profit"] - n["total_profit"]
        sn    = "+" if n["total_profit"] >= 0 else ""
        sr    = "+" if r["total_profit"] >= 0 else ""
        sd    = "+" if diff >= 0 else ""
        nb    = " 💀" if n["bankrupt"] else ""
        rb    = " 💀" if r["bankrupt"] else ""
        print(f"  {i:<6} Rp {sn}{n['total_profit']:>10,.0f}{nb}   "
              f"Rp {sr}{r['total_profit']:>10,.0f}{rb}   "
              f"Rp {sd}{diff:>10,.0f}")

    # ── RINGKASAN ──────────────────────────────────
    print()
    sep("═")
    print(f"  {'METRIK':<24} {'NORMAL':>14}   {'DENGAN RECOVERY':>14}")
    sep("─")
    print_row("Rata-rata P/L",    avg(n_profits), avg(r_profits), "idr")
    print_row("Rata-rata ROI",    avg(n_rois),    avg(r_rois),    "roi")
    print_row("Rata-rata Win Rate", avg(n_wrs),   avg(r_wrs),     "pct")
    print_row("Rata-rata Wager",  avg(n_wagers),  avg(r_wagers),  "idr")
    print_row("Rata-rata Drawdown", avg(n_draws), avg(r_draws),   "idr")
    print_row("Sesi Bangkrut",    n_bankrupt,     r_bankrupt,     "int")
    sep("═")

    # ── ANALISIS ───────────────────────────────────
    print()
    print("  ANALISIS RECOVERY:")
    sep("─")

    pl_diff  = avg(r_profits) - avg(n_profits)
    dd_diff  = avg(r_draws)   - avg(n_draws)
    roi_diff = avg(r_rois)    - avg(n_rois)

    if pl_diff > 0:
        print(f"  ✓ Recovery meningkatkan P/L rata-rata sebesar Rp {pl_diff:,.0f}/sesi")
    else:
        print(f"  ! Recovery belum cukup mengangkat P/L (selisih Rp {pl_diff:,.0f})")

    if dd_diff < 0:
        print(f"  ✓ Drawdown berkurang Rp {abs(dd_diff):,.0f} — risiko lebih rendah")
    else:
        print(f"  ! Drawdown naik Rp {dd_diff:,.0f} — recovery bet lebih besar = risiko lebih tinggi")

    if roi_diff > 0:
        print(f"  ✓ ROI membaik {roi_diff:+.4f}% berkat mode recovery")
    else:
        print(f"  ! ROI masih negatif, house edge tetap berperan")

    if r_bankrupt < n_bankrupt:
        print(f"  ✓ Recovery mengurangi risiko bangkrut: {n_bankrupt} → {r_bankrupt}")
    elif r_bankrupt == n_bankrupt:
        print(f"  → Risiko bangkrut sama ({r_bankrupt} sesi)")
    else:
        print(f"  ⚠ Recovery mode meningkatkan risiko bangkrut: {n_bankrupt} → {r_bankrupt}")

    print()
    print("  SARAN UNTUK SETTING.TXT:")
    sep("─")
    print(f"  # Aktifkan recovery mode — tambahkan baris ini:")
    print(f"  RECOVERY_MODE          = true")
    print(f"  RECOVERY_TIER1_PCT     = {RECOVERY_CFG['tier1_threshold_pct']:.0f}")
    print(f"  RECOVERY_TIER2_PCT     = {RECOVERY_CFG['tier2_threshold_pct']:.0f}")
    print(f"  RECOVERY_MULTIPLIER_T1 = {RECOVERY_CFG['tier1_multiplier']}")
    print(f"  RECOVERY_MULTIPLIER_T2 = {RECOVERY_CFG['tier2_multiplier']}")
    print(f"  RECOVERY_MULTIPLIER_T3 = {RECOVERY_CFG['tier3_multiplier']}")
    print(f"  RECOVERY_WIN_CHANCE    = {RECOVERY_CFG['recovery_win_chance']}")
    print(f"  RECOVERY_EXIT_PCT      = {RECOVERY_CFG['recovery_exit_pct']:.0f}")
    sep("═")
    print()

if __name__ == "__main__":
    main()
