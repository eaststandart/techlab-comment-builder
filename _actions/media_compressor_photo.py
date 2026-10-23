#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_compressor_photo.py
@about   Модуль серверного сжатия графических материалов.
@purpose Валидация расширений, пропорциональный ресайз больших фото под HD-стандарт и конвертация в WebP.
@author  TechLab
@version 1.0.1
"""

import os
import shutil
from PIL import Image

# ==============================================================================
# КОНФИГУРАЦИЯ ПАРАМЕТРОВ СЖАТИЯ ГРАФИКИ
# ==============================================================================
MAX_WIDTH = 1280       # Верхний порог ширины фотографии (HD)
MAX_HEIGHT = 720       # Верхний порог высоты фотографии (HD)
WEBP_QUALITY = 80      # Качество сжатия WebP (настраиваемое: 70, 80, 85 и т.д.)

def compress_image_to_webp(source_path, target_path):
    """
    Принимает сырое изображение, выполняет ресайз под рамки 1280x720 и сохраняет как WebP в _output.
    """
    filename = os.path.basename(source_path)
    ext = os.path.splitext(filename).lower()

    # Если файл уже имеет расширение .webp, отправляем в публикатор «как есть»
    if ext == ".webp":
        print(f"[КОМПРЕССОР ФОТО] Файл '{filename}' уже в формате WebP. Копируем без изменений.")
        shutil.copy2(source_path, target_path)
        return filename

    try:
        with Image.open(source_path) as img:
            # Преобразуем изображения с альфа-каналом (PNG) или палитрой в RGB для совместимости
            if img.mode in ("RGBA", "P") or img.mode != "RGB":
                img = img.convert("RGB")

            orig_width, orig_height = img.size

            # Пропорциональный ресайз, чтобы вписать картинку в рамки MAX_WIDTH x MAX_HEIGHT
            if orig_width > MAX_WIDTH or orig_height > MAX_HEIGHT:
                ratio = min(MAX_WIDTH / orig_width, MAX_HEIGHT / orig_height)
                new_width = int(orig_width * ratio)
                new_height = int(orig_height * ratio)
                
                # Используем качественный фильтр Resampling.LANCZOS
                try:
                    resample_filter = Image.Resampling.LANCZOS
                except AttributeError:
                    resample_filter = Image.ANTIALIAS

                img = img.resize((new_width, new_height), resample_filter)
                print(f"[КОМПРЕССОР ФОТО] Сжатие геометрии '{filename}': с {orig_width}x{orig_height} до {new_width}x{new_height}")
            else:
                print(f"[КОМПРЕССОР ФОТО] Геометрия '{filename}' в пределах нормы ({orig_width}x{orig_height}).")

            # Физическое сохранение в WebP с заданной переменной качества
            img.save(target_path, "WEBP", quality=WEBP_QUALITY)
            
        new_filename = os.path.basename(target_path)
        return new_filename

    except Exception as e:
        print(f"[КОМПРЕССОР ФОТО] ⚠️ Ошибка сжатия файла '{filename}': {str(e)}")
        # В случае аварии копируем оригинал "как есть", чтобы не прерывать публикацию всего отчета
        shutil.copy2(source_path, target_path)
        return filename
