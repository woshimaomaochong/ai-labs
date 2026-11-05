# anatomy 画图技能：装技能 vs 一句话（2026-11-05）

视频：2万星爆款AI画图技能实测：6万单词的说明书，比得过一句话吗？
被测技能：https://github.com/wheresryan22/anatomy（请从原仓库下载 SKILL.md，放到本目录 `src/SKILL.md`；kit、scripts、examples 克隆到容器里的 `/work/anatomy`）

## 实验
- 三组只差一处：A 不装技能；B 装 anatomy（SKILL.md 放进系统提示，技能目录在容器里可读）；C 不装技能，只在要求末尾加一句「请把这个概念画成一台真实的、零件很多的精细等距（isometric）机器：机器怎么动，就代表概念怎么工作。」
- 6 个概念（`concepts.json`，每个附 5 个必讲要点）。模型 Claude Sonnet 5.5，`claude -p` 干净会话。A、B 各两轮，C 一轮，共 30 张图。
- `box_mcp.py`：一个最小 MCP 服务器，把 AI 的 bash / 写文件 / 读文件 / 看图全部转到服务器 Docker 容器里执行（去掉多余权限、只挂实验目录），本机不运行任何 AI 写的代码或技能自带的脚本。`gpu-server` 换成你的 ssh 别名。
- `run.py`：跑实验，记录用时、轮数、工具调用、费用（`results.jsonl`，费用取官方返回的 `total_cost_usd`）。

## 评测
- `lab/shoot.mjs`：在容器里打开每张图，截桌面 / 手机图，记录报错，点按钮、拖动后比对像素看会不会动，数 SVG 图元。`shoot_all.sh` 批量跑。
- `judge.py`：同一概念的三张图随机标成方案 1/2/3，正序、倒序各评一次。裁判 DeepSeek（看图）和 Claude Opus（`claude -p`，只给 Read 工具看匿名图片）。每个要点判 0/1/2，另打「看得懂 / 像实物 / 精致」1~5 分，选最能让普通人看懂的一张。结果在 `judge.jsonl`。
- `stats.py`：汇总，输出 `stats_A_B_C.json`（第 1 轮）、`stats_A2_B2_C.json`（第 2 轮，C 沿用第 1 轮）。
- 技能自带的线头检查（`scripts/lines.mjs`）用来核对 B 组是否达到说明书要求：12 张里 5 张为 0。
- `lab/rec.mjs`：录屏（片子里的画面），只录页面里最大的那张图，三组同一规则。

## 运行
```
export DEEPSEEK_API_KEY=...
python run.py all ABC 2          # 第三个参数是并发数；第四个参数写 2 表示第 2 轮
bash shoot_all.sh
python judge.py deepseek A,B,C
python judge.py claude A,B,C
python stats.py A,B,C
```

## 结果（摘要）
- 「最好懂」共 48 票：C 组 35、A 组 9、B 组 4。看得懂（1~5）：A 3.75、B 2.29、C 3.92。像实物：A 1.26、B 3.25、C 4.83。
- 每张花费：A 约 0.7 元 / 1 分钟；B 约 5 元 / 5 分钟；C 约 6.6 元 / 9 分钟。

## 边界
只测了 Sonnet 5.5，每组每题一两次。没指定深浅色：B 组 12 张里 10 张是黑底，2 张浅色的分数也没明显更高。裁判都是 AI，只代表 AI 的看法。
