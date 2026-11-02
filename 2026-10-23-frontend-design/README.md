# frontend-design 技能做网页（2026-10-23）

视频：官方技能专治AI味？实测60个网页，长出了新套路
被测技能：https://github.com/anthropics/skills（skills/frontend-design，请从原仓库下载 SKILL.md，放在本目录命名为 `frontend-design_SKILL.md`）

## 实验
- `run.py`：同一模型（Claude Sonnet 5.5，`claude -p` 干净会话），A 组只有基础提示词，B 组多附技能原文。30 个需求（15 类，见 `briefs.json`），共 60 个网页。
- `lab/shoot.mjs`、`lab/lh.sh`、`lab/rec.mjs`：在服务器容器里打开网页，桌面和手机截图、axe 无障碍检查、Lighthouse 跑分、录屏。
- `judge.py`：成对盲评。同一题两版随机标成「方案1/方案2」，每对正反各评一次，消除位置偏好。裁判是 DeepSeek 和豆包（看截图）。
- `blind.py`：Claude 当裁判的盲评（拼图 + 打乱顺序），结果在 `blind_scores.json`。
- `analyze.py`：汇总跑分、技能点名的老套路出现次数、盲评胜率、成本和耗时，结果在 `stats.json`。

## 运行
```
export DEEPSEEK_API_KEY=... ARK_API_KEY=...
python run.py <空目录>
# 把 pages/ 拷进容器，跑 lab/ 里的脚本
python judge.py deepseek
python analyze.py
```

## 边界
只测了一个模型，每个需求每边各做一次。AI 裁判的偏好只是 AI 的看法。
