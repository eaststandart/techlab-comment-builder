#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  comment_builder.py
@about   Главный диспетчер буферного шлюза конструктора комментариев.
@purpose Управление очередью комплектов, ожиданием очистки _output, запуском обработки, Git-коммитами и уведомлением основного сайта.
@author  TechLab
@version 1.0.0
"""

import os
import time
import requests
import subprocess

MAX_BUNDLE_ATTEMPTS = 4
BUNDLE_RETRY_DELAYS_SECONDS = (60, 180, 300)

from comment_processor import run_manifest_processor, run_manifest_analyzer

SITE_API_URL = "https://api.github.com/repos/eaststandart/eaststandart.github.io/dispatches"
CHECK_URL = "https://api.github.com/repos/eaststandart/techlab-comment-builder/contents/_output"
REPOSITORY_BRANCH = "main"
OUTPUT_CHECK_INTERVAL = 60
MAX_OUTPUT_WAIT_SECONDS = 3600


def run_command(command, check=True):
    return subprocess.run(command, check=check, capture_output=True, text=True)


def get_output_media_files():
    output_dir = os.path.join(os.getcwd(), "_output")
    if not os.path.exists(output_dir):
        return []
    return sorted(f for f in os.listdir(output_dir) if f.endswith(".md"))


def sync_repository():
    """Безопасное обновление локальной копии из сети без потери перенесённых файлов."""
    print("[ДИСПЕТЧЕР] Синхронизация локальной копии с GitHub...")
    try:
        run_command(["git", "fetch", "origin", REPOSITORY_BRANCH])
        run_command(["git", "pull", "origin", REPOSITORY_BRANCH, "--rebase"])
        print("[ДИСПЕТЧЕР] Локальная копия синхронизирована.")
        return True
    except Exception as err:
        print(f"[ДИСПЕТЧЕР] Ошибка синхронизации Git: {str(err)}")
        return False


def commit_and_push_manifest_cleanup():
    """Сохраняет изменения _input, выполненные предварительной обработкой."""
    try:
        run_command(["git", "config", "--global", "user.name", "TechLab Comment Bot"])
        run_command(["git", "config", "--global", "user.email", "comment-bot@techlab.local"])
        run_command(["git", "add", "_input"])

        diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if diff_check.returncode == 0:
            print("[ДИСПЕТЧЕР] Предварительная обработка не изменила _input.")
            return True
        if diff_check.returncode != 1:
            raise RuntimeError("Не удалось проверить изменения Git.")

        run_command(["git", "commit", "-m", "предварительная обработка манифестов _input"])
        run_command(["git", "fetch", "origin", REPOSITORY_BRANCH])
        run_command(["git", "pull", "origin", REPOSITORY_BRANCH, "--rebase"])
        run_command(["git", "push", "origin", REPOSITORY_BRANCH])
        print("[ДИСПЕТЧЕР] Изменения предварительной обработки сохранены в GitHub.")
        return True
    except Exception as err:
        print(f"[ДИСПЕТЧЕР] Ошибка сохранения предварительной обработки: {str(err)}")
        return False


def commit_and_push_bundle(teacher_login):
    try:
        run_command(["git", "config", "--global", "user.name", "TechLab Comment Bot"])
        run_command(["git", "config", "--global", "user.email", "comment-bot@techlab.local"])
        run_command(["git", "add", "_input", "_output"])

        diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if diff_check.returncode == 0:
            return False

        run_command(["git", "commit", "-m", f"передано: медиа-комплект {teacher_login} в _output"])
        run_command(["git", "fetch", "origin", REPOSITORY_BRANCH])
        run_command(["git", "pull", "origin", REPOSITORY_BRANCH, "--rebase"])
        run_command(["git", "push", "origin", REPOSITORY_BRANCH])
        return True
    except Exception as err:
        print(f"[ДИСПЕТЧЕР] Ошибка выполнения Git: {str(err)}")
        return False


def notify_site(fine_token):
    if not fine_token:
        return False
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {fine_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    payload = {"event_type": "comment-notify"}
    try:
        response = requests.post(SITE_API_URL, json=payload, headers=headers, timeout=30)
        if response.status_code != 204:
            print(f"[ДИСПЕТЧЕР] Ошибка отправки сигнала. Код: {response.status_code}")
            return False
        print("[ДИСПЕТЧЕР] Сигнал comment-notify передан в репозиторий eaststandart.github.io.")
        return True
    except Exception as err:
        print(f"[ДИСПЕТЧЕР] Исключение при отправке сигнала: {str(err)}")
        return False


def wait_until_output_empty(fine_token):
    start_time = time.time()
    check_counter = 0
    headers = {
        "Authorization": f"token {fine_token}",
        "Accept": "application/vnd.github+json",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    while True:
        check_counter += 1
        elapsed = int(time.time() - start_time)
        print(f"\n[ДИСПЕТЧЕР] Проверка №{check_counter} (Время: {elapsed} сек.)")
        print("[ДИСПЕТЧЕР] Делаем запрос к API techlab-comment-builder для проверки удаления файлов.")

        if elapsed >= MAX_OUTPUT_WAIT_SECONDS:
            print("[ДИСПЕТЧЕР] Превышено максимальное время ожидания очистки _output.")
            return False

        try:
            response = requests.get(CHECK_URL, headers=headers, timeout=30)
            if response.status_code >= 500:
                print(f"[ДИСПЕТЧЕР] ❌ Ошибка сервера GitHub API: {response.status_code}. Пауза 60 сек.")
                time.sleep(60)
                continue

            if response.status_code == 200:
                output_contents = response.json()
                live_files = [item.get("name", "") for item in output_contents if item.get("name", "").endswith(".md")]
                if not live_files:
                    print("[ДИСПЕТЧЕР] Папка _output опустела.")
                    return True
                print(f"[ДИСПЕТЧЕР] Директория содержит файлы ({len(live_files)} шт.): {live_files}")
            elif response.status_code == 404:
                print("[ДИСПЕТЧЕР] Папка _output опустела.")
                return True
            else:
                print(f"[ДИСПЕТЧЕР] ⚠️ Нетипичный ответ API: {response.status_code}. Пауза 60 сек.")
        except Exception as err:
            print(f"[ДИСПЕТЧЕР] ❌ Сетевой сбой API: {str(err)}. Пауза 60 сек.")

        time.sleep(OUTPUT_CHECK_INTERVAL)


def run_control_pipeline():
    print("\n=== [МОДУЛЬ COMMENT-BUILDER] ЗАПУСК ДИСПЕТЧЕРА КОНВЕЙЕРА ===")
    output_dir = os.path.join(os.getcwd(), "_output")
    input_dir = os.path.join(os.getcwd(), "_input")

    if not os.path.exists(output_dir) or not os.path.exists(input_dir):
        print("[ДИСПЕТЧЕР] ❌ Ошибка: целевые директории не найдены.")
        return

    fine_token = os.environ.get("MY_FINE_TOKEN")
    if not fine_token:
        print("[ДИСПЕТЧЕР] ❌ Ошибка: Ключ MY_FINE_TOKEN не найден.")
        return

    bundle_counter = 0
    while True:
        bundle_counter += 1
        print(f"\n--- [ДИСПЕТЧЕР] ЦИКЛ ОБРАБОТКИ КОМПЛЕКТОВ №{bundle_counter} ---")

        if not sync_repository():
            return

        output_files = get_output_media_files()
        if output_files:
            print(f"[ДИСПЕТЧЕР] В _output файлы прошлых смен: {output_files}. Ожидаем очистки.")
            if not wait_until_output_empty(fine_token) or not sync_repository():
                return

        if not run_manifest_processor():
            return

        # Отдельно фиксируем изменения предварительной обработки до запуска анализатора.
        if not commit_and_push_manifest_cleanup():
            return

        analyzer_status = None
        for attempt in range(1, MAX_BUNDLE_ATTEMPTS + 1):
            analyzer_status = run_manifest_analyzer()
            if analyzer_status != "BUNDLE_NOT_READY":
                break

            if attempt < MAX_BUNDLE_ATTEMPTS:
                retry_delay = BUNDLE_RETRY_DELAYS_SECONDS[attempt - 1]
                print(
                    f"[ДИСПЕТЧЕР] Комплект не готов. Повторная попытка "
                    f"{attempt + 1}/{MAX_BUNDLE_ATTEMPTS} через "
                    f"{retry_delay} сек."
                )
                time.sleep(retry_delay)
            else:
                print(
                    f"[ДИСПЕТЧЕР] Комплект не удалось обработать за "
                    f"{MAX_BUNDLE_ATTEMPTS} попытки. Останавливаем обработку."
                )


        if analyzer_status in ("NO_BUNDLE_READY", "NO_FILES"):
            print("[ДИСПЕТЧЕР] Готовых комплектов в директории _input не обнаружено. Процесс контроля успешно завершён.")
            return

        if analyzer_status == "OUTPUT_BUSY":
            if not wait_until_output_empty(fine_token):
                return
            continue

        if analyzer_status.startswith("ERROR_") or not analyzer_status.startswith("SUCCESS_"):
            print(f"[ДИСПЕТЧЕР] Ошибка или неизвестный статус Manifest Analyzer: {analyzer_status}")
            return

        teacher_login = analyzer_status.replace("SUCCESS_", "", 1).strip()
        print(f"[ДИСПЕТЧЕР] Обнаружен готовый комплект для преподавателя: '{teacher_login}'")

        if not commit_and_push_bundle(teacher_login):
            return

        if not notify_site(fine_token):
            print("[ДИСПЕТЧЕР] ⚠️ Предупреждение: Сигнал на сайт не отправлен.")

        if not wait_until_output_empty(fine_token):
            return

        print("[ДИСПЕТЧЕР] Папка _output опустела. Переходим к проверке папки _input на следующий комплект.")
        continue


if __name__ == "__main__":
    run_control_pipeline()
