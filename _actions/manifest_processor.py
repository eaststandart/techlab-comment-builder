#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  manifest_processor.py
@about   Предварительная обработка манифестов и файлов в _input.
@purpose Проверка published, сохранение связанных вложений и удаление неподготовленных комплектов и бесхозных файлов.
@author  TechLab
@version 1.0.0
"""

import os
import re
import sys
from urllib.parse import unquote

INPUT_DIR = os.path.join(os.getcwd(), "_input")
STANDARD_MANIFEST_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})-(\d+)_discussion_(\d+)_(.+)\.md$",
    re.IGNORECASE,
)
FRONT_MATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)",
    re.DOTALL,
)
WIKILINK_RE = re.compile(r"!?\[\[(.*?)\]\]")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def extract_attachments(text):
    """Извлекает локальные имена файлов из WikiLinks и Markdown-ссылок."""
    attachments = set()
    raw_links = WIKILINK_RE.findall(text)
    raw_links.extend(MARKDOWN_LINK_RE.findall(text))

    for raw_link in raw_links:
        link = raw_link.strip()
        if not link:
            continue
        if link.startswith("<") and link.endswith(">"):
            link = link[1:-1].strip()
        link = link.split("|", 1)[0].strip()
        link = link.split("#", 1)[0].strip()
        link = link.split("?", 1)[0].strip()
        if not link or re.match(r"^[a-z][a-z0-9+.-]*://", link, re.IGNORECASE):
            continue
        filename = os.path.basename(unquote(link.replace("\\", "/")))
        if filename:
            attachments.add(filename)

    return attachments


def read_manifest(path):
    """Читает только published из Front Matter и извлекает ссылки из тела."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            content = file.read()
    except Exception as error:
        return "invalid", set(), f"ошибка чтения: {error}"

    match = FRONT_MATTER_RE.match(content)
    if not match:
        return "invalid", extract_attachments(content), "Front Matter отсутствует или повреждён"

    published_values = re.findall(
        r"^\s*published\s*:\s*(.*?)\s*$",
        match.group(1),
        re.IGNORECASE | re.MULTILINE,
    )
    if len(published_values) != 1:
        return "invalid", extract_attachments(content[match.end():]), "свойство published отсутствует или задано неоднозначно"

    value = published_values[0].strip().strip("\\\"'").lower()
    if value not in ("true", "false", "delete"):
        return "invalid", extract_attachments(content[match.end():]), f"недопустимое значение published: {value!r}"

    return value, extract_attachments(content[match.end():]), None


def standard_bundle_files(manifest_name, input_files):
    """Возвращает файлы с префиксом стандартного имени манифеста."""
    if not STANDARD_MANIFEST_RE.match(manifest_name):
        return set()
    prefix = os.path.splitext(manifest_name)[0] + "_"
    return {name for name in input_files if name.startswith(prefix)}


def process_manifests():
    print("\n=== [МОДУЛЬ MANIFEST-PROCESSOR] ОБРАБОТКА _INPUT ===")

    if not os.path.isdir(INPUT_DIR):
        print(f"[МАНИФЕСТ] Ошибка: каталог не найден: {INPUT_DIR}")
        return 1

    input_files = {
        name for name in os.listdir(INPUT_DIR)
        if os.path.isfile(os.path.join(INPUT_DIR, name))
    }
    manifest_names = sorted(
        name for name in input_files if name.lower().endswith(".md")
    )

    manifests = {}
    for name in manifest_names:
        status, attachments, reason = read_manifest(os.path.join(INPUT_DIR, name))
        manifests[name] = {
            "status": status,
            "reason": reason,
            "attachments": attachments,
            "standard_files": standard_bundle_files(name, input_files),
            "standard": bool(STANDARD_MANIFEST_RE.match(name)),
        }

    # Выводим решение по каждому найденному манифесту.
    for name, data in manifests.items():
        status = data["status"]
        if status == "true":
            print(f"[МАНИФЕСТ] Найден: {name} | published=true  | передать manifest-analyzer.py")
        elif status == "false":
            print(f"[МАНИФЕСТ] Найден: {name} | published=false | пропустить черновик")
        elif status == "delete":
            print(f"[МАНИФЕСТ] Найден: {name} | published=delete | удалить с вложениями")
        else:
            print(f"[МАНИФЕСТ] Найден: {name} | published=некорректно | удалить с вложениями")
            print(f"[МАНИФЕСТ] Причина удаления: {data['reason']}")

    # Сначала определяем все файлы, на которые ссылаются сохраняемые манифесты.
    keep_files = set()
    for name, data in manifests.items():
        status = data["status"]
        if status not in ("true", "false"):
            continue

        keep_files.add(name)
        keep_files.update(data["attachments"])

        # Черновик со стандартным именем сохраняет весь комплект по общему префиксу,
        # в том числе файлы, пока не перечисленные в тексте манифеста.
        if status == "false" and data["standard"]:
            keep_files.update(data["standard_files"])

    # Манифесты delete и некорректные манифесты не сохраняются.
    delete_manifests = {
        name for name, data in manifests.items()
        if data["status"] in ("delete", "invalid")
    }

    # Удаляем все корневые файлы _input, не относящиеся к сохраняемым манифестам.
    # .gitkeep сохраняем; каталоги (например, arch) не затрагиваем.
    files_to_delete = {
        name for name in input_files
        if name != ".gitkeep" and name not in keep_files
    }

    # Учитываем стандартные комплекты delete/invalid. Общие вложения останутся,
    # поскольку они уже присутствуют в keep_files другого сохраняемого манифеста.
    for name in delete_manifests:
        data = manifests[name]
        candidates = set(data["attachments"]) | data["standard_files"]
        files_to_delete.update(candidates - keep_files)

    deleted = 0
    for name in sorted(files_to_delete):
        path = os.path.join(INPUT_DIR, name)
        if not os.path.isfile(path):
            continue
        try:
            os.remove(path)
            deleted += 1
            print(f"[МАНИФЕСТ] Удалён файл: {name}")
        except Exception as error:
            print(f"[МАНИФЕСТ] Критическая ошибка удаления '{name}': {error}")
            return 1

    kept_drafts = sum(1 for data in manifests.values() if data["status"] == "false")
    ready_manifests = sum(1 for data in manifests.values() if data["status"] == "true")
    removed_manifests = len(delete_manifests)

    print(
        "[МАНИФЕСТ] Итог: "
        f"готовых манифестов={ready_manifests}, "
        f"черновиков={kept_drafts}, "
        f"удалённых/некорректных манифестов={removed_manifests}, "
        f"удалённых файлов={deleted}."
    )
    print("[МАНИФЕСТ] Предварительная обработка завершена.")
    return 0


if __name__ == "__main__":
    sys.exit(process_manifests())
