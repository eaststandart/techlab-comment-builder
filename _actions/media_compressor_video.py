#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_compressor_video.py
@about   Модуль серверного двухрежимного сжатия видеоматериалов.
@purpose Имитация пресетов HandBrake (CRF vs 700kbps), сравнение веса и конвертация в WebP/VP9.
@author  TechLab
@version 1.0.0
"""

import os
import subprocess

def compress_video_to_webm(source_path, target_path):
    """
    Выполняет двойное кодирование видео (CRF 25 vs 700kbps) через FFmpeg.
    Сравнивает вес получившихся файлов и сохраняет самый маленький.
    Возвращает True в случае успеха, False при критическом сбое.
    """
    filename = os.path.basename(source_path)
    base_dir = os.path.dirname(source_path)
    
    # Временные файлы для проведения теста веса
    tmp_crf_path = os.path.join(base_dir, "tmp_quality_crf.webm")
    tmp_bit_path = os.path.join(base_dir, "tmp_bitrate_700k.webm")
    
    # Базовые параметры геометрии и звука по шаблонам HandBrake (720x480, Opus Mono 96k)
    # Использован качественный пресет кодирования 'slower' и ограничение частоты кадров в 30fps
    geo_audio_opts = [
        "-vf", "scale=w=720:h=480:force_original_aspect_ratio=decrease,sws_flags=swscale",
        "-r", "30",
        "-c:a", "libopus",
        "-b:a", "96k",
        "-ac", "1",
        "-deadline", "good",
        "-cpu-used", "2",
        "-y"
    ]

    try:
        print(f"[КОМПРЕССОР ВИДЕО] Начинаем двухрежимный анализ файла '{filename}'...")

        # ----------------------------------------------------------------------
        # ПРОГОН №1: Шаблон 'webm GitHub' (Постоянное качество CRF=25)
        # ----------------------------------------------------------------------
        cmd_crf = [
            "ffmpeg", "-i", source_path,
            "-c:v", "libvpx-vp9",
            "-crf", "25",
            "-b:v", "0"
        ] + geo_audio_opts + [tmp_crf_path]

        print("[КОМПРЕССОР ВИДЕО] Запуск Прогона №1 (Режим качества: CRF 25)...")
        subprocess.run(cmd_crf, check=True, capture_output=True)

        # ----------------------------------------------------------------------
        # ПРОГОН №2: Шаблон 'webm 700kbps GitHub' (Фиксированный средний битрейт)
        # ----------------------------------------------------------------------
        cmd_bit = [
            "ffmpeg", "-i", source_path,
            "-c:v", "libvpx-vp9",
            "-b:v", "700k"
        ] + geo_audio_opts + [tmp_bit_path]

        print("[КОМПРЕССОР ВИДЕО] Запуск Прогона №2 (Режим потолка битрейта: 700 kbps)...")
        subprocess.run(cmd_bit, check=True, capture_output=True)

        # ----------------------------------------------------------------------
        # ИНТЕЛЛЕКТУАЛЬНЫЙ СРАВНИТЕЛЬНЫЙ АНАЛИЗ ВЕСА
        # ----------------------------------------------------------------------
        size_crf = os.path.getsize(tmp_crf_path) if os.path.exists(tmp_crf_path) else float('inf')
        size_bit = os.path.getsize(tmp_bit_path) if os.path.exists(tmp_bit_path) else float('inf')

        print(f"[КОМПРЕССОР ВИДЕО] Результаты теста веса для '{filename}':")
        print(f"  -> Режим качества (CRF 25): {size_crf} байт")
        print(f"  -> Режим лимита (700 kbps): {size_bit} байт")

        if size_crf == float('inf') and size_bit == float('inf'):
            raise Exception("Ни один из режимов FFmpeg не смог собрать файл.")

        # Выбираем победителя, который весит меньше, и переносим его на финальный путь
        if size_crf <= size_bit:
            print(f"[КОМПРЕССОР ВИДЕО] 🏆 Победа за качеством (CRF 25)! Файл компактнее на {size_bit - size_crf} байт.")
            if os.path.exists(target_path):
                os.remove(target_path)
            os.rename(tmp_crf_path, target_path)
        else:
            print(f"[КОМПРЕССОР ФОТО] 🏆 Победа за лимитом битрейта (700 kbps)! Файл компактнее на {size_crf - size_bit} байт.")
            if os.path.exists(target_path):
                os.remove(target_path)
            os.rename(tmp_bit_path, target_path)

        # Безопасная очистка временных буферов
        if os.path.exists(tmp_crf_path): os.remove(tmp_crf_path)
        if os.path.exists(tmp_bit_path): os.remove(tmp_bit_path)

        print(f"[КОМПРЕССОР ВИДЕО] Конвертация '{filename}' успешно завершена.")
        return True

    except Exception as e:
        print(f"[КОМПРЕССОР ВИДЕО] ⚠️ Сбой оптимизации видео '{filename}': {str(e)}")
        # Чистим временные файлы в случае аварии
        if os.path.exists(tmp_crf_path): os.remove(tmp_crf_path)
        if os.path.exists(tmp_bit_path): os.remove(tmp_bit_path)
        return False
