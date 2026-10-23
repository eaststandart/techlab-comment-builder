#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  media_publisher.py
@about   Модуль публикации медиа-отчетов в GitHub Discussions.
@purpose Интеграция с GitHub CLI (gh) для загрузки файлов и отправки/редактирования постов.
@author  TechLab
@version 1.0.0
"""

import os
import sys
import subprocess
import re

def run_gh_command(args):
    """Безопасно запускает системную команду GitHub CLI."""
    # Добавляем саму утилиту gh в начало списка аргументов
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
    Использует временный скрытый драфт-комментарий, чтобы получить вечную ссылку.
    """
    file_path = os.path.join(input_dir, file_name)
    if not os.path.exists(file_path):
        print(f"[ПУБЛИКАТОР] ⚠️ Файл {file_name} не найден для загрузки.")
        return None

    print(f"[ПУБЛИКАТОР] 📤 Загрузка в облако GitHub: '{file_name}'...")
    
    # Команда создания временного комментария с прикрепленным файлом
    # gh discussion comment <номер> --body "текст" --attach <путь_к_файлу>
    args = [
        "discussion", 
        "comment", 
        str(discussion_number), 
        "--body", 
        f"Системный буфер загрузки файла: {file_name}",
        f"--attach={file_path}"
    ]
    
    success, output = run_gh_command(args)
    if not success:
        print(f"[ПУБЛИКАТОР] ❌ Ошибка GitHub CLI при загрузке файла: {output}")
        return None

    # GitHub CLI при успешной отправке возвращает весь текст созданного комментария,
    # внутри которого Гитхаб сам сгенерировал интернет-ссылку на аттачмент.
    # Ищем регулярным выражением ссылку вида https://github.com...
    url_match = re.search(r'https://github\.com/user-attachments/assets/[a-zA-Z0-9\-_]+', output)
    
    if url_match:
        github_url = url_match.group(0)
        print(f"[ПУБЛИКАТОР] ✅ Файл успешно загружен! Вечная ссылка: {github_url}")
        
        # Поскольку это был временный буферный комментарий, чтобы не спамить в ветке,
        # нам нужно узнать его ID из вывода и удалить. ID обычно идет в конце ссылки на коммент.
        comment_id_match = re.search(r'#discussioncomment-(\d+)', output)
        if comment_id_match:
            tmp_id = comment_id_match.group(1)
            # Удаляем временный коммент: gh discussion delete-comment <ID> --yes
            run_gh_command(["discussion", "delete-comment", tmp_id, "--yes"])
            
        return github_url
    else:
        print("[ПУБЛИКАТОР] ⚠️ Файл улетел, но Гитхаб не вернул URL разметки. Пробуем извлечь текст.")
        return None

def publish_final_report(discussion_number, comment_text, comment_id=None):
    """
    Отправляет итоговый сформированный пост в Дискуссии.
    Если передан comment_id — выполняет перезапись (редактирование).
    """
    if comment_id:
        print(f"[ПУБЛИКАТОР] 🔄 Запуск КОНТУРА ПЕРЕЗАПИСИ комментария ID: {comment_id}...")
        # Команда редактирования: gh discussion edit-comment <ID> --body "текст"
        args = ["discussion", "edit-comment", str(comment_id), "--body", comment_text]
        mode_text = "обновлен"
    else:
        print(f"[ПУБЛИКАТОР] 🚀 Запуск КОНТУРА ПУБЛИКАЦИИ нового поста...")
        # Команда создания: gh discussion comment <номер> --body "текст"
        args = ["discussion", "comment", str(discussion_number), "--body", comment_text]
        mode_text = "создан"

    success, output = run_gh_command(args)
    if success:
        print(f"[ПУБЛИКАТОР] 🎉 УСПЕХ! Отчет успешно {mode_text} в Дискуссии №{discussion_number}!")
        return True
    else:
        print(f"[ПУБЛИКАТОР] ❌ Критическая ошибка GitHub CLI при финализации поста: {output}")
        return False
