# caveman 技能到底省不省 Token（2026-10-14）

视频：11万星爆款AI技能号称省65%？我们测了324次，结果反转
被测项目：https://github.com/JuliusBrussee/caveman（实验用的是 commit 2e08b91 的 SKILL.md，请从原仓库下载，放在本目录命名为 `caveman_SKILL.md`）

## 实验
- 三组对照，只差系统提示：A 不加要求；B 只加一句「请简洁回答。」；C 放 caveman SKILL.md 全文。
- 12 道题（生活 8 + 编程 4，见 `questions.json`，每题事先写好评分要点）。
- 模型：DeepSeek Flash、DeepSeek Pro（`run.py`）、Claude Haiku（`run_claude.py`，`claude -p` 干净会话：换系统提示、不开工具、不读本地设置、空目录运行）。每题每组 3 次，共 324 次回答。
- 质量：另一个 AI 盲评要点覆盖（`judge.py`）。
- 统计：`stats.py` 汇总 Token、费用（按官方标价）、要点得分，结果在 `stats.json`。

## 运行
```
export DEEPSEEK_API_KEY=...
python run.py          # → raw.jsonl
python run_claude.py   # 需要装好 Claude Code
python judge.py        # → judge.jsonl
python stats.py        # → stats.json
```

## 边界
只测了单次问答；长时间写代码时说明会被缓存，结果可能不同。
