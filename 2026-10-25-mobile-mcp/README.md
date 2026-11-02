# mobile-mcp：AI 读清单还是看截图操作手机（2026-10-25）

视频：让AI替你点手机：读清单还是看截图？1万星开源工具实测96次
被测项目：https://github.com/mobile-next/mobile-mcp

## 环境
- 安卓 14 模拟器在本机（不登录任何账号），adb 端口通过 ssh 反向隧道给服务器。
- mobile-mcp 本体只在服务器容器 `mm-lab` 里跑，客户端通过 `ssh gpu-server docker exec -i ...` 用 stdio 接上（`mcp_config.json`、`mcp_client.py`）。`gpu-server` 换成你的 ssh 别名。
- 实验时关掉遥测：`MOBILEMCP_DISABLE_TELEMETRY=1`。

## 实验
- 三组只差一个变量：A 只给界面清单（安卓无障碍元素表），B 只给截图 + 坐标点击，C 两样都给。
- 8 个日常任务（`tasks.py`：深色模式、闹钟、新建联系人、锁屏时间、字体、勿扰、设备名等），每个任务的成败由我们用 adb 读系统设置判定，不看模型自己说成没成功。联系人要求名字在姓名栏、号码在电话栏（任务里的号码是测试用的示例号码）。
- Claude Haiku（`run_claude.py`，`--strict-mcp-config` 只挂这个 MCP）和 DeepSeek Flash（`run_deepseek.py`，自己写的 MCP 客户端），各 3 组 × 8 任务 × 2 轮 = 96 次，上限 40 轮。
- `rerun_contacts.py`：收紧联系人判定后重跑的那部分。`rec_run.py`：录屏用的单次运行。
- 结果：`results.jsonl`（每次的成败、用时、步数、Token、费用；去掉了模型原话）。

## 边界
只测了模拟器和系统自带 App 的简单任务。
