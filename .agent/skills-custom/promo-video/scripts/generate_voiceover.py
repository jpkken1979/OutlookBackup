#!/usr/bin/env python3
"""
Genera voiceover cronometrado para videos promo usando ElevenLabs API.

Uso:
    1. Configurar ELEVEN_LABS_API_KEY como variable de entorno
    2. Editar la lista `sections` con el script de voz
    3. Ejecutar: python generate_voiceover.py

Requisitos:
    - Python 3.x
    - ffmpeg instalado
    - ELEVEN_LABS_API_KEY configurada
"""

import json
import os
import subprocess
import sys
import urllib.request

# Configuración
API_KEY = os.environ.get("ELEVEN_LABS_API_KEY")
VOICE_ID = "XrExE9yKIg1WjnnlVkGX"  # Matilda - Profesional, americana
VIDEO_DURATION = 60  # segundos
OUTPUT_FILE = "voiceover.mp3"

# Configuración de voz para entrega clara y profesional
VOICE_SETTINGS = {
    "stability": 0.65,
    "similarity_boost": 0.85,
    "style": 0.2,
    "use_speaker_boost": True,
}

# Define las secciones del script aquí
# Formato: (tiempo_inicio_segundos, "texto a narrar")
sections = [
    (0, "Every missed call costs you money."),
    (5, "Your service drive is overwhelmed."),
    (9, "Four hours to call back? That's too late."),
    (13, "Customers won't wait."),
    (17, "Introducing Your Product. Turn problems into solutions."),
    (21, "Feature one described here, so you get the benefit."),
    (26, "Feature two described here, so you get the benefit."),
    (31, "Feature three described here, so you get the benefit."),
    (36, "Feature four described here, so you get the benefit."),
    (41, "Feature five described here, so you get the benefit."),
    (46, "The results speak for themselves. Better outcomes. Real results."),
    (52, "Your Product. Your tagline. Request your demo today."),
]


def check_requirements() -> None:
    """Verificar que API key y ffmpeg estén disponibles."""
    if not API_KEY:
        print("Error: ELEVEN_LABS_API_KEY no está configurada")
        print("Configurar con: export ELEVEN_LABS_API_KEY=tu_clave_aqui")
        sys.exit(1)

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg no encontrado. Instalar con: brew install ffmpeg")
        sys.exit(1)


def generate_audio(text: str, filename: str) -> float:
    """Generar audio para una sección de texto usando la API de ElevenLabs."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": VOICE_SETTINGS,
    }
    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        with open(filename, "wb") as f:
            f.write(response.read())

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", filename],
        capture_output=True,
        text=True,
        encoding="utf-8", errors="replace",
    )
    return float(result.stdout.strip())


def create_silence_base(duration: int, filename: str) -> None:
    """Crear archivo de audio silencioso como pista base."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            str(duration),
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            filename,
        ],
        capture_output=True,
    )


def combine_audio_sections(section_files: list[str], start_times: list[float], output: str) -> None:
    """Combinar todas las secciones de audio con timing correcto."""
    inputs = ["-i", "silence_base.mp3"]
    filter_parts = []

    for i, (filename, start_time) in enumerate(zip(section_files, start_times)):
        inputs.extend(["-i", filename])
        delay_ms = int(start_time * 1000)
        filter_parts.append(f"[{i + 1}]adelay={delay_ms}|{delay_ms}[d{i}]")

    mix_inputs = "[0]" + "".join(f"[d{i}]" for i in range(len(section_files)))
    filter_str = (
        ";".join(filter_parts) + f";{mix_inputs}amix=inputs={len(section_files) + 1}:duration=first"
    )

    cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", filter_str, output]
    subprocess.run(cmd, capture_output=True)


def normalize_audio(input_file: str, output_file: str) -> None:
    """Normalizar niveles de audio para volumen consistente."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            input_file,
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            output_file,
        ],
        capture_output=True,
    )


def cleanup(files: list[str]) -> None:
    """Eliminar archivos temporales."""
    for f in files:
        try:
            os.remove(f)
        except OSError:
            pass


def verify_timing_with_whisper(audio_file: str) -> list[dict]:
    """Usar Whisper para transcribir y obtener timestamps reales."""
    try:
        import whisper  # type: ignore[import-untyped]

        print("Transcribiendo con Whisper para verificar timing...")
        model = whisper.load_model("tiny")
        result = model.transcribe(audio_file)
        return result.get("segments", [])
    except ImportError:
        print("  Whisper no instalado. Instalar con: pip install openai-whisper")
        print("  Omitiendo verificación de timing.")
        return []
    except Exception as e:
        print(f"  Error de Whisper: {e}")
        return []


def check_timing_alignment(segments: list[dict], script_sections: list) -> list[str]:
    """Comparar timestamps de Whisper contra timing esperado de escenas."""
    issues = []

    for i, (start_time, text) in enumerate(script_sections):
        next_start = script_sections[i + 1][0] if i + 1 < len(script_sections) else VIDEO_DURATION

        for seg in segments:
            if text[:20].lower() in seg.get("text", "").lower():
                actual_start = seg.get("start", 0)
                actual_end = seg.get("end", 0)

                if actual_start < start_time - 0.5:
                    issues.append(
                        f"Sección {i} empieza muy temprano: esperado {start_time}s, "
                        f"actual {actual_start:.1f}s"
                    )
                if actual_end > next_start:
                    issues.append(
                        f"Sección {i} se superpone con la siguiente: termina en "
                        f"{actual_end:.1f}s, próxima escena en {next_start}s"
                    )
                break

    return issues


def main() -> None:
    """Entry point para generación de voiceover."""
    check_requirements()

    print(f"Generando voiceover con {len(sections)} secciones...")
    print(f"Voz: Matilda (ID: {VOICE_ID})")
    print()

    section_files: list[str] = []
    start_times: list[float] = []
    temp_files = ["silence_base.mp3"]

    for i, (start_time, text) in enumerate(sections):
        filename = f"section_{i:02d}.mp3"
        section_files.append(filename)
        start_times.append(start_time)
        temp_files.append(filename)

        print(f"  [{start_time:2d}s] Generando: {text[:50]}...")
        duration = generate_audio(text, filename)
        print(f"       -> {duration:.1f}s audio")

        if i + 1 < len(sections):
            next_start = sections[i + 1][0]
            if start_time + duration > next_start:
                print(
                    f"       ADVERTENCIA: Puede superponerse con sección siguiente "
                    f"(termina en {start_time + duration:.1f}s, próxima en {next_start}s)"
                )

    print()
    print("Creando pista base silenciosa...")
    create_silence_base(VIDEO_DURATION, "silence_base.mp3")

    print("Combinando secciones...")
    combine_audio_sections(section_files, start_times, "voiceover_raw.mp3")
    temp_files.append("voiceover_raw.mp3")

    print("Normalizando niveles de audio...")
    normalize_audio("voiceover_raw.mp3", OUTPUT_FILE)

    print()
    segments = verify_timing_with_whisper(OUTPUT_FILE)
    if segments:
        print("\nTimestamps de transcripción Whisper:")
        for seg in segments:
            print(f"  {seg['start']:5.1f}s - {seg['end']:5.1f}s: {seg['text'][:60]}")

        issues = check_timing_alignment(segments, sections)
        if issues:
            print("\n" + "=" * 60)
            print("SUPERPOSICIONES DETECTADAS — CORREGIR ANTES DE CONTINUAR")
            print("=" * 60)
            for issue in issues:
                print(f"  - {issue}")
            print("\nOPCIONES DE CORRECCIÓN:")
            print("  1. Acortar el texto que se superpone (hacerlo más conciso)")
            print("  2. Aumentar el tiempo de inicio de la sección siguiente")
            print("  3. Agregar '...' para crear pausas naturales")
            print("\nVolver a generar y verificar. NO continuar con superposiciones.")
            print("=" * 60)
        else:
            print("\nTIMING VERIFICADO — Sin superposiciones detectadas")

    print("Limpiando archivos temporales...")
    cleanup(temp_files)

    print()
    print(f"¡Éxito! Guardado en: {OUTPUT_FILE}")
    print()
    print("Próximos pasos:")
    print("  1. Si se detectaron problemas de timing, ajustar sections[] y ejecutar de nuevo")
    print("  2. Agregar música de fondo:")
    print(f"     ffmpeg -y -i {OUTPUT_FILE} -i music.mp3 \\")
    print(
        '       -filter_complex "[1:a]volume=0.15,afade=t=in:st=0:d=2,'
        'afade=t=out:st=57:d=3[music];[0:a][music]amix=inputs=2:duration=first" \\'
    )
    print("       voiceover-with-music.mp3")
    print("  3. Combinar con video:")
    print(
        "     ffmpeg -y -i video.mp4 -i voiceover-with-music.mp3 "
        "-c:v copy -map 0:v:0 -map 1:a:0 final.mp4"
    )


if __name__ == "__main__":
    main()
