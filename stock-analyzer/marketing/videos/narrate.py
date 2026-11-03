"""Voix off : synthèse scène par scène (Piper), scènes allongées pour suivre la voix, mixage final.
Usage : narrate.py v_xxx.html narration.json voix.onnx sortie.mp4"""
import json, re, subprocess, sys, wave
from pathlib import Path
from piper import PiperVoice, SynthesisConfig

D = Path(__file__).parent
src, texts, model, out = sys.argv[1], json.loads(Path(sys.argv[2]).read_text()), sys.argv[3], sys.argv[4]
body = (D / src).read_text()
scenes = [(float(a), float(b)) for a, b in re.findall(r'data-start="([\d.]+)" data-end="([\d.]+)"', body)]
assert len(scenes) == len(texts), (len(scenes), len(texts))
voice = PiperVoice.load(model)
cfg = SynthesisConfig(length_scale=0.95, noise_scale=0.6, noise_w_scale=0.7)
LEAD, TAIL = 0.35, 0.7
clips, t = [], 0.0
new_body = body
for i, ((a, b), text) in enumerate(zip(scenes, texts)):
    wav = D / f"voice_{i}.wav"
    with wave.open(str(wav), "wb") as w:
        voice.synthesize_wav(text, w, syn_config=cfg)
    with wave.open(str(wav)) as w:
        dur = w.getnframes() / w.getframerate()
    length = max(b - a, LEAD + dur + TAIL)
    new_body = new_body.replace(f'data-start="{a:g}" data-end="{b:g}"', f'data-start="{t:.2f}" data-end="{t + length:.2f}"', 1)
    clips.append((wav, t + LEAD))
    t += length
total = round(t + 0.5, 2)
new_body = re.sub(r"TOTAL=[\d.]+", f"TOTAL={total}", new_body)
tmp = D / src.replace("v_", "v_vo_", 1)
tmp.write_text(new_body)
subprocess.run([sys.executable, str(D / "build.py"), tmp.name], check=True)
html = D / tmp.name.replace("v_vo_", "out_vo_", 1)
silent = D / (Path(out).stem + ".silent.mp4")
subprocess.run(["node", str(D / "make.js"), str(html), str(silent)], check=True)
inputs, delays = [], []
for k, (wav, at) in enumerate(clips):
    inputs += ["-i", str(wav)]
    delays.append(f"[{k + 1}:a]adelay={int(at * 1000)}|{int(at * 1000)}[a{k}]")
mix = ";".join(delays) + ";" + "".join(f"[a{k}]" for k in range(len(clips))) + \
      f"amix=inputs={len(clips)}:normalize=0,aresample=44100,loudnorm=I=-16:TP=-1.5,apad[voice]"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), *inputs, "-filter_complex", mix,
                "-map", "0:v", "-map", "[voice]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ac", "2",
                "-t", str(total), "-movflags", "+faststart", out], check=True)
silent.unlink()
print("ok", out, total, "s")
