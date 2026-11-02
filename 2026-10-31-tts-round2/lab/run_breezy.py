import os, sys
os.chdir("/work/BreezyVoice")  # g2pw 在当前目录找 G2PWModel/
sys.path[:0] = ["/work", "/work/BreezyVoice", "/work/BreezyVoice/third_party/Matcha-TTS"]
import torch
from harness import run, to_np


class M:
    def load(self):
        import opencc
        from g2pw import G2PWConverter
        from single_inference import CustomCosyVoice, get_bopomofo_rare
        from cosyvoice.utils.file_utils import load_wav
        self.cv = CustomCosyVoice("/work/models/BreezyVoice")
        self.g2p, self.rare, self.load_wav = G2PWConverter(), get_bopomofo_rare, load_wav
        self.t2 = opencc.OpenCC("s2twp")  # 官方输入是台湾繁体，我们的题目是简体，先转换

    def prepare(self, wav, text):
        self.prompt = self.load_wav(wav, 16000)
        t = self.cv.frontend.text_normalize_new(self.t2.convert(text), split=False)
        self.ptext = self.rare(t, self.g2p)

    def synth(self, text):
        # 照官方 single_inference：规范化 → 生僻字加注音 → 零样本合成
        t = self.cv.frontend.text_normalize_new(self.t2.convert(text), split=False)
        out = self.cv.inference_zero_shot_no_normalize(self.rare(t, self.g2p), self.ptext, self.prompt)
        return to_np(out["tts_speech"]), 22050


run("breezyvoice", M())
