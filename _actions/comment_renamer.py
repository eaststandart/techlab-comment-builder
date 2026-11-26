#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  comment_renamer.py
@about   Модуль стандартизации имён файлов комплекта.
@purpose Формирует общий префикс и двузначную нумерацию вложений по метаданным и порядку ссылок в манифесте, переименовывает исходные файлы в _input репозитория eaststandart/techlab-comment-builder до сжатия.
@author  TechLab
@version 1.0.0
"""

import os
import re
import time

def standardize_bundle_names(input_dir, meta, body_text, attachments):
    """
    Переименовывает сырые файлы на месте во Входе по порядку их появления в тексте (01, 02...).
    Возвращает: обновленный текст манифеста, список новых имен для переноса и базовый префикс.
    """
    # Извлекаем метаданные для сборки стандартизированного префикса
    date_str = meta.get("date", "").strip()
    discussion = meta.get("discussion_number", "0").strip()
    teacher = meta.get("teacher", "").strip()
    
    # Сначала проверяем timestamp в имени исходного манифеста.
    # Имя считается соответствующим формату, только если остальные части
    # полностью совпадают с date, discussion_number и teacher из Frontmatter.
    frontmatter_teacher = teacher
    timestamp = None

    if date_str and discussion and frontmatter_teacher:
        manifest_files = [
            name for name in os.listdir(input_dir)
            if name.lower().endswith(".md")
        ]
        if len(manifest_files) == 1:
            manifest_name = manifest_files[0]
            manifest_pattern = (
                rf"{re.escape(date_str)}-(\d+)_discussion_"
                rf"{re.escape(discussion)}_{re.escape(frontmatter_teacher)}\.md"
            )
            match = re.fullmatch(manifest_pattern, manifest_name)
            if match:
                timestamp = match.group(1)

    # Если имя манифеста не подошло, используем timestamp из Frontmatter.
    if timestamp is None:
        frontmatter_timestamp = meta.get("timestamp", "").strip()
        if frontmatter_timestamp.isdigit():
            timestamp = frontmatter_timestamp

    # Если timestamp нет ни в имени, ни во Frontmatter — генерируем новый.
    if timestamp is None:
        timestamp = str(int(time.time()))

    # Резервный подбор логина для веб-интерфейса.
    # Он используется для имени комплекта, но не для проверки имени исходного манифеста.
    if not teacher:
        teacher = os.environ.get("GITHUB_ACTOR", "WebUser").strip()

    # Проверяем итоговое имя по всем манифестам в _input.
    # Текущий исходный манифест исключаем из проверки.
    input_root = os.path.dirname(input_dir)
    current_manifest_names = {
        name for name in os.listdir(input_dir)
        if name.lower().endswith(".md")
    }
    current_manifest_name = next(iter(current_manifest_names), None)
    for attempt in range(10):
        existing_manifests = {
            name for name in os.listdir(input_root)
            if name.lower().endswith(".md") and name != current_manifest_name
        }
        candidate_name = (
            f"{date_str}-{timestamp}_discussion_{discussion}_{teacher}.md"
        )
        if candidate_name not in existing_manifests:
            break

        print(
            f"[comment_renamer] Имя '{candidate_name}' уже занято в _input. "
            f"Ожидание 1 минуту перед повторной попыткой ({attempt + 1}/10)."
        )
        time.sleep(60)
        timestamp = str(int(time.time()))
    else:
        existing_manifests = {
            name for name in os.listdir(input_root)
            if name.lower().endswith(".md") and name != current_manifest_name
        }
        candidate_name = (
            f"{date_str}-{timestamp}_discussion_{discussion}_{teacher}.md"
        )
        if candidate_name in existing_manifests:
            raise RuntimeError(
                "Не удалось подобрать свободное имя манифеста в _input "
                "за 10 попыток с интервалом 1 минута."
            )

    # Сборка базового префикса без идентификатора комментария
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
        if base_ext in [".jpg", ".jpeg", ".png", ".webp"]:
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
        elif base_ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
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
