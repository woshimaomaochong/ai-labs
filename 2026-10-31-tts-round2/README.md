# 配音第二期：Audio8-TTS、BreezyVoice 加入对比（2026-10-31）

视频：观众点名的两款开源配音，念长段全翻车；数字写成汉字真管用
被测项目：https://github.com/Edge0-AI/Audio8_TTS 、https://github.com/mtkresearch/BreezyVoice ，加上期的 VoxCPM2、Qwen3-TTS、CosyVoice3 和豆包
听写裁判：https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B

## 实验
- 框架同上一期（`lab/harness.py`），新增 `run_audio8.py`、`run_breezy.py`。这期统一克隆 CosyVoice 官方示例录音（评论区观众的建议）。
- `lab/runv2.sh`：一键跑各模型。`lab/summary.py`：汇总翻车次数、念错率、数字写法对比。
- 数字写法：同一稿子数字写阿拉伯数字和写成汉字各跑一遍（评论区观众的问题），比较念错率。结果在 `lab/eval_v2a*/scores.json`。
- `nemo/cross.py`：Paraformer 和 Nemotron 两个听写员对同一批配音按同一把尺子打分，看是否一致。
- `nemo/diar.py`：Nemotron 说话人分辨（抢话、背景人声）的打分。

## 边界
每个模型每段新闻念 15 遍，只测了中文。
