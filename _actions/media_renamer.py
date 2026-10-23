#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_renamer.py
@about   Выделенный модуль стандартизации имен файлов по правилам CMS.
@purpose Расчет базового префикса, ведение двузначных счетчиков и переименование файлов в _input до сжатия.
@author  TechLab
@version 1.0.0
"""

import os

def standardize_bundle_names(input_dir, meta, body_text, attachments):
    """
    Переименовывает сырые файлы на месте во Входе по порядку их появления в тексте (01, 02...).
    Возвращает: обновленный текст манифеста, список новых имен для переноса и базовый префикс.
    """
    # Извлекаем метаданные для сборки стандартизированного префикса
    date_str = meta.get("date", "").strip()
    discussion = meta.get("discussion_number", "0").strip()
    comment_id = meta.get("comment_id", "").strip()
    teacher = meta.get("teacher", "").strip()
    
    # Резервный подбор логина для веб-интерфейса
    if not teacher:
        teacher = os.environ.get("GITHUB_ACTOR", "WebUser").strip()

    import time
    # Генерируем единый секундный штамп для всего пакета
    timestamp = int(time.time())

    # Сборка базового префикса со штампом строго ПОСЛЕ даты через дефис
    if comment_id:
        base_filename = f"{date_str}-{timestamp}_discussion_{discussion}_comment_{comment_id}_{teacher}"
    else:
        base_filename = f"{date_str}-{timestamp}_discussion_{discussion}_{teacher}"

    updated_body_text = body_text
    final_transfer_list = []
    
    photo_counter = 0
    video_counter = 0

    # Сканируем вложения строго сверху вниз по тексту
    for file_name in attachments:
        old_path = os.path.join(input_dir, file_name)
        base_ext = os.path.splitext(file_name)[1].lower()
        
        # --- СТАНДАРТИЗАЦИЯ ИМЕН ГРАФИКИ ---
        if base_ext in [".jpg", ".jpeg", ".png"]:
            photo_counter += 1
            # Формируем двузначный индекс сортировки (01, 02)
            str_index = f"{photo_counter:02d}"
            
            renamed_raw_name = f"{base_filename}_photo_{str_index}{base_ext}"
            final_webp_name = f"{base_filename}_photo_{str_index}.webp"
            
            # Физически переименовываем сырой оригинал прямо в папке _input/
            os.rename(old_path, os.path.join(input_dir, renamed_raw_name))
            # Подменяем ссылку в тексте манифеста на будущее легкое расширение
            updated_body_text = updated_body_text.replace(file_name, final_webp_name)
            
            # Передаем в анализатор параметры для конвейера сжатия
            final_transfer_list.append((renamed_raw_name, final_webp_name, "photo"))
            
        # --- СТАНДАРТИЗАЦИЯ ИМЕН ВИДЕО ---
        elif base_ext in [".mp4", ".mov", ".avi", ".mkv"]:
            video_counter += 1
            str_index = f"{video_counter:02d}"
            
            renamed_raw_name = f"{base_filename}_video_{str_index}{base_ext}"
            final_webm_name = f"{base_filename}_video_{str_index}.webm"
            
            os.rename(old_path, os.path.join(input_dir, renamed_raw_name))
            updated_body_text = updated_body_text.replace(file_name, final_webm_name)
            
            final_transfer_list.append((renamed_raw_name, final_webm_name, "video"))
        
        # --- ТРАНЗИТ ДЛЯ ОСТАЛЬНЫХ ФАЙЛОВ ---
        else:
            renamed_raw_name = f"{base_filename}_file_{file_name}"
            os.rename(old_path, os.path.join(input_dir, renamed_raw_name))
            updated_body_text = updated_body_text.replace(file_name, renamed_raw_name)
            final_transfer_list.append((renamed_raw_name, renamed_raw_name, "transit"))

    return updated_body_text, final_transfer_list, base_filename
