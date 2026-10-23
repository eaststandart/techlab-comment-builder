#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_publisher.py
@about   Модуль публикации медиа-отчетов в GitHub Discussions.
@purpose Загрузка файлов через Git-транспорт на сайт и публикация в Дискуссии.
@author  TechLab
@version 1.2.0
"""

import os
import sys
import subprocess
import shutil

# Репозиторий сайта, куда отправляются готовые медиафайлы и посты
TARGET_SITE_REPO = "eaststandart/eaststandart.github.io"

def run_command(cmd, cwd=None):
    """Вспомогательная функция для запуска системных команд."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=cwd, encoding='utf-8')
        return True, res.stdout.strip()
    except subprocess.CalledProcessError as e:
        err = e.stderr.strip() if e.stderr else e.stdout.strip()
        return False, err

def upload_media_to_github(file_name, input_dir, discussion_number):
    """
    Загружает локальный файл напрямую в медиа-архив репозитория сайта.
    Возвращает прямую интернет-ссылку на картинку.
    """
    source_path = os.path.join(input_dir, file_name)
    if not os.path.exists(source_path):
        print(f"[ПУБЛИКАТОР] ⚠️ Файл {file_name} не найден для загрузки.")
        return None

    print(f"[ПУБЛИКАТОР] 📤 Интеграция файла через Git-архив сайта: '{file_name}'...")

    # Создаем временную изолированную папку для клонирования сайта на сервере
    tmp_clone_dir = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "site_clone")
    if os.path.exists(tmp_clone_dir):
        shutil.rmtree(tmp_clone_dir)

    # 1. Клонируем репозиторий основного сайта, используя права администратора
    token = os.environ.get("SITE_WRITE_TOKEN", "")
    clone_url = f"https://{token}@://github.com{TARGET_SITE_REPO}.git"
    
    success, output = run_command(["git", "clone", "--depth", "1", clone_url, tmp_clone_dir])
    if not success:
        print(f"[ПУБЛИКАТОР] ❌ Ошибка клонирования сайта: {output}")
        return None

    # 2. Создаем структуру папки медиа-архива внутри сайта (разбиваем по номерам дискуссий)
    media_rel_dir = os.path.join("assets", "media_ шлюз", f"disc_{discussion_number}")
    media_full_dir = os.path.join(tmp_clone_dir, media_rel_dir)
    os.makedirs(media_full_dir, exist_ok=True)

    # Переносим сжатый файл внутрь папки сайта
    target_path = os.path.join(media_full_dir, file_name)
    shutil.copy2(source_path, target_path)

    # 3. Публикуем файл в репозиторий сайта через Git commit
    try:
        run_command(["git", "config", "user.name", "TechLab Media Bot"], cwd=tmp_clone_dir)
        run_command(["git", "config", "user.email", "media-bot@techlab.local"], cwd=tmp_clone_dir)
        run_command(["git", "add", "."], cwd=tmp_clone_dir)
        
        diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=tmp_clone_dir)
        if diff_check.returncode != 0:
            run_command(["git", "commit", "-m", f"автоматика: добавлен медиафайл {file_name} для дискуссии {discussion_number} [skip ci]"], cwd=tmp_clone_dir)
            run_command(["git", "push", "origin", "main"], cwd=tmp_clone_dir)
            print(f"[ПУБЛИКАТОР] Файл {file_name} успешно зафиксирован в репозитории сайта.")
    except Exception as e_git:
        print(f"[ПУБЛИКАТОР] ❌ Ошибка Git-транспорта медиа: {str(e_git)}")
        return None

    # 4. Формируем прямую интернет-ссылку на файл, по которой его увидят Дискуссии и Obsidian
    # Формат ссылки: https://github.io
    github_cdn_url = f"https://eaststandart.github.io/assets/media_gate/disc_{discussion_number}/{file_name}"
    print(f"[ПУБЛИКАТОР] ✅ Вечная ссылка сформирована: {github_cdn_url}")
    
    # Удаляем локальный оригинал со входа конвейера
    if os.path.exists(source_path):
        os.remove(source_path)
        
    return github_cdn_url

def publish_final_report(discussion_number, comment_text, comment_id=None):
    """Отправляет итоговый сформированный пост в Дискуссии сайта через GitHub CLI."""
    if comment_id:
        print(f"[ПУБЛИКАТОР] 🔄 Запуск КОНТУРА ПЕРЕЗАПИСИ комментария ID: {comment_id}...")
        # Строгий синтаксис редактирования: gh discussion comment <ID> -R repo --edit -b "текст"
        args = ["discussion", "comment", str(comment_id), "-R", TARGET_SITE_REPO, "--edit", "-b", comment_text]
        mode_text = "обновлен"
    else:
        print(f"[ПУБЛИКАТОР] 🚀 Запуск КОНТУРА ПУБЛИКАЦИИ нового поста...")
        # Строгий синтаксис создания: gh discussion comment <номер> -R repo -b "текст"
        args = ["discussion", "comment", str(discussion_number), "-R", TARGET_SITE_REPO, "-b", comment_text]
        mode_text = "создан"

    full_cmd = ["gh"] + args
    result = subprocess.run(full_cmd, capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode == 0:
        print(f"[ПУБЛИКАТОР] 🎉 УСПЕХ! Отчет успешно {mode_text} в Дискуссии №{discussion_number} сайта {TARGET_SITE_REPO}!")
        return True
    else:
        print(f"[ПУБЛИКАТОР] ❌ Критическая ошибка GitHub CLI при финализации поста: {result.stderr.strip()}")
        return False

