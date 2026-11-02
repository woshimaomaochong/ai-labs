import sys; sys.path.insert(0, "/work")
import torch
from harness import run, to_np

MID = "/work/models/Audio8-Realistic-0.6b"


class M:
    def load(self):
        from transformers import AutoModel, AutoProcessor
        self.p = AutoProcessor.from_pretrained(MID, trust_remote_code=True)
        self.m = AutoModel.from_pretrained(MID, trust_remote_code=True, dtype=torch.bfloat16).eval().to("cuda")

    def prepare(self, wav, text):
        self.wav, self.text = wav, text

    def synth(self, text):
        # 官方模型卡的零样本克隆写法与默认采样参数
        x = self.p(text=[text], reference_audio=[self.wav], reference_text=[self.text], return_tensors="pt")
        x = {k: v.to("cuda") for k, v in x.items()}
        L = x["prefix_input_ids"].shape[-1] + x["suffix_input_ids"].shape[-1] + int(x["reference_audio_lengths"].max()) // 2048 + 1
        cap = max(256, 2040 - L)  # 模型上下文 2048（文本 + 参考音 + 生成），官方示例 1024 会截断整段新闻
        with torch.inference_mode():
            o = self.m.generate(**x, max_new_tokens=cap, temperature=0.8, top_p=0.95, top_k=50,
                                do_sample=True, return_dict_in_generate=True)
            w, n = self.m.decode_audio(o.codes)
        self.last_cap, self.last_frames = cap, o.codes.shape[-1]
        return to_np(w[0, :int(n[0])]), self.m.config.codec_sample_rate


run("audio8", M())
