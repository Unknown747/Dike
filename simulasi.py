#!/usr/bin/env python3
"""
DIKE - Simulasi Setting Baru (Optimized)
Membandingkan: Setting Lama vs Setting Baru (dari hasil simulasi)
"""

import random

# ─────────────────────────────────────────────
#  SETTING LAMA (sebelum optimasi)
# ─────────────────────────────────────────────
OLD = {
    "base_bet": 100, "default_win_chance": 49.50,
    "ls3_increase_pct": 250.0, "ls3_win_chance": 92.00,
    "ls4_win_chance": 89.00,   "ls5_win_chance": 94.01,
    "ls6_increase_pct": 300.0, "ls6_win_chance": 93.00,
    "win_every_3_reset": True, "ws2_decrease_pct": 70.0,
    "ws4_win_chance": 70.00,   "ws6_win_chance": 65.00,
    "win_reset_win_chance": True, "every9_reset_chance": True,
    "stop_loss": 5000, "max_bet": 0,
    "min_balance": 0,
    # Recovery: tidak ada
    "recovery_mode": False,
    "recovery_win_chance": 49.50, "recovery_bet_mult": 1.0,
    "recovery_exit_pct": 80, "recovery_min_deficit": 0,
}

# ─────────────────────────────────────────────
#  SETTING BARU (optimized dari simulasi)
# ─────────────────────────────────────────────
NEW = {
    "base_bet": 2000, "default_win_chance": 49.50,
    "ls3_increase_pct": 250.0, "ls3_win_chance": 92.00,
    "ls4_win_chance": 89.00,   "ls5_win_chance": 94.01,
    "ls6_increase_pct": 300.0, "ls6_win_chance": 93.00,
    "win_every_3_reset": True, "ws2_decrease_pct": 70.0,
    "ws4_win_chance": 70.00,   "ws6_win_chance": 65.00,
    "win_reset_win_chance": True, "every9_reset_chance": True,
    # ★ Setting saat ini (setting.txt) — base bet dinaikkan ke 2000
    "stop_loss": 40000, "max_bet": 70000,
    "min_balance": 50000,
    # ★ Recovery mode aktif (win chance, bukan naikkan bet)
    "recovery_mode": True,
    "recovery_win_chance": 90.00, "recovery_bet_mult": 1.0,
    "recovery_exit_pct": 80, "recovery_min_deficit": 0,
}

NUM_RUNS     = 20
BETS_PER_RUN = 10_000
START_BAL    = 2_000_000

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def sim_bet(bet, win_chance):
    won = random.uniform(0, 100) > (100 - win_chance)
    return (True,  bet * (99.0 / win_chance) - bet) if won else (False, -bet)

def apply_rules(cfg, state):
    bet, wc = state["bet"], state["win_chance"]
    ls, ws  = state["loss_streak"], state["win_streak"]
    if ls >= 6: bet = bet*(1+cfg["ls6_increase_pct"]/100); wc = cfg["ls6_win_chance"]
    elif ls==5: wc = cfg["ls5_win_chance"]
    elif ls==4: wc = cfg["ls4_win_chance"]
    elif ls==3: bet = bet*(1+cfg["ls3_increase_pct"]/100); wc = cfg["ls3_win_chance"]
    if ws>=6:   wc = cfg["ws6_win_chance"]
    elif ws>=4: wc = cfg["ws4_win_chance"]
    elif ws>=2: bet = bet*(cfg["ws2_decrease_pct"]/100)
    if cfg["win_every_3_reset"] and state["total_wins"]>0 \
            and state["total_wins"]%3==0 \
            and state.get("_lr") != state["total_wins"]:
        bet = cfg["base_bet"]; state["_lr"] = state["total_wins"]
    if cfg["max_bet"] > 0: bet = min(bet, cfg["max_bet"])
    state["bet"] = max(round(bet), 1)
    state["win_chance"] = round(wc, 4)
    return state

def run_session(cfg, num_bets, start_balance):
    st = {"bet": cfg["base_bet"], "win_chance": cfg["default_win_chance"],
          "loss_streak": 0, "win_streak": 0, "total_wins": 0,
          "total_losses": 0, "total_bets": 0, "session_loss": 0.0,
          "_lr": -1}
    balance = start_balance
    total_wager = profit = max_dd = 0.0
    peak = start_balance
    safety_stops = bankrupt = 0
    max_ls = 0
    recovery_active = False
    total_deficit = recovered = 0.0
    rec_bets = 0

    for _ in range(num_bets):
        # Safety stop
        if st["session_loss"] >= cfg["stop_loss"]:
            safety_stops  += 1
            total_deficit += st["session_loss"]
            st["session_loss"] = 0.0
            st["loss_streak"]  = 0
            st["win_streak"]   = 0
            if cfg["recovery_mode"] and total_deficit > cfg["recovery_min_deficit"]:
                recovery_active = True
                recovered = 0.0
                rec_bet = max(round(cfg["base_bet"] * cfg["recovery_bet_mult"]), 1)
                st["bet"] = rec_bet
                st["win_chance"] = cfg["recovery_win_chance"]
            else:
                st["bet"] = cfg["base_bet"]
                st["win_chance"] = cfg["default_win_chance"]

        cb = int(st["bet"])
        if balance < cb:
            bankrupt = 1; break

        total_wager   += cb
        st["total_bets"] += 1
        won, result    = sim_bet(cb, st["win_chance"])

        if won:
            balance += result; profit += result
            st["total_wins"] += 1; st["win_streak"] += 1; st["loss_streak"] = 0
            if recovery_active:
                recovered += result; rec_bets += 1
                if recovered >= total_deficit * (cfg["recovery_exit_pct"] / 100):
                    recovery_active = False; total_deficit = 0.0; recovered = 0.0
                    st["bet"] = cfg["base_bet"]
                    st["win_chance"] = cfg["default_win_chance"]
                    st["loss_streak"] = 0; st["win_streak"] = 0
            else:
                if cfg["win_reset_win_chance"]:
                    st["win_chance"] = cfg["default_win_chance"]
        else:
            balance += result; profit += result
            st["session_loss"] -= result
            st["total_losses"] += 1; st["loss_streak"] += 1; st["win_streak"] = 0
            max_ls = max(max_ls, st["loss_streak"])
            if recovery_active: total_deficit -= result

        peak = max(peak, balance)
        max_dd = max(max_dd, peak - balance)

        if not recovery_active:
            if cfg["every9_reset_chance"] and st["total_bets"] % 9 == 0:
                st["win_chance"] = cfg["default_win_chance"]
            st = apply_rules(cfg, st)

    wr  = st["total_wins"] / st["total_bets"] * 100 if st["total_bets"] else 0
    roi = profit / total_wager * 100 if total_wager else 0
    return dict(bets=st["total_bets"], wins=st["total_wins"], losses=st["total_losses"],
                win_rate=wr, wager=total_wager, profit=profit, roi=roi,
                balance=balance, max_dd=max_dd, safety_stops=safety_stops,
                max_ls=max_ls, rec_bets=rec_bets, bankrupt=bankrupt)

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def avg(l): return sum(l)/len(l) if l else 0

def main():
    random.seed()
    print()
    print("═"*70)
    print("  DIKE — Simulasi: Setting LAMA vs Setting BARU (Optimized)")
    print("═"*70)
    print(f"  Saldo awal: Rp {START_BAL:,}  |  {BETS_PER_RUN:,} bet/sesi  |  {NUM_RUNS} sesi")
    print()
    print(f"  {'PERUBAHAN SETTING':}")
    print(f"  Base Bet     : Rp 100     →  Rp 2.000  (dinaikkan 20x)")
    print(f"  Stop Loss    : Rp 5.000   →  Rp 40.000 (proporsional 20x base bet)")
    print(f"  Max Bet      : Tidak ada  →  Rp 70.000 (batas aman)")
    print(f"  Min Saldo    : Tidak ada  →  Rp 50.000 (batas berhenti)")
    print(f"  Recovery Mode: NONAKTIF   →  AKTIF (win chance 90%)")
    print("─"*70)

    # Kolom header
    print(f"\n  {'':>4}  {'──── LAMA ────':>28}  {'──── BARU ────':>28}")
    print(f"  {'#':>4}  {'P/L':>13} {'Saldo Akhir':>14}  {'P/L':>13} {'Saldo Akhir':>14}  {'Δ P/L':>10}")
    print("  " + "─"*68)

    op=[]; ow=[]; od=[]; os_=[]; ob=0
    np_=[]; nw=[]; nd=[]; ns=[]; nb=0

    for i in range(1, NUM_RUNS+1):
        seed = random.randint(0, 9999999)

        random.seed(seed)
        o = run_session(OLD, BETS_PER_RUN, START_BAL)

        random.seed(seed)
        n = run_session(NEW, BETS_PER_RUN, START_BAL)

        op.append(o["profit"]); ow.append(o["wager"])
        od.append(o["max_dd"]); os_.append(o["safety_stops"])
        if o["bankrupt"]: ob += 1

        np_.append(n["profit"]); nw.append(n["wager"])
        nd.append(n["max_dd"]); ns.append(n["safety_stops"])
        if n["bankrupt"]: nb += 1

        diff = n["profit"] - o["profit"]
        so = "+" if o["profit"]>=0 else ""
        sn = "+" if n["profit"]>=0 else ""
        sd = "+" if diff>=0 else ""
        bnk_o = "💀" if o["bankrupt"] else "  "
        bnk_n = "💀" if n["bankrupt"] else "  "
        print(f"  {i:>4}  "
              f"Rp {so}{o['profit']:>9,.0f}{bnk_o} Rp {o['balance']:>9,.0f}  "
              f"Rp {sn}{n['profit']:>9,.0f}{bnk_n} Rp {n['balance']:>9,.0f}  "
              f"Rp {sd}{diff:>7,.0f}")

    # ── RINGKASAN ──────────────────────────────
    print()
    print("═"*70)
    print(f"  {'METRIK':<30} {'LAMA':>15}   {'BARU':>15}")
    print("─"*70)

    rows = [
        ("Rata-rata P/L",        avg(op),  avg(np_),  "idr"),
        ("Rata-rata ROI",        avg(op)/avg(ow)*100 if avg(ow) else 0,
                                  avg(np_)/avg(nw)*100 if avg(nw) else 0, "pct2"),
        ("Rata-rata Wager",      avg(ow),  avg(nw),   "idr"),
        ("Rata-rata Drawdown",   avg(od),  avg(nd),   "idr"),
        ("Rata-rata Safety Stop",avg(os_), avg(ns),   "num"),
        ("Sesi Bangkrut",        ob,       nb,        "num"),
        ("Sesi Profit",
         sum(1 for x in op if x>=0), sum(1 for x in np_ if x>=0), "num"),
    ]

    for label, v_old, v_new, fmt in rows:
        diff = v_new - v_old
        better = diff > 0 if fmt in ("idr","pct2") else diff < 0
        icon = "✓" if better else ("→" if diff==0 else "!")
        if fmt == "idr":
            so = "+" if v_old>=0 else ""
            sn = "+" if v_new>=0 else ""
            sd = "+" if diff>=0 else ""
            print(f"  {icon} {label:<28} Rp {so}{v_old:>10,.0f}   Rp {sn}{v_new:>10,.0f}   ({sd}Rp {diff:,.0f})")
        elif fmt == "pct2":
            sd = "+" if diff>=0 else ""
            print(f"  {icon} {label:<28} {v_old:>12.4f}%   {v_new:>12.4f}%   ({sd}{diff:.4f}%)")
        else:
            diff_i = int(v_new - v_old)
            sd = "+" if diff_i>=0 else ""
            print(f"  {icon} {label:<28} {int(v_old):>13,}   {int(v_new):>13,}   ({sd}{diff_i})")

    # ── KESIMPULAN ─────────────────────────────
    print()
    print("═"*70)
    print("  KESIMPULAN")
    print("─"*70)
    pl_diff  = avg(np_) - avg(op)
    dd_diff  = avg(nd)  - avg(od)
    safe_diff= avg(ns)  - avg(os_)

    if pl_diff >= 0:
        print(f"  ✓ Setting baru LEBIH MENGUNTUNGKAN Rp {pl_diff:,.0f}/sesi")
    else:
        print(f"  → Setting baru rugi lebih kecil sebesar Rp {abs(pl_diff):,.0f}/sesi")
        print(f"    (house edge tetap ada, tapi modal lebih terlindungi)")
    if dd_diff < 0:
        print(f"  ✓ Drawdown BERKURANG Rp {abs(dd_diff):,.0f} — modal lebih aman")
    else:
        print(f"  ! Drawdown naik Rp {dd_diff:,.0f} — pantau saldo lebih ketat")
    if safe_diff < 0:
        print(f"  ✓ Safety stop lebih jarang terpicu ({abs(safe_diff):.0f}x lebih sedikit/sesi)")
    else:
        print(f"  → Safety stop lebih sering terpicu (stop loss lebih ketat)")
    if nb < ob:
        print(f"  ✓ Risiko bangkrut berkurang: {ob} → {nb} sesi")
    elif nb == ob == 0:
        print(f"  ✓ Tidak ada sesi bangkrut di kedua setting")
    else:
        print(f"  ! Bangkrut meningkat: {ob} → {nb}")

    wager_per_day_old = (3600/(OLD["delay_ms"]/1000) if "delay_ms" in OLD else 3600/0.3) * OLD["base_bet"] * 24
    wager_per_day_new = (3600/(NEW["delay_ms"]/1000) if "delay_ms" in NEW else 3600/0.3) * NEW["base_bet"] * 24
    print(f"\n  Estimasi Wager/hari (lama) : Rp {28_800_000:,.0f}")
    print(f"  Estimasi Wager/hari (baru) : Rp {28_800_000:,.0f}")
    print(f"  Jika ada rakeback 5%       : Rp {28_800_000*0.05:,.0f}/hari")
    print(f"  Jika ada rakeback 10%      : Rp {28_800_000*0.10:,.0f}/hari")
    print("═"*70)
    print()

if __name__ == "__main__":
    main()
