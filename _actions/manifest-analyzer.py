#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  manifest-analyzer.py
@about   Модуль проверки комплектности и оптимизации медиа-пакетов.
@purpose Группировка медиа-файлов, сжатие в WebP на месте в _input и чистый перенос в _output.
@author  TechLab
@version 2.0.0
"""

import os
import re
import sys
import shutil
import tempfile
from datetime import datetime, timedelta

# Подключаем оба наших компрессора и модуль стандартизации имен
from media_compressor_photo import compress_image_to_webp
from media_compressor_video import compress_video_to_webm
from comment_renamer import standardize_bundle_names


def finish_status(status):
    """Печатает единый статус для вызывающего процесса и сохраняет его в GitHub Actions."""
    print(f"[АНАЛИЗАТОР] Финальный статус работы модуля: {status}")
    if "GITHUB_ENV" in os.environ:
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env_file:
            env_file.write(f"ANALYZER_STATUS={status}\n")
    return status

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

def analyze_and_process_media():
    print("\n=== [МОДУЛЬ MANIFEST-ANALYZER] АНАЛИЗ ПАПКИ _INPUT ===")

    input_dir = os.path.join(os.getcwd(), "_input")
    output_dir = os.path.join(os.getcwd(), "_output")

    if not os.path.exists(input_dir) or not os.path.exists(output_dir):
        print("[АНАЛИЗАТОР] ❌ Ошибка: Целевые директории не найдены.")
        return finish_status("ERROR_DIR_NOT_FOUND")

    # Защита от начала нового комплекта строго по расширению .md (как в оригинале Журнала)
    output_files = sorted(f for f in os.listdir(output_dir) if f.endswith(".md"))
    if output_files:
        print(f"[АНАЛИЗАТОР] Папка _output занята: {len(output_files)} .md файл(ов). Новый комплект не переносим.")
        return finish_status("OUTPUT_BUSY")

    all_files = sorted(os.listdir(input_dir))
    md_files = [f for f in all_files if f.endswith(".md")]

    if not md_files:
        print("[АНАЛИЗАТОР] В директории _input файлы манифестов (.md) отсутствуют.")
        return finish_status("NO_FILES")

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

        # 3. Сбор вложений из WikiLinks и Markdown-ссылок.
        # Учитываются как встроенные медиа, так и обычные текстовые ссылки.
        # Порядок ссылок сохраняется для последовательной нумерации файлов.
        wiki_link_re = re.compile(r"!?\[\[(.*?)\]\]")
        markdown_link_re = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
        link_matches = []
        for pattern in (wiki_link_re, markdown_link_re):
            link_matches.extend(pattern.finditer(body_text))
        link_matches.sort(key=lambda match: match.start())

        from urllib.parse import unquote

        attachments = []
        for match in link_matches:
            clean_att = match.group(1).strip()
            if clean_att.startswith("<") and clean_att.endswith(">"):
                clean_att = clean_att[1:-1].strip()
            clean_att = clean_att.split("|", 1)[0].strip()
            clean_att = clean_att.split("#", 1)[0].strip()
            clean_att = clean_att.split("?", 1)[0].strip()
            if not clean_att or re.match(
                r"^[a-z][a-z0-9+.-]*://", clean_att, re.IGNORECASE
            ):
                continue

            clean_att = os.path.basename(
                unquote(clean_att.replace("\\", "/"))
            )
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
        print(f"[АНАЛИЗАТОР] 🔥 Обнаружен полностью готовый комплект от '{teacher}'!")
        print("[АНАЛИЗАТОР] Поиск завершен. Анализ директории _input остановлен.")

        # Превентивная локальная проверка перед физическим переносом файлов
        if sorted(f for f in os.listdir(output_dir) if f.endswith(".md")):
            return finish_status("OUTPUT_BUSY")

        # Подготовка выполняется в отдельной временной копии комплекта.
        # До успешной обработки всех файлов содержимое _input не изменяется.
        moved_output = []
        try:
            with tempfile.TemporaryDirectory(
                prefix=".bundle_work_", dir=input_dir
            ) as work_dir:
                work_md_path = os.path.join(work_dir, md_name)
                shutil.copy2(md_path, work_md_path)

                for file_name in attachments:
                    shutil.copy2(
                        os.path.join(input_dir, file_name),
                        os.path.join(work_dir, file_name)
                    )

                updated_body_text, target_files_list, base_filename = standardize_bundle_names(
                    work_dir, meta, body_text, attachments
                )

                final_transfer_list = []
                processing_failed = False
                processing_status = None

                for raw_name, target_name, media_type in target_files_list:
                    raw_path = os.path.join(work_dir, raw_name)
                    target_path = os.path.join(work_dir, target_name)

                    if media_type == "photo":
                        try:
                            result = compress_image_to_webp(raw_path, target_path)
                        except Exception as e:
                            print(f"[АНАЛИЗАТОР] Ошибка обработки фото '{raw_name}': {e}")
                            result = False

                        if isinstance(result, str) and result.startswith(("FILE_CORRUPTED|", "RETRY|")):
                            processing_status = result
                            processing_failed = True
                            break
                        if result is False or not os.path.isfile(target_path):
                            processing_status = f"RETRY|{raw_name}|Целевой файл после обработки не создан."
                            processing_failed = True
                            break

                        final_transfer_list.append(target_name)

                    elif media_type == "video":
                        try:
                            result = compress_video_to_webm(raw_path, target_path)
                        except Exception as e:
                            print(f"[АНАЛИЗАТОР] Ошибка обработки видео '{raw_name}': {e}")
                            result = False

                        if result is False or not os.path.isfile(target_path):
                            print(f"[АНАЛИЗАТОР] Файл '{raw_name}' не обработан.")
                            processing_failed = True
                            break

                        final_transfer_list.append(target_name)

                    else:
                        if not os.path.isfile(raw_path):
                            print(f"[АНАЛИЗАТОР] Файл комплекта '{raw_name}' не найден после стандартизации.")
                            processing_failed = True
                            break
                        final_transfer_list.append(raw_name)

                if processing_failed:
                    print(
                        "[АНАЛИЗАТОР] Комплект не готов. Временные результаты удаляются; "
                        "исходный комплект в _input не изменён."
                    )
                    if processing_status:
                        print(f"[АНАЛИЗАТОР] Причина остановки обработки: {processing_status}")
                        return finish_status(processing_status)
                    return finish_status("RETRY|unknown|Ошибка обработки файла комплекта без подробностей.")

                # Проверяем комплектность результатов до любого переноса в _output.
                missing_results = [
                    name for name in final_transfer_list
                    if not os.path.isfile(os.path.join(work_dir, name))
                ]
                if missing_results:
                    print(f"[АНАЛИЗАТОР] Не найдены готовые файлы: {missing_results}")
                    return finish_status(f"RETRY|{missing_results[0]}|Подготовленный файл результата отсутствует.")

                # Формируем обновлённый манифест только после успешной обработки всех файлов.
                meta_lines = ["---"]
                for k, v in meta.items():
                    meta_lines.append(f"{k}: {v}")
                meta_lines.append("---\n\n")
                final_md_content = "\n".join(meta_lines) + updated_body_text

                final_md_name = f"{base_filename}.md"
                staged_md_path = os.path.join(work_dir, final_md_name)
                with open(staged_md_path, "w", encoding="utf-8") as f:
                    f.write(final_md_content)

                output_names = final_transfer_list + [final_md_name]
                collisions = [
                    name for name in output_names
                    if os.path.exists(os.path.join(output_dir, name))
                ]
                if collisions:
                    print(f"[АНАЛИЗАТОР] В _output уже существуют файлы: {collisions}")
                    return finish_status("ERROR_OUTPUT_COLLISION")

                # Переносим только полностью подготовленный комплект.
                try:
                    for file_name in final_transfer_list:
                        staged_path = os.path.join(work_dir, file_name)
                        output_path = os.path.join(output_dir, file_name)
                        os.replace(staged_path, output_path)
                        moved_output.append((output_path, staged_path))
                        print(f"[АНАЛИЗАТОР] Подготовлен файл комплекта: {file_name}")

                    output_md_path = os.path.join(output_dir, final_md_name)
                    os.replace(staged_md_path, output_md_path)
                    moved_output.append((output_md_path, staged_md_path))
                except Exception:
                    # При сбое переноса убираем уже перемещённые части комплекта из _output.
                    for output_path, staged_path in reversed(moved_output):
                        if os.path.exists(output_path):
                            os.replace(output_path, staged_path)
                    raise

                # Исходники удаляются только после успешной подготовки и переноса всего комплекта.
                for file_name in attachments:
                    source_path = os.path.join(input_dir, file_name)
                    if os.path.exists(source_path):
                        os.remove(source_path)

                os.remove(md_path)
                print(
                    f"[АНАЛИЗАТОР] Полный комплект '{final_md_name}' перемещён в _output."
                )

        except Exception as e:
            print(f"[АНАЛИЗАТОР] Ошибка подготовки комплекта: {type(e).__name__}: {e}")
            return finish_status("ERROR_BUNDLE_PROCESSING")

        # Финальный статус передаётся вызывающему процессу единым способом.
        status = f"SUCCESS_{teacher}"
        return finish_status(status)

    print("[АНАЛИЗАТОР] Готовых или открытых по дате комплектов для переноса не обнаружено.")
    return finish_status("NO_BUNDLE_READY")

if __name__ == "__main__":
    status = analyze_and_process_media()
