#!/usr/bin/env python3
"""竞彩预测记录与复盘工具 — skill自我进化的数据底座
用法:
  # 记录一次预测(分析完成后立即执行)
  python track.py log --match "曼城vs利物浦" --play 胜平负 --pick 主胜 \
      --prob 0.55 --odds 2.10 --conf 高 --reasons "主场强势;客队三中卫伤停" \
      --file records.json

  # 赛后录入结果
  python track.py settle --id 3 --result 主胜 --file records.json
  python track.py settle --id 4 --result 平 --note "第89分钟点球扳平" --file records.json

  # 复盘报告(命中率/校准度/Brier/ROI,按玩法和置信度分组)
  python track.py report --file records.json
"""
import argparse
import json
import os
import sys
from datetime import date


def load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def cmd_log(args):
    data = load(args.file)
    rec = {
        "id": (max((r["id"] for r in data), default=0) + 1),
        "date": args.date or date.today().isoformat(),
        "match": args.match,
        "play": args.play,
        "pick": args.pick,
        "prob": args.prob,
        "odds": args.odds,
        "conf": args.conf,
        "reasons": args.reasons,
        "result": None,
        "hit": None,
        "note": None,
    }
    data.append(rec)
    save(args.file, data)
    print(f"已记录 #{rec['id']}: {rec['match']} | {rec['play']} {rec['pick']} | 概率 {rec['prob']*100:.0f}% @ {rec['odds']} | 置信度 {rec['conf']}")


def cmd_settle(args):
    data = load(args.file)
    rec = next((r for r in data if r["id"] == args.id), None)
    if not rec:
        sys.exit(f"找不到记录 #{args.id}")
    rec["result"] = args.result
    rec["hit"] = (args.result == rec["pick"])
    if args.note:
        rec["note"] = args.note
    save(args.file, data)
    mark = "✓ 命中" if rec["hit"] else "✗ 未中"
    print(f"#{rec['id']} {rec['match']}: 预测 {rec['pick']} → 实际 {rec['result']} {mark}")
    if not rec["hit"]:
        print("提示: 请进行失败归因(见SKILL.md复盘流程),区分'判断错误'与'运气波动',并更新lessons文件。")


def cmd_report(args):
    data = [r for r in load(args.file) if r["result"] is not None]
    if not data:
        print("暂无已结算记录")
        return
    n = len(data)
    hits = sum(r["hit"] for r in data)
    brier = sum((r["prob"] - (1.0 if r["hit"] else 0.0)) ** 2 for r in data) / n
    stake = 1.0  # 按每注1单位计算ROI
    pnl = sum((r["odds"] - 1) * stake if r["hit"] else -stake for r in data)
    print(f"=== 总览 (已结算 {n} 注) ===")
    print(f"命中率: {hits}/{n} = {hits/n*100:.1f}%")
    print(f"Brier分数: {brier:.3f} (越低越好; 0.25=纯瞎猜二元基准, <0.20 算有判断力)")
    print(f"模拟ROI(每注1单位): {pnl:+.2f} 单位 ({pnl/n*100:+.1f}%)")

    print("\n=== 校准度 (说X%把握时实际命中多少) ===")
    bins = [(0, 0.45, "低估区 <45%"), (0.45, 0.6, "中等 45-60%"), (0.6, 0.75, "较高 60-75%"), (0.75, 1.01, "高 ≥75%")]
    for lo, hi, label in bins:
        grp = [r for r in data if lo <= r["prob"] < hi]
        if grp:
            avg_p = sum(r["prob"] for r in grp) / len(grp)
            actual = sum(r["hit"] for r in grp) / len(grp)
            gap = actual - avg_p
            flag = " ← 显著过度自信" if gap < -0.10 and len(grp) >= 8 else (" ← 显著过度保守" if gap > 0.10 and len(grp) >= 8 else "")
            print(f"  {label}: {len(grp)}注 | 平均声称 {avg_p*100:.0f}% | 实际命中 {actual*100:.0f}%{flag}")

    print("\n=== 分组表现 ===")
    for key, name in [("play", "玩法"), ("conf", "置信度")]:
        groups = {}
        for r in data:
            groups.setdefault(r[key], []).append(r)
        print(f"按{name}:")
        for k, grp in sorted(groups.items()):
            h = sum(r["hit"] for r in grp)
            g_pnl = sum((r["odds"] - 1) if r["hit"] else -1 for r in grp)
            print(f"  {k}: {h}/{len(grp)} 命中 ({h/len(grp)*100:.0f}%) | ROI {g_pnl/len(grp)*100:+.0f}%")

    misses = [r for r in data if not r["hit"]]
    if misses:
        print(f"\n=== 未中清单 ({len(misses)}注, 复盘素材) ===")
        for r in misses:
            note = f" | {r['note']}" if r.get("note") else ""
            print(f"  #{r['id']} {r['match']} {r['play']}: 预测{r['pick']}({r['prob']*100:.0f}%@{r['odds']}) 实际{r['result']}{note}")
    if n < 30:
        print(f"\n注意: 样本仅{n}注。少于30注的任何结论都不可靠,少于50注不要据此修改分析方法。")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("log")
    p1.add_argument("--match", required=True)
    p1.add_argument("--play", required=True, help="胜平负/让球/比分/总进球/半全场/串关")
    p1.add_argument("--pick", required=True)
    p1.add_argument("--prob", type=float, required=True, help="主观概率 0-1")
    p1.add_argument("--odds", type=float, required=True)
    p1.add_argument("--conf", default="中", help="高/中/低")
    p1.add_argument("--reasons", default="", help="分号分隔的核心理由")
    p1.add_argument("--date", default=None)
    p1.add_argument("--file", default="records.json")
    p1.set_defaults(func=cmd_log)

    p2 = sub.add_parser("settle")
    p2.add_argument("--id", type=int, required=True)
    p2.add_argument("--result", required=True)
    p2.add_argument("--note", default=None, help="比赛关键事件,失败归因素材")
    p2.add_argument("--file", default="records.json")
    p2.set_defaults(func=cmd_settle)

    p3 = sub.add_parser("report")
    p3.add_argument("--file", default="records.json")
    p3.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
