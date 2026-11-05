"""Озвучка сценария через ElevenLabs.

    ELEVENLABS_API_KEY=sk_... python video/voice/generate.py yersultan
    ELEVENLABS_API_KEY=sk_... python video/voice/generate.py adi

Ключ берётся только из переменной окружения и нигде не сохраняется.
Каждая часть сценария — отдельный mp3 в video/voice/<голос>/, плюс
склейка full.mp3 с паузами между частями.
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent

VOICES = {
    # Носители казахского из библиотеки ElevenLabs.
    "yersultan": ("Wa1HorICOC58Tie62cWB", "eleven_v3", {"stability": 0.5, "similarity_boost": 0.8, "style": 0.7, "use_speaker_boost": True}),
    "adi": ("wbGUrCE6cHpRbU9idaMy", "eleven_v4", {"stability": 0.35, "similarity_boost": 0.8, "style": 0.7, "use_speaker_boost": True}),
}


def tts(text: str, voice_id: str, model: str, settings: dict, key: str) -> bytes:
    if not model.startswith("eleven_v3"):
        text = text.split("] ", 1)[-1] if text.startswith("[") else text  # теги эмоций — только для v3
    body = json.dumps({"text": text, "model_id": model, "language_code": "kk", "voice_settings": settings}).encode()
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
        data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout)


def main():
    name = sys.argv[1]
    voice_id, model, settings = VOICES[name]
    key = os.environ["ELEVENLABS_API_KEY"]
    parts = json.loads((HERE / "voiceover_kk.json").read_text(encoding="utf-8"))
    out_dir = HERE / name
    out_dir.mkdir(exist_ok=True)
    timings = []

    for part in parts:
        path = out_dir / f"{part['id']}.mp3"
        if not path.exists():
            path.write_bytes(tts(part["text"], voice_id, model, settings, key))
        seconds = duration(path)
        timings.append({"id": part["id"], "seconds": round(seconds, 2), "target": part["target"]})
        print(f"{part['id']}: {seconds:5.1f} с (слот {part['target']} с)")

    # Склейка: каждая часть стоит в начале своего слота сценария.
    inputs, filters, start = [], [], 0.0
    for index, (part, timing) in enumerate(zip(parts, timings)):
        inputs += ["-i", str(out_dir / f"{part['id']}.mp3")]
        delay = int(start * 1000)
        filters.append(f"[{index}:a]adelay={delay}|{delay}[a{index}]")
        start += max(part["target"], timing["seconds"] + 0.5)
    mix = "".join(f"[a{i}]" for i in range(len(parts)))
    filters.append(f"{mix}amix=inputs={len(parts)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[out]")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters),
         "-map", "[out]", "-ar", "44100", "-b:a", "192k", str(out_dir / "full.mp3")],
        check=True,
    )
    (out_dir / "timings.json").write_text(json.dumps(timings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"full.mp3: {duration(out_dir / 'full.mp3'):.1f} с")


if __name__ == "__main__":
    main()
