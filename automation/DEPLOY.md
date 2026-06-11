# 定时任务部署指南 (DEPLOY.md)

把 `weekly_jingcai.py` 部署为无人值守周任务的完整建议。以Linux服务器(crontab)为主,文末附Windows任务计划版。

## 1. 时间点选择

竞彩SP是动态的,自动报告的定位是**初筛**,不是最终决策依据:

| 任务 | 推荐时间 | 理由 |
|---|---|---|
| analyze 分析 | 周五 10:00 | 当天在售场次已更新完毕 |
| review 复盘 | 周一 09:00 | 周日欧洲晚场(北京时间凌晨)结果已全部产生 |

真要投注,临场前务必人工核实最新SP与首发名单——这一步自动化无法替代。

**时区检查(常见坑):** 先跑 `timedatectl` 确认服务器时区。若是UTC,cron时间需减8小时(北京时间周五10:00 = UTC周五02:00)。

## 2. 部署步骤

```bash
# 拉取代码
cd /opt && git clone https://github.com/JamesMake520/jingcai-football.git
cd jingcai-football && mkdir -p logs reports

# 配置密钥(.env已在.gitignore中,不会被推送)
cat > automation/.env << 'EOF'
JC_API_BASE=https://你的中转站/v1
JC_API_KEY=sk-xxxx
JC_MODEL=deepseek-chat
JC_PUSH_KEY=你的Server酱SendKey
JC_WORKDIR=/opt/jingcai-football
EOF
chmod 600 automation/.env   # 仅所有者可读

# 手动跑一次验证全链路(接口→LLM→落盘→推送)
cd automation && python3 weekly_jingcai.py analyze
```

**密钥纪律:** 不要把key写进crontab(`crontab -l`对登录者可见),统一放`.env`。建议在API中转站后台为此用途单独建key并设额度上限——万一接口解析异常导致超长内容进prompt,有上限就不会失血。

## 3. crontab(含可靠性三件套)

`crontab -e` 加入:

```bash
0 10 * * 5 cd /opt/jingcai-football/automation && flock -n /tmp/jc_analyze.lock python3 weekly_jingcai.py analyze >> ../logs/analyze.log 2>&1
0 9 * * 1 cd /opt/jingcai-football/automation && flock -n /tmp/jc_review.lock python3 weekly_jingcai.py review >> ../logs/review.log 2>&1
```

三件套说明:
- **日志落盘** `>> logs/*.log 2>&1`:出问题有据可查
- **flock防重入**:上次任务卡死未退出时,不会叠加起新进程
- **失败告警**:脚本内置——任何异常会通过Server酱推送"任务失败"到微信。定时任务最怕的不是失败,是**静默失败**(你以为在跑,其实早断了)

## 4. 教训库的单一数据源原则

服务器复盘任务会产出 `lessons.md` 的更新**建议**,但不要让服务器自动改文件自动commit。LLM自动写入的教训未经把关,长期会被噪声污染。

正确流程: 周一复盘报告推送到微信 → **人工审核归因是否成立** → 认可的才在本地更新lessons.md并push → 服务器 `git pull` 同步。人在回路是进化机制不跑偏的保险。

## 5. 关于GitHub Actions

技术上可用workflow定时跑,但本项目不推荐:公开仓库的Actions日志任何人可见(暴露投注倾向);且runner在海外,访问竞彩接口不稳定。境内服务器crontab是更稳的方案。

## 6. 使用纪律(比所有技术建议都重要)

定时推送会制造"该买点什么"的默认节奏。请在行动前给自己立机械规则,例如:
- 只跟 EV>8% 且置信度高的推荐;一周一注没有,很正常
- 复盘ROI连续4周为负 → 停一个月
- 让自动化服务于纪律,而不是服务于频率

本系统每周占用的时间应以分钟计。理性购彩,量力而行。

---

## 附: Windows任务计划版

```powershell
schtasks /create /tn "竞彩周分析" /tr "python F:\workspace\jingcai-football\automation\weekly_jingcai.py analyze" /sc weekly /d FRI /st 10:00
schtasks /create /tn "竞彩周复盘" /tr "python F:\workspace\jingcai-football\automation\weekly_jingcai.py review" /sc weekly /d MON /st 09:00
```

Windows下`.env`同样放在`automation/`目录,脚本会自动加载。注意Windows方案依赖电脑开机,长期建议迁移到云服务器。
