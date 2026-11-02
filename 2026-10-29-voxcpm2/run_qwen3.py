import sys; sys.path.insert(0, "/work")
from harness import run, to_np


class M:
    def load(self):
        import torch
        from qwen_tts import Qwen3TTSModel
        self.m = Qwen3TTSModel.from_pretrained("/work/models/Qwen3-TTS-12Hz-1.7B-Base", device_map="cuda:0",
                                               dtype=torch.bfloat16, attn_implementation="sdpa")

    def prepare(self, wav, text):
        self.p = self.m.create_voice_clone_prompt(ref_audio=wav, ref_text=text, x_vector_only_mode=False)

    def synth(self, text):
        wavs, sr = self.m.generate_voice_clone(text=text, language="Chinese", voice_clone_prompt=self.p)
        return to_np(wavs[0]), sr


run("qwen3tts", M())
