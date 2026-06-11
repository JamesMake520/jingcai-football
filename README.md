# jingcai-football — 竞彩足球分析 Skill

跨平台AI Agent技能,遵循开放的 SKILL.md 格式。适用于任何支持Agent Skills的工具,也可作为纯提示词手动喂给任意大模型。

## 各平台安装方式

| 平台 | 方法 |
|---|---|
| **Claude.ai / Claude App** | 设置 → Skills(能力)→ 上传 `jingcai-football.skill` 压缩包 |
| **Claude Code** | 解压本文件夹到 `~/.claude/skills/jingcai-football/` |
| **Codex CLI** | 解压到 Codex 的 skills 目录(参考 `codex` 文档的 skills 路径) |
| **OpenClaw** | 解压到其 workspace 的 `skills/` 目录 |
| **Cursor / 其他IDE Agent** | 解压到项目内任意目录,在规则文件(如 `.cursor/rules` 或 AGENTS.md)中加入一行:"涉及足球竞彩分析时,先阅读 ./jingcai-football/SKILL.md 并遵循其流程" |
| **ChatGPT / Gemini / DeepSeek 等无skill机制的对话产品** | 把 `SKILL.md` 全文作为首条消息发送;模型要求读取references时,把对应文件内容粘贴给它 |

## 文件结构

```
jingcai-football/
├── SKILL.md                  # 主流程(模型的入口,含环境能力降级表)
├── jingcai-单文件提示词版.md   # 合并版,直接粘给ChatGPT/DeepSeek/Gemini等对话产品
├── automation/
│   ├── weekly_jingcai.py     # 周任务: 周五自动分析 + 周一自动复盘(零依赖)
│   └── DEPLOY.md             # 定时任务部署指南(crontab/时区/密钥/告警/使用纪律)
├── references/
│   ├── rules.md              # 竞彩五大玩法规则、串关、SP水位
│   ├── analysis.md           # 分析框架与概率估计方法
│   ├── formulas.md           # 手算公式(无代码执行环境时的降级方案)
│   └── lessons.md            # 教训库(进化内存,随复盘更新)
├── scripts/
│   ├── jc_calc.py            # 赔率/EV/凯利/串关/泊松计算(标准库,无第三方依赖)
│   └── track.py              # 预测记录与复盘报告(标准库,无第三方依赖)
└── records.json              # 预测记录(使用后生成,已gitignore,不入库)
```

## 通用性设计

- 两个脚本只用Python标准库,Python 3.8+ 即可运行,无需pip安装任何东西
- 模型无代码执行能力 → SKILL.md会引导其按 `references/formulas.md` 手算
- 模型无联网能力 → SKILL.md会引导其向用户索要数据清单,而非编造
- 进化机制(records.json + lessons.md)是纯文件,不绑定任何平台

## 理性购彩

本skill仅提供分析方法与计算工具,不保证任何预测结果。竞彩长期期望值为负,请量力而行,娱乐为主。
