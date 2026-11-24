#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_compressor_video.py
@about   Модуль сжатия и преобразования видеофайлов.
@purpose Определяет геометрию и состояние видео, сохраняет подходящие WebM без повторного кодирования и преобразует остальные поддерживаемые видео в WebM при подготовке комплектов репозитория eaststandart/techlab-comment-builder.
@author  TechLab
@version 1.0.0
"""

import json
import os
import subprocess


MAX_VIDEO_SIDE = 854


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


def _is_corrupt_media_error(error_text):
    """Распознаёт только явные признаки повреждённого контейнера."""
    text = (error_text or "").lower()
    signatures = (
        "invalid data found when processing input",
        "moov atom not found",
        "ebml header parsing failed",
    )
    return any(signature in text for signature in signatures)


def _print_mode_result(label, size):
    """Выводит только размер файла после соответствующего режима."""
    if size == float("inf"):
        print(f"[media_compressor_video] {label}: выходной файл не создан.")
    else:
        print(f"[media_compressor_video] {label}: {size} байт.")


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
        "-vf", "scale='if(gte(iw,ih),854,-1)':'if(gte(iw,ih),-1,854)',scale=trunc(iw/2)*2:trunc(ih/2)*2",
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
                    f"[media_compressor_video] WebM '{filename}' уже соответствует "
                    f"ограничениям ({width}x{height}); оставляем без изменений."
                )
                return "PRESERVED"
            print(
                f"[media_compressor_video] WebM '{filename}' превышает ограничение: "
                f"{width}x{height}. Уменьшаем геометрию."
            )

        source_size = os.path.getsize(source_path)
        print(f"[media_compressor_video] Файл: {filename} ({source_size} байт).")

        for temp_file in (tmp_crf_path, tmp_bit_path):
            if os.path.exists(temp_file):
                os.remove(temp_file)

        cmd_crf = [
            "ffmpeg", "-i", source_path,
            "-c:v", "libvpx-vp9", "-crf", "25", "-b:v", "0"
        ] + geo_audio_opts + [tmp_crf_path]
        subprocess.run(cmd_crf, check=True, capture_output=True)

        cmd_bit = [
            "ffmpeg", "-i", source_path,
            "-c:v", "libvpx-vp9", "-b:v", "700k"
        ] + geo_audio_opts + [tmp_bit_path]
        subprocess.run(cmd_bit, check=True, capture_output=True)

        size_crf = os.path.getsize(tmp_crf_path) if os.path.exists(tmp_crf_path) else float("inf")
        size_bit = os.path.getsize(tmp_bit_path) if os.path.exists(tmp_bit_path) else float("inf")

        _print_mode_result("Режим качества (CRF 25)", size_crf)
        _print_mode_result("Режим битрейта (700 kbps)", size_bit)

        if size_crf == float("inf") and size_bit == float("inf"):
            raise RuntimeError("Ни один режим FFmpeg не создал выходной файл.")

        if size_crf <= size_bit:
            winner = tmp_crf_path
            loser = tmp_bit_path
            difference = size_bit - size_crf
            compression = (source_size - size_crf) / source_size * 100 if source_size > 0 else 0
            result_text = f"сжатие {compression:.1f}%" if compression >= 0 else f"увеличение размера {abs(compression):.1f}%"
            print(f"[media_compressor_video] Выбран режим CRF 25 ({result_text}).")
        else:
            winner = tmp_bit_path
            loser = tmp_crf_path
            difference = size_crf - size_bit
            compression = (source_size - size_bit) / source_size * 100 if source_size > 0 else 0
            result_text = f"сжатие {compression:.1f}%" if compression >= 0 else f"увеличение размера {abs(compression):.1f}%"
            print(f"[media_compressor_video] Выбран режим 700 kbps ({result_text}).")

        os.replace(winner, target_path)
        if os.path.exists(loser):
            os.remove(loser)

        print(f"[media_compressor_video] Обработка '{filename}' успешно завершена.")
        return "PRESERVED" if is_webm else True

    except subprocess.CalledProcessError as e:
        stdout_text = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr_text = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        diagnostic_lines = stderr_text.splitlines() + stdout_text.splitlines()
        reason = next(
            (line.strip() for line in diagnostic_lines if _is_corrupt_media_error(line)),
            None
        )
        if not reason:
            reason = next(
                (line.strip() for line in reversed(diagnostic_lines) if line.strip()),
                f"FFmpeg exit code {e.returncode}"
            )
        print(f"[media_compressor_video] Сбой FFmpeg для '{filename}'. Код возврата: {e.returncode}")
        if stdout_text:
            print(f"[media_compressor_video] STDOUT:\n{stdout_text}")
        if stderr_text:
            print(f"[media_compressor_video] STDERR FFmpeg:\n{stderr_text}")
        if _is_corrupt_media_error(reason):
            return f"FILE_CORRUPTED|{filename}|{reason}"
        return f"RETRY|{filename}|{reason}"

    except Exception as e:
        reason = f"{type(e).__name__}: {e}"
        print(f"[media_compressor_video] Ошибка обработки '{filename}': {reason}")
        return f"RETRY|{filename}|{reason}"

    finally:
        for temp_file in (tmp_crf_path, tmp_bit_path):
            if os.path.exists(temp_file):
                os.remove(temp_file)
