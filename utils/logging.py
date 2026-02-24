import logging
import sys
import os
from datetime import datetime

class ImmediateFileHandler(logging.FileHandler):
    """Кастомный handler с немедленной записью на диск"""
    def emit(self, record):
        super().emit(record)
        self.flush()  # принудительная запись после каждого сообщения

def setup_logging(log_dir="logs", log_level=logging.INFO):
    """
    Настройка логирования с немедленной записью
    """
    # Создаем папку для логов если её нет
    os.makedirs(log_dir, exist_ok=True)
    
    # Имя файла с датой
    log_filename = os.path.join(
        log_dir, 
        f'app_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    )
    
    # Настройка форматирования
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler для файла с немедленной записью
    file_handler = ImmediateFileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Handler для консоли (опционально)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    # Очищаем старые handler'ы чтобы не было дублей
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Перехват необработанных исключений
    def exception_handler(exctype, value, tb):
        logging.critical("Необработанное исключение", exc_info=(exctype, value, tb))
        sys.__excepthook__(exctype, value, tb)
    
    sys.excepthook = exception_handler
    
    logging.info(f"Логирование инициализировано. Файл: {log_filename}")
    return root_logger