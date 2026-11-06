"""Generate instrumental candidates with MusicGen (local, GPU if available).

Usage: python gen_music.py <out_dir> [count] [seconds]
Needs torch, transformers, soundfile. Writes <out_dir>/take<N>.wav (mono, 32 kHz).
"""
import sys, os
import torch, soundfile as sf
from transformers import AutoProcessor, MusicgenForConditionalGeneration

MODEL = "facebook/musicgen-stereo-small"
PROMPT = ("90s Amiga demoscene tracker module, instrumental action game soundtrack, "
          "heavy distorted electric guitar riffs, driving electric bass, punchy rock drums, "
          "energetic, 140 bpm, minor key, no vocals")

def main():
    out = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 30
    os.makedirs(out, exist_ok=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    proc = AutoProcessor.from_pretrained(MODEL)
    model = MusicgenForConditionalGeneration.from_pretrained(
        MODEL, torch_dtype=torch.float16 if dev == "cuda" else torch.float32).to(dev)
    rate = model.config.audio_encoder.sampling_rate
    tokens = int(seconds * model.config.audio_encoder.frame_rate)
    for n in range(count):
        torch.manual_seed(1000 + n)
        inputs = proc(text=[PROMPT], return_tensors="pt").to(dev)
        audio = model.generate(**inputs, do_sample=True, guidance_scale=3.5,
                               max_new_tokens=tokens)
        mono = audio[0].float().mean(0).cpu().numpy()
        path = os.path.join(out, f"take{n}.wav")
        sf.write(path, mono, rate)
        print(path, len(mono) / rate, "s", flush=True)

if __name__ == "__main__":
    main()
