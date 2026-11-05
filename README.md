# ai-labs：AI 早知道 · 实测代码

我们在视频里做过的实测，实验脚本、题目和统计结果都放在这里，方便大家复查和复现。

视频在 B 站：https://space.bilibili.com/47563435 ，每期实测和 AI 小课堂都在这里更新。

每个文件夹对应一期视频，文件夹名就是发布日期：

| 文件夹 | 视频 | 测的是 |
|---|---|---|
| [2026-10-14-caveman](2026-10-14-caveman) | 11万星爆款AI技能号称省65%？我们测了324次，结果反转 | caveman 技能到底省不省 Token |
| [2026-10-18-lightpanda](2026-10-18-lightpanda) | 号称比Chrome快9倍的AI浏览器，实测：省内存是真的，快9倍打折 | Lightpanda 和 Chrome 的速度、内存、兼容性 |
| [2026-10-23-frontend-design](2026-10-23-frontend-design) | 官方技能专治AI味？实测60个网页，长出了新套路 | frontend-design 技能做网页的效果 |
| [2026-10-25-mobile-mcp](2026-10-25-mobile-mcp) | 让AI替你点手机：读清单还是看截图？1万星开源工具实测96次 | mobile-mcp：AI 读界面清单还是看截图操作手机 |
| [2026-10-29-voxcpm2](2026-10-29-voxcpm2) | 14秒录音克隆声音？4万星开源配音VoxCPM2对比付费豆包 | VoxCPM2 / Qwen3-TTS / CosyVoice3 / 豆包 声音克隆 |
| [2026-10-31-tts-round2](2026-10-31-tts-round2) | 观众点名的两款开源配音，念长段全翻车；数字写成汉字真管用 | Audio8-TTS、BreezyVoice 加入对比；数字写法；Nemotron 听写当裁判 |
| [2026-11-05-anatomy](2026-11-05-anatomy) | 2万星爆款AI画图技能实测：6万单词的说明书，比得过一句话吗？ | anatomy 技能 vs 不装 vs 只加一句话，画技术概念插图 |

## 说明

- **只有我们自己写的实验代码。** 被测项目本身请到它们的原仓库下载，各文件夹的 README 里有地址。被测技能的说明文件（SKILL.md）也请从原仓库取。
- **陌生项目一律在隔离容器里跑**（服务器上的 Docker，去掉多余权限、只挂实验目录）。脚本里的 `gpu-server` 是 ssh 别名，换成你自己的机器。
- **密钥从环境变量读**：`DEEPSEEK_API_KEY`、`ARK_API_KEY`（火山方舟）、`DOUBAO_APP_ID` / `DOUBAO_ACCESS_KEY`（豆包语音）。Claude 用的是 Claude Code 的 `claude -p` 命令行。
- **没有放的东西**：生成的音频和网页、录屏、对话原文、声音克隆用的参考录音。结果文件只留统计数字。
- 价格、星数、模型版本都是录制当时的，以后可能变。
- 代码是做实验时边测边写的，不算整洁，见谅。

## 许可

MIT License，见 [LICENSE](LICENSE)。
