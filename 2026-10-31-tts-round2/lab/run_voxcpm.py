import sys; sys.path.insert(0, "/work")
from harness import run, to_np


class M:
    def load(self):
        from voxcpm import VoxCPM
        self.m = VoxCPM.from_pretrained("/work/models/VoxCPM2", load_denoiser=False, optimize=False)

    def prepare(self, wav, text):
        self.wav, self.text = wav, text

    def synth(self, text):
        # 官方「极致克隆」：参考音频 + 逐字原文，同一段也传给 reference_wav_path
        w = self.m.generate(text=text, prompt_wav_path=self.wav, prompt_text=self.text, reference_wav_path=self.wav,
                            cfg_value=2.0, inference_timesteps=10)
        return to_np(w), self.m.tts_model.sample_rate


run("voxcpm2", M())
