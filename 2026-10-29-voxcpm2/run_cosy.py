import sys; sys.path.insert(0, "/work"); sys.path += ["/work/CosyVoice", "/work/CosyVoice/third_party/Matcha-TTS"]
import torch
from harness import run, to_np


class M:
    def load(self):
        from cosyvoice.cli.cosyvoice import AutoModel
        self.m = AutoModel(model_dir="/work/models/Fun-CosyVoice3-0.5B")

    def prepare(self, wav, text):
        self.wav, self.text = wav, "You are a helpful assistant.<|endofprompt|>" + text

    def synth(self, text):
        parts = [j["tts_speech"] for j in self.m.inference_zero_shot(text, self.text, self.wav, stream=False)]
        return to_np(torch.cat(parts, dim=1)), self.m.sample_rate


run("cosyvoice3", M())
