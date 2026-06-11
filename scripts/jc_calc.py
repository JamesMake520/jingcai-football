#!/usr/bin/env python3
"""竞彩足球计算工具
用法:
  python jc_calc.py implied 2.10 3.20 3.40          # 赔率->去水隐含概率
  python jc_calc.py ev 0.52 2.10                     # 期望值
  python jc_calc.py kelly 0.52 2.10 --bankroll 500   # 凯利仓位(默认1/4凯利)
  python jc_calc.py parlay 2.10 1.85 --stake 100 --probs 0.52,0.60   # 串关
  python jc_calc.py poisson 1.6 1.1                  # 泊松比分/胜平负/总进球分布
"""
import argparse
import math
import sys


def cmd_implied(args):
    odds = args.odds
    raw = [1.0 / o for o in odds]
    overround = sum(raw)
    payout = 1.0 / overround
    labels = ["胜", "平", "负"] if len(odds) == 3 else [f"选项{i+1}" for i in range(len(odds))]
    print(f"赔率: {odds}")
    print(f"总和(含水): {overround:.4f}  | 返还率: {payout*100:.1f}%  | 水位: {(overround-1)*100:.1f}%")
    print("去水隐含概率:")
    for lab, r in zip(labels, raw):
        print(f"  {lab}: {r/overround*100:.1f}%  (含水: {r*100:.1f}%)")


def cmd_ev(args):
    p, o = args.prob, args.odds
    ev = p * o - 1
    print(f"主观概率 {p*100:.1f}% × 赔率 {o} − 1 = EV {ev*100:+.1f}%")
    if ev > 0.08:
        print("判定: 可操作的价值点 (EV > +8%)")
    elif ev > 0:
        print("判定: 微弱正EV,在估计误差范围内,谨慎")
    else:
        print("判定: 负EV,无价值")


def kelly_fraction(p, odds):
    b = odds - 1
    return (p * b - (1 - p)) / b if b > 0 else 0.0


def cmd_kelly(args):
    p, o = args.prob, args.odds
    f = kelly_fraction(p, o)
    if f <= 0:
        print(f"凯利值 {f*100:.1f}% ≤ 0:无优势,不建议投注")
        return
    quarter = f / 4
    print(f"全凯利: 资金的 {f*100:.1f}%")
    print(f"1/4凯利(建议): 资金的 {quarter*100:.2f}%")
    if args.bankroll:
        print(f"按资金 {args.bankroll}: 全凯利 {args.bankroll*f:.0f},1/4凯利 {args.bankroll*quarter:.0f}")
    print("注: 凯利公式假设主观概率准确;实际估计有误差,务必使用分数凯利。")


def cmd_parlay(args):
    odds = args.odds
    total_odds = math.prod(odds)
    n = len(odds)
    print(f"{n}串1 | 各场SP: {odds} | 总赔率: {total_odds:.2f}")
    if args.stake:
        print(f"本金 {args.stake} → 全中奖金 {args.stake*total_odds:.0f} (利润 {args.stake*(total_odds-1):.0f})")
    if args.probs:
        probs = [float(x) for x in args.probs.split(",")]
        if len(probs) != n:
            sys.exit("错误: --probs 数量必须与赔率场次一致")
        hit = math.prod(probs)
        ev = hit * total_odds - 1
        print(f"各场命中率: {[f'{p*100:.0f}%' for p in probs]}")
        print(f"整体命中率: {hit*100:.1f}%  | 组合EV: {ev*100:+.1f}%")
        singles_ev = [p * o - 1 for p, o in zip(probs, odds)]
        neg = [i + 1 for i, e in enumerate(singles_ev) if e < 0]
        if neg:
            print(f"警告: 第{neg}场单场EV为负,串入会拉低整体EV,建议剔除")


def cmd_poisson(args):
    lh, la = args.home_xg, args.away_xg
    max_g = 8

    def pois(lmb, k):
        return math.exp(-lmb) * lmb ** k / math.factorial(k)

    grid = [[pois(lh, i) * pois(la, j) for j in range(max_g + 1)] for i in range(max_g + 1)]
    p_home = sum(grid[i][j] for i in range(max_g + 1) for j in range(max_g + 1) if i > j)
    p_draw = sum(grid[i][i] for i in range(max_g + 1))
    p_away = sum(grid[i][j] for i in range(max_g + 1) for j in range(max_g + 1) if i < j)
    print(f"预期进球: 主 {lh} / 客 {la}")
    print(f"胜平负: 主胜 {p_home*100:.1f}% | 平 {p_draw*100:.1f}% | 客胜 {p_away*100:.1f}%")

    scores = [((i, j), grid[i][j]) for i in range(max_g + 1) for j in range(max_g + 1)]
    scores.sort(key=lambda x: -x[1])
    print("最可能比分 Top 6:")
    for (i, j), p in scores[:6]:
        print(f"  {i}:{j}  {p*100:.1f}%")

    print("总进球分布:")
    totals = {}
    for (i, j), p in scores:
        t = i + j
        key = "7+" if t >= 7 else str(t)
        totals[key] = totals.get(key, 0) + p
    for k in ["0", "1", "2", "3", "4", "5", "6", "7+"]:
        print(f"  {k}球: {totals.get(k, 0)*100:.1f}%")
    print("注: 泊松模型假设进球独立,实际平局/低比分概率常被低估1-3个百分点,可手动上调平局。")


def main():
    ap = argparse.ArgumentParser(description="竞彩足球计算工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("implied", help="赔率->去水隐含概率")
    p1.add_argument("odds", type=float, nargs="+")
    p1.set_defaults(func=cmd_implied)

    p2 = sub.add_parser("ev", help="期望值")
    p2.add_argument("prob", type=float, help="主观概率, 0-1")
    p2.add_argument("odds", type=float)
    p2.set_defaults(func=cmd_ev)

    p3 = sub.add_parser("kelly", help="凯利仓位")
    p3.add_argument("prob", type=float)
    p3.add_argument("odds", type=float)
    p3.add_argument("--bankroll", type=float, default=None)
    p3.set_defaults(func=cmd_kelly)

    p4 = sub.add_parser("parlay", help="串关计算")
    p4.add_argument("odds", type=float, nargs="+")
    p4.add_argument("--stake", type=float, default=None)
    p4.add_argument("--probs", type=str, default=None, help="逗号分隔的各场命中率")
    p4.set_defaults(func=cmd_parlay)

    p5 = sub.add_parser("poisson", help="泊松比分模型")
    p5.add_argument("home_xg", type=float)
    p5.add_argument("away_xg", type=float)
    p5.set_defaults(func=cmd_poisson)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
