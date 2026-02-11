import subprocess
import tempfile
import os
import uuid


def get_duration(file_path):
    """Возвращает длительность видео в секундах (float)"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def concat_videos_by_order(video_files, order, output_file):
    inputs = []
    audio_flags = []
    durations = []

    # Проверяем существование файлов, наличие аудио и длительность
    for idx in order:
        path = os.path.abspath(video_files[idx])
        if not os.path.exists(path):
            raise FileNotFoundError(f"Файл не найден: {path}")
        inputs.append(path)
        # есть аудио?
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        audio_flags.append(bool(result.stdout.strip()))
        durations.append(get_duration(path))

    cmd = ["ffmpeg", "-y"]

    # Добавляем все видео как входы
    for f in inputs:
        cmd += ["-i", f]

    # Добавляем пустое аудио только для файлов без аудио
    null_audio_indices = []
    for i, has_a in enumerate(audio_flags):
        if not has_a:
            # задаем длительность равную исходному видео
            cmd += ["-f", "lavfi", "-t", str(durations[i]), "-i", "anullsrc=r=44100:cl=stereo"]
            null_audio_indices.append(i)

    # Строим filter_complex
    filter_parts = ""
    for i in range(len(inputs)):
        v = f"[{i}:v]"
        if audio_flags[i]:
            a = f"[{i}:a]"
        else:
            null_idx = len(inputs) + null_audio_indices.index(i)
            a = f"[{null_idx}:a]"
        filter_parts += v + a

    filter_complex = f"{filter_parts}concat=n={len(inputs)}:v=1:a=1[v][a]"

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "fast", #"veryfast",
        "-crf", "22", #"18",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-g", "48",
        output_file
    ]

    print("Запуск ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    # print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError("Ошибка при склеивании видео (см. вывод выше)")

    print(f"Видео успешно создано: {output_file}")

def concat_videos_by_order_old(video_files, order, output_file):
    """
    Склеивает видео в один файл по заданной последовательности индексов.

    :param video_files: список путей к исходным видео
    :param order: список индексов из video_files, определяющий порядок
    :param output_file: путь к итоговому mp4
    """
    # создаём временный файл с порядком для ffmpeg
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as list_file:
        list_filename = list_file.name
        for idx in order:
            path = os.path.abspath(video_files[idx])
            if not os.path.exists(path):
                raise FileNotFoundError(f"Файл не найден: {path}")
            # ffmpeg требует экранировать слеши в Windows
            path = path.replace('\\', '/')
            list_file.write(f"file '{path}'\n")

    # вызываем ffmpeg для склеивания без перекодирования
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_filename,
        "-map", "0:v",
        "-map", "0:a?",
        "-c:v", "copy",
        "-c:a", "aac",
        "-fflags", "+genpts",
        output_file
    ]

    print("Выполняется ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Ошибка ffmpeg:\n", result.stderr)
        raise RuntimeError("Ошибка при склеивании видео")
    else:
        print(f"Видео успешно склеено в {output_file}")

    # удаляем временный файл
    os.remove(list_filename)