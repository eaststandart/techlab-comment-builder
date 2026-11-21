#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_compressor_video.py
@about   Модуль серверного двухрежимного сжатия видеоматериалов.
@purpose Сохранение WebM без повторного кодирования при подходящей геометрии и
         двухрежимное преобразование остальных видео в WebM.
@author  TechLab
@version 1.0.2
"""

import json
import os
import subprocess


MAX_VIDEO_SIDE = 720


def get_video_geometry(path):
    """Возвращает размеры кадра с учётом метаданных поворота."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:stream_tags=rotate:stream_side_data=rotation",
        "-of", "json", path
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise RuntimeError("Видеопоток не найден.")

    stream = streams[0]
    width = int(stream["width"])
    height = int(stream["height"])
    rotation = stream.get("tags", {}).get("rotate")

    for side_data in stream.get("side_data_list", []):
        if "rotation" in side_data:
            rotation = side_data["rotation"]
            break

    if rotation is not None:
        rotation = int(round(float(rotation))) % 360
        if rotation in (90, 270):
            width, height = height, width

    return width, height


def compress_video_to_webm(source_path, target_path):
    """
    WebM в пределах геометрических ограничений оставляет без изменений.
    WebM большего размера уменьшает на месте; другие поддерживаемые видео
    перекодирует в WebM, сохраняя сравнение CRF 25 и 700 kbps.
    Возвращает True для нового файла, "PRESERVED" для WebM и False при ошибке.
    """
    filename = os.path.basename(source_path)
    base_dir = os.path.dirname(source_path)
    is_webm = os.path.splitext(filename)[1].lower() == ".webm"

    tmp_crf_path = os.path.join(base_dir, "tmp_quality_crf.webm")
    tmp_bit_path = os.path.join(base_dir, "tmp_bitrate_700k.webm")

    geo_audio_opts = [
        "-vf", "scale='if(gte(iw,ih),720,-1)':'if(gte(iw,ih),-1,720)',scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "libvorbis",
        "-b:a", "96k",
        "-ac", "1",
        "-strict", "-2",
        "-deadline", "good",
        "-cpu-used", "2",
        "-y"
    ]

    try:
        if is_webm:
            width, height = get_video_geometry(source_path)
            if max(width, height) <= MAX_VIDEO_SIDE:
                print(
                    f"[КОМПРЕССОР ВИДЕО] WebM '{filename}' уже соответствует "
                    f"ограничениям ({width}x{height}); оставляем без изменений."
                )
                return "PRESERVED"
            print(
                f"[КОМПРЕССОР ВИДЕО] WebM '{filename}' превышает ограничение: "
                f"{width}x{height}. Уменьшаем геометрию."
            )

        print(f"[КОМПРЕССОР ВИДЕО] Начинаем двухрежимную обработку '{filename}'...")

        for temp_file in (tmp_crf_path, tmp_bit_path):
            if os.path.exists(temp_file):
                os.remove(temp_file)

        cmd_crf = [
            "ffmpeg", "-i", source_path,
            "-c:v", "libvpx-vp9", "-crf", "25", "-b:v", "0"
        ] + geo_audio_opts + [tmp_crf_path]
        print("[КОМПРЕССОР ВИДЕО] Запуск режима качества CRF 25...")
        subprocess.run(cmd_crf, check=True, capture_output=True)

        cmd_bit = [
            "ffmpeg", "-i", source_path,
            "-c:v", "libvpx-vp9", "-b:v", "700k"
        ] + geo_audio_opts + [tmp_bit_path]
        print("[КОМПРЕССОР ВИДЕО] Запуск режима битрейта 700 kbps...")
        subprocess.run(cmd_bit, check=True, capture_output=True)

        size_crf = os.path.getsize(tmp_crf_path) if os.path.exists(tmp_crf_path) else float("inf")
        size_bit = os.path.getsize(tmp_bit_path) if os.path.exists(tmp_bit_path) else float("inf")

        print(f"[КОМПРЕССОР ВИДЕО] CRF 25: {size_crf} байт; 700 kbps: {size_bit} байт.")
        if size_crf == float("inf") and size_bit == float("inf"):
            raise RuntimeError("Ни один режим FFmpeg не создал выходной файл.")

        winner = tmp_crf_path if size_crf <= size_bit else tmp_bit_path
        loser = tmp_bit_path if winner == tmp_crf_path else tmp_crf_path
        os.replace(winner, target_path)
        if os.path.exists(loser):
            os.remove(loser)

        print(f"[КОМПРЕССОР ВИДЕО] Обработка '{filename}' успешно завершена.")
        return "PRESERVED" if is_webm else True

    except subprocess.CalledProcessError as e:
        print(
            f"[КОМПРЕССОР ВИДЕО] Сбой FFmpeg для '{filename}'. "
            f"Код возврата: {e.returncode}"
        )
        if e.stdout:
            print(f"[КОМПРЕССОР ВИДЕО] STDOUT:\n{e.stdout.decode('utf-8', errors='replace') if isinstance(e.stdout, bytes) else e.stdout}")
        if e.stderr:
            print(f"[КОМПРЕССОР ВИДЕО] STDERR FFmpeg:\n{e.stderr.decode('utf-8', errors='replace') if isinstance(e.stderr, bytes) else e.stderr}")
        return False

    except Exception as e:
        print(
            f"[КОМПРЕССОР ВИДЕО] Ошибка обработки '{filename}': "
            f"{type(e).__name__}: {e}"
        )
        return False

    finally:
        for temp_file in (tmp_crf_path, tmp_bit_path):
            if os.path.exists(temp_file):
                os.remove(temp_file)
