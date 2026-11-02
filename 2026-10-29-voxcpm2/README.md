# VoxCPM2 / Qwen3-TTS / CosyVoice3 / 豆包：声音克隆对比（2026-10-29）

视频：14秒录音克隆声音？4万星开源配音VoxCPM2对比付费豆包，一家念了11分钟停不下来
被测项目：https://github.com/OpenBMB/VoxCPM 、Qwen3-TTS、CosyVoice3（各自原仓库）；豆包语音合成 2.0（付费接口）

## 实验（开源模型在服务器 4090 的容器里跑，每个模型一个虚拟环境）
- `harness.py`：统一测试框架，每个模型实现 load / prepare(参考录音, 参考原文) / synth(文本)。`run_voxcpm.py`、`run_qwen3.py`、`run_cosy.py` 分别接三个开源模型，`run_doubao.py` 调豆包接口。
- 测试稿：`texts.json`、`texts2.json`（符号句、新闻难读句、真实新闻），`expect2.json` 是带读法的标准答案。
- `evaluate.py`：Paraformer 听写 + 音高统计。`score.py`：按带声调拼音比对算念错率（同音字不算错，型号数字逐位读、按数值读都算对）。
- `spk_sim.py`：CAM++ 声纹相似度。注意 CosyVoice 克隆时也用 CAM++，分数可能偏向它。
- `hang_probe.py`、`hang_acoustic.py`：「行行行」多音字的探查（只做花絮，不是正式结论）。
- 汇总结果：`eval_temp/scores.json`。

## 运行
```
python run_voxcpm.py <参考wav> <参考原文> <输出目录名>
python evaluate.py <输出目录>
python score.py <eval 目录>
```
参考录音请用你自己有权使用的声音。我们用的参考录音不公开。

## 边界
Qwen3-TTS 两次「停不下来」都是念到程序的生成长度上限（655 秒）才被截断。
