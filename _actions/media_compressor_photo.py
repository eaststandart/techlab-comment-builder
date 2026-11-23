#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_compressor_photo.py
@about   Модуль сжатия и преобразования графических файлов.
@purpose Проверяет поддерживаемые форматы изображений, корректирует ориентацию и размеры фотографий и преобразует их в WebP при подготовке комплектов репозитория eaststandart/techlab-comment-builder.
@author  TechLab
@version 1.0.0
"""

import os
from PIL import Image, ImageOps, UnidentifiedImageError

# ==============================================================================
# КОНФИГУРАЦИЯ ПАРАМЕТРОВ СЖАТИЯ ГРАФИКИ
# ==============================================================================
MAX_WIDTH = 1280
MAX_HEIGHT = 720
WEBP_QUALITY = 75


def compress_image_to_webp(source_path, target_path):
    """
    Создаёт WebP для исходных форматов.
    Существующий WebP не перекодирует без необходимости; при превышении геометрии
    уменьшает его на месте.
    Возвращает True для нового файла, "PRESERVED" для WebP и False при ошибке.
    """
    filename = os.path.basename(source_path)
    ext = os.path.splitext(filename)[1].lower()
    is_webp = ext == ".webp"
    temp_path = None
    source_reading = True
    original_size = os.path.getsize(source_path)

    try:
        with Image.open(source_path) as opened:
            opened.load()
            orientation = opened.getexif().get(274, 1)
            img = ImageOps.exif_transpose(opened)
            source_reading = False

            if img.mode in ("RGBA", "P") or img.mode != "RGB":
                img = img.convert("RGB")

            orig_width, orig_height = img.size
            needs_resize = orig_width > MAX_WIDTH or orig_height > MAX_HEIGHT
            orientation_changed = orientation not in (None, 1)

            if is_webp and not needs_resize and not orientation_changed:
                print(
                    f"[media_compressor_photo] WebP '{filename}' уже соответствует "
                    f"ограничениям ({orig_width}x{orig_height}); оставляем без изменений."
                )
                return "PRESERVED"

            if needs_resize:
                ratio = min(MAX_WIDTH / orig_width, MAX_HEIGHT / orig_height)
                new_width = max(1, int(orig_width * ratio))
                new_height = max(1, int(orig_height * ratio))
                try:
                    resample_filter = Image.Resampling.LANCZOS
                except AttributeError:
                    resample_filter = Image.ANTIALIAS
                img = img.resize((new_width, new_height), resample_filter)
            else:
                print(
                    f"[media_compressor_photo] Геометрия '{filename}' в пределах нормы "
                    f"({orig_width}x{orig_height})."
                )

            # Любой результат сначала полностью записывается во временный файл.
            # Исходник или целевой файл заменяется только после успешного сохранения.
            temp_path = (
                source_path + ".tmp.webp"
                if is_webp else target_path + ".tmp.webp"
            )
            img.save(temp_path, "WEBP", quality=WEBP_QUALITY)

        output_path = source_path if is_webp else target_path
        os.replace(temp_path, output_path)
        temp_path = None

        output_size = os.path.getsize(output_path)
        output_width, output_height = img.size
        compression = (original_size - output_size) / original_size * 100 if original_size else 0
        source_format = ext.lstrip(".").upper()
        print(
            f"[media_compressor_photo] Файл: {filename} ({original_size} байт)."
        )
        print(
            f"[media_compressor_photo] {source_format} ({orig_width}×{orig_height}) -> "
            f"WebP ({output_width}×{output_height}): {output_size} байт "
            f"(сжатие {compression:.1f}%)."
        )

        if is_webp:
            return "PRESERVED"

        return True

    except UnidentifiedImageError as e:
        reason = f"{type(e).__name__}: {e}"
        print(f"[media_compressor_photo] Файл повреждён или не читается '{filename}': {reason}")
        return f"FILE_CORRUPTED|{filename}|{reason}"
    except OSError as e:
        reason = f"{type(e).__name__}: {e}"
        if source_reading:
            print(f"[media_compressor_photo] Не удалось декодировать изображение '{filename}': {reason}")
            return f"FILE_CORRUPTED|{filename}|{reason}"
        print(f"[media_compressor_photo] Сбой чтения или записи при обработке '{filename}': {reason}")
        return f"RETRY|{filename}|{reason}"
    except Exception as e:
        reason = f"{type(e).__name__}: {e}"
        print(f"[media_compressor_photo] Временный сбой оптимизации '{filename}': {reason}")
        return f"RETRY|{filename}|{reason}"
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
