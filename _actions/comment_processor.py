#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  comment_processor.py
@about   Модуль обработки комплектов конструктора комментариев.
@purpose Запуск предварительной обработки манифестов и анализатора с сохранением действующей последовательности специализированных операций.
@author  TechLab
@version 1.0.0
"""

import subprocess
import sys


def run_manifest_processor():
    """Запускает предварительную обработку манифестов перед Analyzer."""
    print("\n[ОБРАБОТЧИК] Запуск модуля 'manifest_processor.py'...")
    try:
        result = subprocess.run(
            [sys.executable, "_actions/manifest_processor.py"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        if result.returncode != 0:
            print(f"[ОБРАБОТЧИК] Manifest Processor завершился с кодом {result.returncode}.")
            return False
        return True
    except Exception as err:
        print(f"[ОБРАБОТЧИК] Ошибка запуска Manifest Processor: {str(err)}")
        return False


def run_manifest_analyzer():
    """Запускает анализатор и возвращает его финальный статус."""
    print("\n[ОБРАБОТЧИК] Запуск модуля 'manifest-analyzer.py'...")
    try:
        result = subprocess.run(
            [sys.executable, "_actions/manifest-analyzer.py"],
            capture_output=True,
            text=True
        )
        print(result.stdout)

        if result.returncode != 0:
            if result.stderr:
                print(result.stderr)
            print(f"[ОБРАБОТЧИК] Manifest Analyzer завершился с кодом {result.returncode}.")
            return "ERROR_ANALYZER"

        for line in result.stdout.splitlines():
            if "Финальный статус работы модуля:" in line:
                analyzer_status = line.split(":")[-1].strip()
                if analyzer_status:
                    return analyzer_status
                break

        print("[ОБРАБОТЧИК] Manifest Analyzer не вернул ожидаемый финальный статус.")
        return "ERROR_ANALYZER"
    except Exception as err:
        print(f"[ОБРАБОТЧИК] Ошибка запуска Manifest Analyzer: {str(err)}")
        return "ERROR_ANALYZER"
