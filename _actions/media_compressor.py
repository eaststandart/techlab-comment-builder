#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_compressor.py
@about   Модуль оптимизации медиа-файлов конвейера TechLab.
@purpose Сжатие графики в формат WebP с обходом уже оптимизированных файлов.
@author  TechLab
@version 1.0.0
"""

import os
import re
from PIL import Image

def compress_image_to_webp(file_name, input_dir, quality=80):
    """
    Конвертирует изображение в формат WebP.
    Если файл уже .webp, пропускает его без изменений.
    """
    clean_name = file_name.split('|')[0].strip()
    base_name, ext = os.path.splitext(clean_name)
    
    # 1. ОБХОДНОЙ ФИЛЬТР WEBP: Если картинка уже оптимизирована, отдаем как есть
    if ext.lower() == '.webp':
        print(f"[КОМПРЕССОР] ⏩ Файл '{clean_name}' уже в формате WebP. Пропуск сжатия.")
        return clean_name

    source_path = os.path.join(input_dir, clean_name)
    target_name = f"{base_name}.webp"
    target_path = os.path.join(input_dir, target_name)

    # Защита от сбоя, если файл физически пропал во время раунда
    if not os.path.exists(source_path):
        print(f"[КОМПРЕССОР] ⚠️ Предупреждение: Файл {source_path} не найден для сжатия.")
        return None

    print(f"[КОМПРЕССОР] 🔄 Оптимизация: '{clean_name}' -> '{target_name}' (Качество: {quality}%)")
    
    try:
        # 2. ПРОЦЕСС СЖАТИЯ: Открываем тяжелое фото и сохраняем в легкий WebP
        with Image.open(source_path) as img:
            # Конвертируем в RGB, если исходник в RGBA (например, прозрачный PNG), так как JPEG/WebP любят RGB
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img = img.convert('RGB')
            img.save(target_path, 'WEBP', quality=quality)
            
        # 3. ЗАЧИСТКА ВХОДА: Удаляем оригинальное тяжелое фото
        os.remove(source_path)
        return target_name
        
    except Exception as e:
        print(f"[КОМПРЕССОР] ❌ Ошибка сжатия файла '{clean_name}': {str(e)}")
        return None

def process_markdown_attachments(md_body, input_dir):
    """
    Сканирует текст заметки, находит локальные вложения,
    сжимает их и заменяет имена файлов в тексте на новые .webp имена.
    """
    print("[КОМПРЕССОР] Запуск пакетной обработки графики...")
    
    # Поиск ссылок Obsidian ![[file.ext]] и Markdown ![txt](file.ext)
    obsidian_links = re.findall(r'!\[\[(.*?)\]\]', md_body)
    markdown_links = re.findall(r'!\[.*?\]\((.*?)\)', md_body)
    all_attachments = list(set(obsidian_links + markdown_links))
    
    updated_body = md_body

    for file_name in all_attachments:
        # Отсекаем внешние интернет-ссылки
        if file_name.startswith('http://') or file_name.startswith('https://'):
            continue
            
        # Запускаем конвертер для каждого локального файла
        new_file_name = compress_image_to_webp(file_name, input_dir)
        
        if new_file_name and new_file_name != file_name:
            # Точечно заменяем имя старого файла на .webp в тексте отчета
            updated_body = updated_body.replace(file_name, new_file_name)
            
    return updated_body
