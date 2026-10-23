#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_publisher.py
@about   Модуль публикации медиа-отчетов в GitHub Discussions.
@purpose Загрузка медиа через контур Issues и публикация в репозиторий сайта с флагом -R.
@author  TechLab
@version 1.1.0
"""

import os
import sys
import subprocess
import re

# Название целевого репозитория, куда отправляются готовые отчеты родителей
TARGET_SITE_REPO = "eaststandart/eaststandart.github.io"

def run_gh_command(args):
    """Безопасно запускает системную команду GitHub CLI."""
    full_cmd = ["gh"] + args
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else e.stdout.strip()
        return False, error_msg

def upload_media_to_github(file_name, input_dir, discussion_number):
    """
    Загружает локальный файл в облако user-attachments GitHub.
    Использует легальный обходной контур Issues текущего репозитория.
    """
    file_path = os.path.join(input_dir, file_name)
    if not os.path.exists(file_path):
        print(f"[ПУБЛИКАТОР] ⚠️ Файл {file_name} не найден для загрузки.")
        return None

    print(f"[ПУБЛИКАТОР] 📤 Загрузка в облако GitHub через буфер задач: '{file_name}'...")
    
    # Легальная команда создания задачи с флагом загрузки файла медиа
    # gh issue create --title "Заголовок" --body "Описание" --attach <путь_к_файлу>
    args = [
        "issue",
        "create",
        "--title", f"Медиа-буфер: {file_name}",
        "--body", "Автоматическая загрузка файла в облако подсистемы.",
        f"--attach={file_path}"
    ]
    
    success, output = run_gh_command(args)
    if not success:
        print(f"[ПУБЛИКАТОР] ❌ Ошибка GitHub CLI при загрузке файла: {output}")
        return None

    # Сканируем вывод команды точным регулярным выражением в поисках вечной ссылки user-attachments
    url_match = re.search(r'https://github\.com/user-attachments/assets/[a-zA-Z0-9\-_]+', output)
    
    if url_match:
        github_url = url_match.group(0)
        print(f"[ПУБЛИКАТОР] ✅ Файл успешно загружен! Ссылка: {github_url}")
        
        # Находим номер созданной задачи в выводе, чтобы мгновенно закрыть её для чистоты
        # Обычно вывод выглядит как: https://github.com
        issue_num_match = re.search(r'/issues/(\d+)', output)
        if issue_num_match:
            issue_num = issue_num_match.group(1)
            # Закрываем и скрываем временную задачу: gh issue close <номер> --reason "completed"
            run_gh_command(["issue", "close", issue_num, "--reason", "completed"])
            
        return github_url
    else:
        print("[ПУБЛИКАТОР] ⚠️ Файл загружен, но регулярное выражение не смогло извлечь интернет-ссылку.")
        return None

def publish_final_report(discussion_number, comment_text, comment_id=None):
    """
    Отправляет итоговый сформированный пост в Дискуссии.
    Принудительно перенаправляет поток в репозиторий сайта через флаг -R.
    """
    if comment_id:
        print(f"[ПУБЛИКАТОР] 🔄 Запуск КОНТУРА ПЕРЕЗАПИСИ комментария ID: {comment_id}...")
        # Команда редактирования: gh discussion edit-comment <ID> -R owner/repo --body "текст"
        args = [
            "discussion", 
            "edit-comment", 
            str(comment_id), 
            "-R", TARGET_SITE_REPO, 
            "--body", comment_text
        ]
        mode_text = "обновлен"
    else:
        print(f"[ПУБЛИКАТОР] 🚀 Запуск КОНТУРА ПУБЛИКАЦИИ нового поста...")
        # Команда создания: gh discussion comment <номер> -R owner/repo --body "текст"
        args = [
            "discussion", 
            "comment", 
            str(discussion_number), 
            "-R", TARGET_SITE_REPO, 
            "--body", comment_text
        ]
        mode_text = "создан"

    success, output = run_gh_command(args)
    if success:
        print(f"[ПУБЛИКАТОР] 🎉 УСПЕХ! Отчет успешно {mode_text} в Дискуссии №{discussion_number} сайта {TARGET_SITE_REPO}!")
        return True
    else:
        print(f"[ПУБЛИКАТОР] ❌ Критическая ошибка GitHub CLI при финализации поста: {output}")
        return False
