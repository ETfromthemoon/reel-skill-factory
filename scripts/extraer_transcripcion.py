#!/usr/bin/env python3
"""
extraer_transcripcion.py — Convierte un link de reel/short o video local en transcripcion con timestamps.

Pipeline (en orden de preferencia, para no descargar modelos pesados sin necesidad):
  1. Enlaces: yt-dlp baja metadata (caption) + intenta subtitulos automaticos (es/en).
  2. Si hay subtitulos -> se parsean directo (rapido, sin Whisper).
  3. Si no -> yt-dlp baja audio; para video local FFmpeg lo extrae. Whisper transcribe con timestamps.

Salida: imprime un bloque JSON-ish legible y deja archivos en --outdir:
  - reel.info.json     (metadata cruda de yt-dlp)
  - transcripcion.txt  (lineas "[mm:ss] texto")
Si todo falla, devuelve codigo != 0 y un mensaje claro para hacer fallback manual.

Uso:
  python extraer_transcripcion.py "<URL|VIDEO_LOCAL>" [--outdir DIR] [--model small]
         [--lang es] [--cookies-from-browser chrome]

Requisitos: yt-dlp y ffmpeg en PATH. whisper solo si no hay subtitulos.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys


# En Windows la consola usa cp1252 y revienta al imprimir emojis/acentos de la
# transcripcion. Forzamos UTF-8 en stdout/stderr.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def have(tool):
    return shutil.which(tool) is not None


def run(cmd):
    log("·", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def clean_url(url):
    # Quita parametros de tracking que rompen algunas descargas (igsh, utm, etc.)
    return re.split(r"[?&]igsh=|[?&]utm_|[?]si=", url)[0].strip()


def ts_to_seconds(ts):
    # "00:01:23.456" o "00:01:23,456" -> segundos float
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + s


def fmt_mmss(seconds):
    seconds = int(round(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def parse_subs(path):
    """Parsea .vtt o .srt -> lista de (inicio_seg, texto). Deduplica lineas repetidas."""
    raw = open(path, encoding="utf-8", errors="replace").read()
    blocks = []
    last_text = None
    # Captura "HH:MM:SS.mmm --> HH:MM:SS.mmm" y el texto que sigue
    pattern = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*\d{1,2}:\d{2}:\d{2}[.,]\d{3}.*?\n(.*?)(?=\n\n|\Z)",
        re.DOTALL,
    )
    for m in pattern.finditer(raw):
        start = ts_to_seconds(m.group(1))
        text = re.sub(r"<[^>]+>", "", m.group(2))            # quita tags <c> de vtt
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text == last_text:
            continue
        blocks.append((start, text))
        last_text = text
    return blocks


def transcript_lines(blocks):
    return "\n".join(f"[{fmt_mmss(s)}] {t}" for s, t in blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="URL de Reel o ruta de un video local")
    ap.add_argument("--outdir", default="reel_work")
    ap.add_argument("--model", default="small", help="modelo whisper: tiny/base/small/medium")
    ap.add_argument("--lang", default="auto", help="idioma del audio: es/en/auto")
    ap.add_argument("--cookies-from-browser", default=None,
                    help="usa cookies del navegador (chrome/edge/firefox) si el reel pide login")
    ap.add_argument("--cookies", default=None,
                    help="ruta a un cookies.txt (workaround cuando Chrome falla por DPAPI en Windows)")
    args = ap.parse_args()

    local_video = os.path.isfile(args.url)
    if not local_video and not have("yt-dlp"):
        log("ERROR: yt-dlp no esta en PATH. Instala con: pip install -U yt-dlp")
        sys.exit(2)
    if not have("ffmpeg"):
        log("ERROR: ffmpeg no esta en PATH. Necesario para extraer audio.")
        sys.exit(2)

    os.makedirs(args.outdir, exist_ok=True)
    url = os.path.abspath(args.url) if local_video else clean_url(args.url)
    base = os.path.join(args.outdir, "reel")
    cookie_args = []
    if args.cookies:
        cookie_args = ["--cookies", args.cookies]
    elif args.cookies_from_browser:
        cookie_args = ["--cookies-from-browser", args.cookies_from_browser]

    # --- Paso 1: metadata + caption + subtitulos automaticos ---
    if not local_video:
        r = run(["yt-dlp", *cookie_args, "--write-info-json",
                 "--write-auto-subs", "--write-subs", "--sub-langs", "es,en,es-ES,en-US",
                 "--sub-format", "vtt", "--skip-download", "-o", base, url])
        if r.returncode != 0:
            log("AVISO yt-dlp (metadata):", r.stderr[-800:])

    caption = ""
    duration = None
    info_path = base + ".info.json"
    if os.path.exists(info_path):
        try:
            info = json.load(open(info_path, encoding="utf-8", errors="replace"))
            caption = (info.get("description") or info.get("title") or "").strip()
            duration = info.get("duration")
        except Exception as e:
            log("AVISO: no pude leer info.json:", e)

    # --- Paso 2: usar subtitulos si existen ---
    sub_files = [] if local_video else sorted(glob.glob(base + "*.vtt") + glob.glob(base + "*.srt"))
    blocks = []
    fuente = None
    for sf in sub_files:
        try:
            b = parse_subs(sf)
            if b:
                blocks = b
                fuente = f"subtitulos ({os.path.basename(sf)})"
                break
        except Exception as e:
            log("AVISO: no pude parsear", sf, e)

    # --- Paso 3: fallback a Whisper sobre el audio ---
    if not blocks:
        if local_video:
            audio = base + ".wav"
            ra = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", url,
                      "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", audio])
            if ra.returncode != 0 or not os.path.exists(audio):
                log("ERROR: no se pudo extraer el audio del video.")
                log(ra.stderr[-800:])
                sys.exit(1)
        else:
            log("No hay subtitulos utiles -> bajando audio para Whisper...")
            ra = run(["yt-dlp", *cookie_args, "-x", "--audio-format", "mp3",
                      "--audio-quality", "5", "--postprocessor-args", "-ar 16000 -ac 1",
                      "-o", base + ".%(ext)s", url])
            audio = base + ".mp3"
            if ra.returncode != 0 or not os.path.exists(audio):
                log("ERROR: no se pudo descargar el audio.")
                log(ra.stderr[-800:])
                log("\nFALLBACK: pide al usuario que pegue la transcripcion o el caption a mano.")
                if caption:
                    print(json.dumps({"ok": False, "fuente": "solo_caption",
                                      "caption": caption, "transcripcion": ""}, ensure_ascii=False))
                sys.exit(1)

        if not have("whisper"):
            log("ERROR: whisper no esta instalado y no hubo subtitulos.")
            log("Instala con: pip install -U openai-whisper  (o usa fallback manual)")
            sys.exit(3)

        lang_args = [] if args.lang == "auto" else ["--language", args.lang]
        log(f"Transcribiendo con Whisper (modelo {args.model})... la 1ra vez baja el modelo.")
        rw = run(["whisper", audio, "--model", args.model, "--output_format", "srt",
                  "--output_dir", args.outdir, "--verbose", "False", *lang_args])
        if rw.returncode != 0:
            log("ERROR Whisper:", rw.stderr[-800:])
            sys.exit(4)
        srt = sorted(glob.glob(os.path.join(args.outdir, "reel*.srt")))
        if srt:
            blocks = parse_subs(srt[0])
            fuente = f"whisper ({args.model})"

    if not blocks and not caption:
        log("ERROR: no se obtuvo transcripcion ni caption.")
        sys.exit(1)

    transcript = transcript_lines(blocks)
    out_txt = os.path.join(args.outdir, "transcripcion.txt")
    open(out_txt, "w", encoding="utf-8").write(transcript)

    if duration is None and blocks:
        duration = blocks[-1][0]

    # Salida estructurada para que la skill la consuma
    print(json.dumps({
        "ok": True,
        "url": url,
        "fuente": fuente or "solo_caption",
        "duracion_seg": duration,
        "n_segmentos": len(blocks),
        "caption": caption,
        "transcripcion": transcript,
        "archivo_transcripcion": os.path.abspath(out_txt),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
