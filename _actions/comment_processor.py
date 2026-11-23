#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@module  comment_processor.py
@about   Модуль запуска специализированных этапов обработки комплектов.
@purpose Последовательно запускает manifest_processor.py и manifest-analyzer.py для комплектов в репозитории eaststandart/techlab-comment-builder, передаёт вывод дочерних процессов и контролирует время выполнения анализатора.
@author  TechLab
@version 1.0.0
"""

import os
import signal
import subprocess
import sys
import threading


ANALYZER_TIMEOUT_SECONDS = 15 * 60


def run_manifest_processor():
    """Запускает предварительную обработку манифестов перед Analyzer."""
    print("\n[comment_processor] Запуск модуля 'manifest_processor.py'...")
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
            print(f"[comment_processor] Manifest Processor завершился с кодом {result.returncode}.")
            return False
        return True
    except Exception as err:
        print(f"[comment_processor] Ошибка запуска Manifest Processor: {str(err)}")
        return False


def _stop_analyzer_process(process):
    """Завершает анализатор вместе с запущенными им дочерними процессами."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except Exception:
        process.terminate()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception:
            process.kill()
        process.wait()


def run_manifest_analyzer():
    """Запускает анализатор с потоковым выводом и ограничением времени."""
    print("\n[comment_processor] Запуск модуля 'manifest-analyzer.py'...")
    print(
        f"[comment_processor] Тайм-аут одной попытки анализатора: "
        f"{ANALYZER_TIMEOUT_SECONDS // 60} минут."
    )

    process = None
    output_lines = []

    try:
        process = subprocess.Popen(
            [sys.executable, "-u", "_actions/manifest-analyzer.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True
        )

        def forward_output():
            try:
                for line in process.stdout:
                    output_lines.append(line)
                    print(line, end="", flush=True)
            finally:
                process.stdout.close()

        output_thread = threading.Thread(target=forward_output, daemon=True)
        output_thread.start()

        try:
            return_code = process.wait(timeout=ANALYZER_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            print(
                f"[comment_processor] Превышен тайм-аут {ANALYZER_TIMEOUT_SECONDS // 60} минут. "
                "Завершаем анализатор и его дочерние процессы."
            )
            _stop_analyzer_process(process)
            output_thread.join(timeout=10)
            return "ERROR_ANALYZER_TIMEOUT"

        output_thread.join()

        if return_code != 0:
            print(f"[comment_processor] Manifest Analyzer завершился с кодом {return_code}.")
            return "ERROR_ANALYZER"

        for line in output_lines:
            marker = "Финальный статус работы модуля:"
            if marker in line:
                analyzer_status = line.split(marker, 1)[1].strip()
                if analyzer_status:
                    return analyzer_status
                break

        print("[comment_processor] Manifest Analyzer не вернул ожидаемый финальный статус.")
        return "ERROR_ANALYZER"

    except Exception as err:
        if process is not None and process.poll() is None:
            _stop_analyzer_process(process)
        print(f"[comment_processor] Ошибка запуска Manifest Analyzer: {str(err)}")
        return "ERROR_ANALYZER"
