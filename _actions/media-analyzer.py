#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media-analyzer.py
@about   Модуль проверки комплектности и оптимизации медиа-пакетов.
@purpose Группировка медиа-файлов по манифестам, контроль даты, флага публикации и перенос готового пакета со сжатием в _output.
@author  TechLab
@version 1.0.0
"""

import os
import re
import sys
import shutil
from datetime import datetime, timedelta

def get_vladivostok_date():
    """
    Возвращает текущую дату в часовом поясе Владивостока (UTC+10).
    """
    utc_now = datetime.utcnow()
    vladivostok_now = utc_now + timedelta(hours=10)
    return vladivostok_now.date()

def parse_front_matter(file_path):
    """
    Извлекает Front Matter из .md файла в виде словаря.
    """
    meta = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Ищем блок между первыми двумя тройными дефисами
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if match:
            yaml_block = match.group(1)
            for line in yaml_block.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip().strip('"').strip("'")
                    meta[key] = value
            return meta, content[match.end():]
    except Exception as e:
        print(f"[АНАЛИЗАТОР] ⚠️ Ошибка парсинга Front Matter в '{os.path.basename(file_path)}': {str(e)}")
    return None, None

def mock_compress_photo(source_path, target_path):
    """
    Заготовка для модуля media_compressor_photo.py.
    Пока просто копирует файл, на Шаге 7 здесь развернется Pillow/WebP.
    """
    shutil.copy2(source_path, target_path)
    return os.path.basename(target_path)

def mock_compress_video(source_path, target_path):
    """
    Заготовка для модуля media_compressor_video.py.
    Пока просто копирует файл, на Шаге 7 здесь развернется оптимизация MP4.
    """
    shutil.copy2(source_path, target_path)
    return os.path.basename(target_path)

def analyze_and_process_media():
    print("\n=== [МОДУЛЬ MEDIA-ANALYZER] АНАЛИЗ ПАПКИ _INPUT ===")

    input_dir = os.path.join(os.getcwd(), "_input")
    output_dir = os.path.join(os.getcwd(), "_output")

    if not os.path.exists(input_dir) or not os.path.exists(output_dir):
        print("[АНАЛИЗАТОР] ❌ Ошибка: Целевые директории не найдены.")
        return "ERROR_DIR_NOT_FOUND"

    # Защита от начала нового комплекта, если папка Выход занята
    output_files = sorted(f for f in os.listdir(output_dir) if f.endswith(".md"))
    if output_files:
        print(f"[АНАЛИЗАТОР] Папка _output занята: {len(output_files)} файл(ов). Новый комплект не переносим.")
        return "OUTPUT_BUSY"

    all_files = sorted(os.listdir(input_dir))
    md_files = [f for f in all_files if f.endswith(".md")]

    if not md_files:
        print("[АНАЛИЗАТОР] В директории _input файлы манифестов (.md) отсутствуют.")
        return "NO_FILES"

    current_vl_date = get_vladivostok_date()
    print(f"[АНАЛИЗАТОР] Текущая дата сервера по Владивостоку: {current_vl_date}")

    # Детерминированный поиск первого полностью готового комплекта
    for md_name in md_files:
        md_path = os.path.join(input_dir, md_name)
        meta, body_text = parse_front_matter(md_path)
        
        if not meta or not body_text:
            continue

        # 1. Контроль флага видимости (published)
        published_val = meta.get("published", "false").lower()
        if published_val != "true":
            print(f"[АНАЛИЗАТОР] Манифест '{md_name}' пропущен: опубликован как черновик (published: false).")
            continue

        # 2. Контроль времени (Отложенная публикация)
        date_str = meta.get("date", "").strip()
        if not date_str:
            print(f"[АНАЛИЗАТОР] ⚠️ Манифест '{md_name}' пропущен: отсутствует поле даты.")
            continue
            
        try:
            packet_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if packet_date > current_vl_date:
                print(f"[АНАЛИЗАТОР] Манифест '{md_name}' отложен: дата публикации ({date_str}) еще не наступила.")
                continue
        except Exception:
            print(f"[АНАЛИЗАТОР] ⚠️ Манифест '{md_name}' пропущен: неверный формат даты '{date_str}'.")
            continue

        # 3. Сбор списка упомянутых вложений регулярными выражениями
        raw_attachments = []
        # Находим ![[photo.jpg]] или ![[photo.jpg|300]]
        raw_attachments.extend(re.findall(r"!\[\[(.*?)\]\]", body_text))
        # Находим ![](photo.jpg) или ![описание](photo.jpg)
        raw_attachments.extend(re.findall(r"!\[.*?\]\((.*?)\)", body_text))

        # Очищаем имена файлов от пробелов и обрезаем якоря Obsidian (например, |300)
        attachments = []
        for att in raw_attachments:
            clean_att = att.strip().split("|")[0].strip()
            if clean_att and clean_att not in attachments:
                attachments.append(clean_att)

        # 4. Контроль комплектности файлов на Входе
        bundle_ready = True
        missing_files = []
        for file_name in attachments:
            source_file_path = os.path.join(input_dir, file_name)
            if not os.path.exists(source_file_path):
                bundle_ready = False
                missing_files.append(file_name)

        if not bundle_ready:
            print(f"[АНАЛИЗАТОР] Манифест '{md_name}' не собран. Отсутствуют файлы: {missing_files}. Пропускаем до полной сборки.")
            continue

        # РЕАЛЬНЫЙ ПРОЦЕСС №1: ФИКСАЦИЯ ОБНАРУЖЕНИЯ ГОТОВОГО КОМПЛЕКТА
        teacher = meta.get("teacher", "Unknown").strip()
        discussion = meta.get("discussion_number", "0").strip()
        print(f"[АНАЛИЗАТОР] 🔥 Обнаружен полностью готовый комплект от '{teacher}' для дискуссии №{discussion}!")
        print("[АНАЛИЗАТОР] Поиск завершен. Анализ директории _input остановлен.")

        # Повторная превентивная проверка папки Выход перед физическим переносом
        if sorted(f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))):
            return "OUTPUT_BUSY"

        # РЕАЛЬНЫЙ ПРОЦЕСС №2: СЖАТИЕ, ОПТИМИЗАЦИЯ И ФИЗИЧЕСКИЙ ПЕРЕНОС В _OUTPUT
        updated_body_text = body_text
        
        for file_name in attachments:
            old_path = os.path.join(input_dir, file_name)
            base_ext = os.path.splitext(file_name).lower()
            
            # Извлекаем чистое имя файла (индекс 0)
            clean_name = os.path.splitext(file_name)[0]
            
            if base_ext in [".jpg", ".jpeg", ".png"]:
                new_file_name = f"{clean_name}.webp"
                new_path = os.path.join(output_dir, new_file_name)
                # Вызываем сжатие фото
                final_name = mock_compress_photo(old_path, new_path)
            elif base_ext in [".mp4", ".mov", ".avi"]:
                new_file_name = f"{clean_name}.mp4"
                new_path = os.path.join(output_dir, new_file_name)
                # Вызываем сжатие видео
                final_name = mock_compress_video(old_path, new_path)
            else:
                # Неизвестные типы файлов переносим "как есть"
                new_file_name = file_name
                new_path = os.path.join(output_dir, new_file_name)
                shutil.copy2(old_path, new_path)
                final_name = new_file_name

            # Обновляем имя файла в тексте отчета
            updated_body_text = updated_body_text.replace(file_name, final_name)
            
            # Стираем тяжелый оригинал из папки _input
            if os.path.exists(old_path):
                os.remove(old_path)
                print(f"[АНАЛИЗАТОР] Оптимизирован и удален оригинал: {file_name} -> {final_name}")

        # Сборка финального .md контента с оригинальной YAML-шапкой
        # Восстанавливаем оригинальные метаданные во Front Matter
        meta_lines = ["---"]
        for k, v in meta.items():
            meta_lines.append(f"{k}: {v}")
        meta_lines.append("---\n")
        final_md_content = "\n".join(meta_lines) + updated_body_text

        # Сохраняем готовый .md файл в папку _output
        new_md_path = os.path.join(output_dir, md_name)
        with open(new_md_path, "w", encoding="utf-8") as f:
            f.write(final_md_content)

        # Полностью удаляем старый .md файл из папки _input
        if os.path.exists(md_path):
            os.remove(md_path)
            print(f"[АНАЛИЗАТОР] Манифест {md_name} перенесен в _output и удален со входа.")

        # РЕАЛЬНЫЙ ПРОЦЕСС №3: ФИКСАЦИЯ СТАТУСА УСПЕХА ДЛЯ ДИСПЕТЧЕРА
        status = f"SUCCESS_{teacher}"
        if "GITHUB_ENV" in os.environ:
            with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env_file:
                env_file.write(f"ANALYZER_STATUS={status}\n")

        print(f"[АНАЛИЗАТОР] Финальный статус работы модуля: {status}")
        return status

    print("[АНАЛИЗАТОР] Готовых или открытых по дате комплектов для переноса не обнаружено.")
    if "GITHUB_ENV" in os.environ:
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env_file:
            env_file.write("ANALYZER_STATUS=NO_BUNDLE_READY\n")
    return "NO_BUNDLE_READY"

if __name__ == "__main__":
    status = analyze_and_process_media()
