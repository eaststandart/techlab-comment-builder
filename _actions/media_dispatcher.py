#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_dispatcher.py
@about   Центральный диспетчер медиа-конвейера TechLab.
@purpose Сканирование _input, проверка черновиков/дат, контроль комплектности медиа и архивация.
@author  TechLab
@version 1.0.0
"""

import os
import re
import sys
import yaml
import shutil
from datetime import datetime, timedelta
import media_compressor
import media_publisher

def parse_front_matter(file_content):
    """Парсит YAML Front Matter из начала markdown-файла."""
    front_matter = {}
    body = file_content
    
    # Ищем блок между первой и второй парой тройных дефисов ---
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', file_content, re.DOTALL)
    if match:
        yaml_text = match.group(1)
        body = match.group(2)
        try:
            front_matter = yaml.safe_load(yaml_text) or {}
        except Exception as e:
            print(f"[ДИСПЕТЧЕР] ⚠️ Ошибка парсинга YAML в шапке: {str(e)}")
            
    return front_matter, body

def check_package_completeness(body, input_dir):
    """Проверяет, все ли локальные медиафайлы, упомянутые в тексте, есть в папке."""
    # Регулярные выражения для ссылок Obsidian ![[file.ext]] и классических Markdown ![txt](file.ext)
    obsidian_links = re.findall(r'!\[\[(.*?)\]\]', body)
    markdown_links = re.findall(r'!\[.*?\]\((.*?)\)', body)
    
    # Объединяем списки в один уникальный массив
    all_attachments = list(set(obsidian_links + markdown_links))
    # Отсекаем внешние веб-ссылки, оставляем только локальные имена файлов
    clean_attachments = []
    
    for file_name in all_attachments:
        # Убираем параметры отображения Obsidian вроде ![[photo.jpg|300]]
        clean_name = file_name.split('|')[0].strip()
        if not clean_name.startswith('http://') and not clean_name.startswith('https://'):
            clean_attachments.append(clean_name)
            
    # Проверяем физическое наличие файлов на диске
    missing_files = []
    for file_name in clean_attachments:
        file_path = os.path.join(input_dir, file_name)
        if not os.path.exists(file_path):
            missing_files.append(file_name)
            
    return missing_files, clean_attachments

def main():
    print("\n=== [МЕДИА-ДИСПЕТЧЕР] ЗАПУСК УПРАВЛЯЮЩЕГО КОНВЕЙЕРА ===")
    
    base_dir = os.getcwd()
    input_dir = os.path.join(base_dir, "_input")
    published_dir = os.path.join(base_dir, "_published")
    
    # Гарантируем наличие папки архива
    os.makedirs(published_dir, exist_ok=True)

    if not os.path.exists(input_dir):
        print("[ДИСПЕТЧЕР] ❌ Критическая ошибка: Входная директория _input не найдена.")
        sys.exit(1)

    # Точное определение времени во Владивостоке (UTC+10) для контроля отложенных публикаций
    vladivostok_time = datetime.utcnow() + timedelta(hours=10)
    today_str = vladivostok_time.strftime("%Y-%m-%d")
    print(f"[ДИСПЕТЧЕР] Текущее системное время Владивостока: {today_str}")

    # Сканируем буфер входа строго на наличие .md файлов-манифестов
    md_files = sorted(f for f in os.listdir(input_dir) if f.endswith(".md"))
    if not md_files:
        print("[ДИСПЕТЧЕР] В директории _input файлы Markdown отсутствуют. Очередь пуста.")
        return

    print(f"[ДИСПЕТЧЕР] Обнаружено файлов в очереди на анализ: {len(md_files)}")

    # Поочередно обрабатываем файлы, имитируя логику поштучного шлюза вашего журнала
    for file_name in md_files:
        file_path = os.path.join(input_dir, file_name)
        print(f"\n[ДИСПЕТЧЕР] >>> Анализ файла манифеста: '{file_name}'")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            print(f"[ДИСПЕТЧЕР] ❌ Ошибка чтения файла '{file_name}': {str(e)}")
            continue

        front_matter, body = parse_front_matter(file_content)

        # 1. Проверка флага публикации (CMS-контроль черновиков)
        is_published = front_matter.get("published")
        if is_published is False or str(is_published).lower() == "false":
            print(f"[ДИСПЕТЧЕР] ⏸️ Статус: ЧЕРНОВИК (published: false). Пропускаем файл.")
            continue

        # 2. Контроль даты публикации (Защита отложенных постов)
        target_date = str(front_matter.get("date", "")).strip()
        if target_date and target_date > today_str:
            print(f"[ДИСПЕТЧЕР] 🕒 Статус: ОТЛОЖЕННЫЙ ПОСТ. Дата отчета ({target_date}) еще не наступила во Владивостоке. Пропускаем.")
            continue

        # 3. Жесткая валидация комплектности пакета медиа
        missing_media, required_media = check_package_completeness(body, input_dir)
        if missing_media:
            print(f"[ДИСПЕТЧЕР] 🛑 ОШИБКА КОМПЛЕКТНОСТИ: В тексте заявлены файлы, которых физически нет в папке _input:")
            print(f"            • Отсутствуют: {missing_media}")
            print(f"[ДИСПЕТЧЕР] Обработка пакета '{file_name}' принудительно заблокирована до загрузки всех медиа.")
            continue

        # Собираем технические параметры отчета для логирования и формирования имени
        disc_num = front_matter.get("discussion_number", "unknown")
        teacher = front_matter.get("teacher", "unknown").strip()
        comment_id = front_matter.get("discussion_comment")

        print(f"[ДИСПЕТЧЕР] ✅ Пакет успешно прошел валидацию комплектности!")
        print(f"            • Преподаватель: {teacher}")
        print(f"            • Целевая Дискуссия: №{disc_num}")
        if comment_id:
            print(f"            • Режим: ПЕРЕЗАПИСЬ существующего комментария ID: {comment_id}")
        else:
            print(f"            • Режим: ПУБЛИКАЦИЯ нового комментария")
        print(f"            • Количество медиа в пакете: {len(required_media)} шт.")

        # ЗАПУСК МОДУЛЯ СЖАТИЯ: Пережимаем графику в WebP и обновляем текст манифеста
        try:
            body = media_compressor.process_markdown_attachments(body, input_dir)
            print("[ДИСПЕТЧЕР] ✅ Все локальные медиафайлы успешно оптимизированы конвейером.")
        except Exception as e_comp:
            print(f"[ДИСПЕТЧЕР] ❌ Критическая ошибка при работе компрессора: {str(e_comp)}")
            sys.exit(1)

        # Пересчитываем комплектность, чтобы получить уже новые (.webp) имена файлов для загрузки
        obs_links = re.findall(r'!\[\[(.*?)\]\]', body)
        md_links = re.findall(r'!\[.*?\]\((.*?)\)', body)
        final_media_list = list(set(obs_links + md_links))
        final_media_list = [f for f in final_media_list if not f.startswith('http')]

        # ПООЧЕРЕДНАЯ ЗАГРУЗКА МЕДИАФАЙЛОВ В ОБЛАКО GITHUB
        for media_file in final_media_list:
            clean_media_name = media_file.split('|')[0].strip()
            # Загружаем файл и получаем вечную ссылку user-attachments
            github_url = media_publisher.upload_media_to_github(clean_media_name, input_dir, disc_num)
            
            if github_url:
                # Мгновенно подменяем локальное имя файла на сетевую ссылку в тексте заметки
                body = body.replace(media_file, github_url)
                # Удаляем сжатый файл с диска, так как он уже сохранен в облаке Дискуссий
                media_path = os.path.join(input_dir, clean_media_name)
                if os.path.exists(media_path):
                    os.remove(media_path)
            else:
                print(f"[ДИСПЕТЧЕР] ❌ Критическая ошибка: Не удалось загрузить медиафайл {clean_media_name}. Отмена публикации отчета.")
                sys.exit(1)

        # НАВЕДЕНИЕ ТЕКСТОВОЙ КРАСОТЫ: Формируем шапку и подвал поста для Дискуссий
        day_short_map = {"понедельник": "пн", "вторник": "вт", "среда": "ср", "четверг": "чт", "пятница": "пт", "суббота": "сб", "воскресенье": "вс"}
        try:
            parsed_date = datetime.strptime(clean_date, "%Y-%m-%d")
            # Переводим английский день недели в русский текст
            eng_day = parsed_date.strftime("%A").lower()
            day_translation = {"monday": "понедельник", "tuesday": "вторник", "wednesday": "среда", "thursday": "четверг", "friday": "пятница", "saturday": "суббота", "sunday": "воскресенье"}
            ru_day = day_translation.get(eng_day, "выходной")
        except:
            ru_day = "занятие"
        
        day_suffix = day_short_map.get(ru_day, "вс")
        formatted_date = datetime.strptime(clean_date, "%Y-%m-%d").strftime("%d.%m.%Y")

        # Формируем итоговый текст комментария (Маркдаун жирности через звезды для красоты)
        post_header = f"### 📸 Медиа-материалы творческого процесса за {formatted_date} г. ({day_suffix})\n\n"
        post_footer = f"\n\n---\n*Материалы подготовил и опубликовал преподаватель: **{teacher}***"
        final_comment_text = f"{post_header}{body.strip()}{post_footer}"

        # ФИНАЛЬНАЯ ОТПРАВКА В ДИСКУССИИ (Публикация или Точечная Перезапись)
        pub_success = media_publisher.publish_final_report(disc_num, final_comment_text, comment_id)
        if not pub_success:
            print("[ДИСПЕТЧЕР] ❌ Отказ сервера при публикации финального поста.")
            sys.exit(1)

        print("[ДИСПЕТЧЕР] Запуск этапа архивации...")

        # 4. Формирование детерминированного имени файла по вашему стандарту
        clean_date = target_date if target_date else today_str
        if comment_id:
            archive_name = f"{clean_date}_discussion_{disc_num}_comment_{comment_id}_{teacher}.md"
        else:
            archive_name = f"{clean_date}_discussion_{disc_num}_{teacher}.md"

        archive_path = os.path.join(published_dir, archive_name)

        # Сохранение обновленного отчета в архивную папку _published и очистка входа
        try:
            # Восстанавливаем полный текст отчета с YAML-шапкой
            full_yaml_text = yaml.dump(front_matter, allow_unicode=True, default_flow_style=False)
            reconstructed_content = f"---\n{full_yaml_text}---\n{body}"
            
            # Записываем обновленный файл сразу в архив
            with open(archive_path, "w", encoding="utf-8") as f_arch:
                f_arch.write(reconstructed_content)
                
            # Удаляем отработанный исходник со входа
            os.remove(file_path)

            print(f"[ДИСПЕТЧЕР] 🚀 Пакет успешно обработан! Файл манифеста перенесен в архив:")
            print(f"            • Направление: _published/{archive_name}")
            
            # Логика поштучного шлюза: завершаем работу скрипта после обработки первого готового пакета,
            # чтобы избежать конкуренции, точно так же, как в вашем journal-analyzer.py
            print("[ДИСПЕТЧЕР] Раунд конвейера завершен. Выходим.")
            return "SUCCESS_BUNDLE_PROCESSED"
            
        except Exception as e:
            print(f"[ДИСПЕТЧЕР] ❌ Ошибка при архивации файла отчета: {str(e)}")
            sys.exit(1)

    print("[ДИСПЕТЧЕР] Все доступные файлы в очереди проверены. Готовых к выпуску комплектов нет.")

if __name__ == "__main__":
    main()
