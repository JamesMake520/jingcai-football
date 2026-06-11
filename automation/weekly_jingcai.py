#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""竞彩周任务自动化 — weekly_jingcai.py
模式照搬 agent_tips_daily.py: 拉数据 → 调LLM → 存markdown → 可选推送

用法:
  python weekly_jingcai.py analyze   # 周五跑: 分析周末赛事
  python weekly_jingcai.py review    # 周一跑: 复盘上周预测

环境变量:
  JC_API_BASE   API地址(默认你的中转站, 如 https://your-relay.com/v1)
  JC_API_KEY    API密钥
  JC_MODEL      模型名(默认 deepseek-chat)
  JC_PUSH_KEY   (可选) Server酱SendKey, 用于微信推送
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

# ===================== 配置 =====================
WORKDIR = Path(os.environ.get("JC_WORKDIR", r"F:\workspace\jingcai"))
SKILL_PROMPT_FILE = WORKDIR / "jingcai-单文件提示词版.md"
RECORDS_FILE = WORKDIR / "records.json"
REPORT_DIR = WORKDIR / "reports"

API_BASE = os.environ.get("JC_API_BASE", "https://api.deepseek.com/v1")
API_KEY = os.environ.get("JC_API_KEY", "")
MODEL = os.environ.get("JC_MODEL", "deepseek-chat")
PUSH_KEY = os.environ.get("JC_PUSH_KEY", "")

# 只分析这些联赛(避免一次塞太多比赛, 控制token)
LEAGUES_FILTER = ["英超", "西甲", "德甲", "意甲", "法甲", "欧冠", "中超"]
MAX_MATCHES = 8  # 每周最多分析场次

# ===================== 数据源 =====================
# 竞彩官方公开接口(历史上长期可用, 若失效需F12抓包 sporttery.cn 更新)
SPORTTERY_API = (
    "https://webapi.sporttery.cn/gateway/jc/football/"
    "getMatchCalculatorV1.qry?poolCode=hhad,had&channel=c"
)


def http_get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_matches():
    """拉取竞彩在售赛程+胜平负/让球SP。返回精简后的比赛列表。"""
    data = http_get_json(SPORTTERY_API)
    matches = []
    try:
        match_list = data["value"]["matchInfoList"]
    except (KeyError, TypeError):
        print("[!] 接口结构变化, 请抓包更新解析逻辑。原始返回已存 raw_api.json")
        (WORKDIR / "raw_api.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return []
    for day in match_list:
        for m in day.get("subMatchList", []):
            league = m.get("leagueAllName", "")
            if LEAGUES_FILTER and not any(k in league for k in LEAGUES_FILTER):
                continue
            had = m.get("had") or {}
            hhad = m.get("hhad") or {}
            matches.append({
                "编号": m.get("matchNumStr", ""),
                "联赛": league,
                "时间": f'{m.get("matchDate","")} {m.get("matchTime","")}',
                "对阵": f'{m.get("homeTeamAllName","")} vs {m.get("awayTeamAllName","")}',
                "胜平负SP": f'{had.get("h","-")}/{had.get("d","-")}/{had.get("a","-")}',
                "让球数": hhad.get("goalLine", "-"),
                "让球SP": f'{hhad.get("h","-")}/{hhad.get("d","-")}/{hhad.get("a","-")}',
            })
    return matches[:MAX_MATCHES]


# ===================== LLM调用 =====================
def call_llm(system_prompt, user_prompt, max_tokens=4000):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,  # 分析任务压低随机性
    }
    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return resp["choices"][0]["message"]["content"]


def push_wechat(title, content_md):
    """Server酱推送到微信(可选)"""
    if not PUSH_KEY:
        return
    data = urllib.parse.urlencode(
        {"title": title, "desp": content_md[:8000]}
    ).encode("utf-8")
    try:
        urllib.request.urlopen(
            f"https://sctapi.ftqq.com/{PUSH_KEY}.send", data=data, timeout=15
        )
        print("[+] 已推送微信")
    except Exception as e:
        print(f"[!] 推送失败: {e}")


# ===================== 任务: 分析 =====================
def task_analyze():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    skill = SKILL_PROMPT_FILE.read_text(encoding="utf-8")

    print("[*] 拉取竞彩赛程与SP...")
    matches = fetch_matches()
    if not matches:
        print("[!] 未获取到比赛, 退出")
        return
    print(f"[+] 获取 {len(matches)} 场目标联赛比赛")

    matches_text = json.dumps(matches, ensure_ascii=False, indent=1)
    user_prompt = f"""今天是{date.today().isoformat()}。以下是本周末竞彩在售比赛及官方SP(来自接口, 真实数据):

{matches_text}

请按skill流程逐场分析。注意:
1. 你无法联网, 伤停/状态信息你没有最新数据 —— 凡是依赖近期信息的判断, 标注"待人工核实"并降低置信度
2. 重点输出: 每场去水隐含概率、你的主观概率(基于赛季实力盘口常识)、EV估算、推荐方向+置信度
3. 最后给出: 本周最值得人工跟进核实的2-3场(说明核实什么信息)
4. 末尾附理性购彩提示"""

    print(f"[*] 调用 {MODEL} 分析中...")
    report = call_llm(skill, user_prompt)

    fname = REPORT_DIR / f"竞彩分析_{date.today().isoformat()}.md"
    fname.write_text(report, encoding="utf-8")
    print(f"[+] 报告已保存: {fname}")
    push_wechat(f"竞彩周报 {date.today().isoformat()}", report)


# ===================== 任务: 复盘 =====================
def task_review():
    if not RECORDS_FILE.exists():
        print("[!] 没有records.json, 无可复盘内容")
        return
    skill = SKILL_PROMPT_FILE.read_text(encoding="utf-8")
    records = RECORDS_FILE.read_text(encoding="utf-8")
    lessons_file = WORKDIR / "lessons.md"
    lessons = lessons_file.read_text(encoding="utf-8") if lessons_file.exists() else "(空)"

    user_prompt = f"""现在执行周复盘。当前预测记录(records.json):

{records}

当前教训库:

{lessons}

任务:
1. 对其中 result 为 null 的记录, 列出比赛清单, 提示我提供赛果(你无法联网)
2. 对已有结果的记录: 计算命中率、Brier分数、模拟ROI、校准度分区(手算, 展示过程)
3. 对每个未中预测做失败归因: 严格区分"判断错误"与"运气波动", 只有判断错误才能进教训观察区
4. 按教训库的收录标准, 输出更新后的完整lessons.md内容(如有变化)
5. 严守纪律: 样本<30注不下结论, <50注不修改分析方法"""

    print(f"[*] 调用 {MODEL} 复盘中...")
    report = call_llm(skill, user_prompt)
    fname = REPORT_DIR / f"竞彩复盘_{date.today().isoformat()}.md"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    fname.write_text(report, encoding="utf-8")
    print(f"[+] 复盘已保存: {fname}")
    push_wechat(f"竞彩复盘 {date.today().isoformat()}", report)


if __name__ == "__main__":
    import urllib.parse  # for push_wechat
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "analyze":
        task_analyze()
    elif cmd == "review":
        task_review()
    else:
        print(__doc__)
