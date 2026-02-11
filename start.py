from PyQt5.QtWidgets import QApplication
import os
import sys
import time

from utils.theme_loader import load_qss
from utils.resonance_control import ResonanceAppProxy

from utils.dispatcher import CallDispatcher
from drivers.resonance_foreign_driver import Driver
from ui.main_window import MainWindow


if __name__ == "__main__":
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = r'.\venv\Lib\site-packages\PyQt5\Qt5\plugins'
    os.environ['PATH'] += r';~qgis directoryqt\apps\qgis\bin;~qgis directory\apps\Qt5\bin'

    # == Создание главный объект приложения Qt == 
    app = QApplication(sys.argv)    

    # == Магическое подключениен драйвера для получения потока с данными из резонанса ==                                                                                        
    driver = Driver("PonkSync-Trainer")

    dispatcher = CallDispatcher()                                         # пустая функция-обработчик
    driver.inputDataStream("emg", dispatcher)                             # создание входного потока данных типа Stream

    output_stream = driver.outputMessageStream("controlSignal")           # создание выходного потока данных типа Message
    # output_stream_stimuli = driver.outputMessageStream("stimuli")         # создание выходного потока данных типа Message
    resonance = ResonanceAppProxy(output_stream)                          # Создаем прокси резонанса

    # driver.loadConfig(r'stream_nvx136@eeg__to__PonkSync-Trainer@emg.json')       # вгрузить настройки с потоком в резонансе

    # == Запуск приложения ==

    window  = MainWindow(dispatcher, resonance)   # open main window
    window.show()
    
    sys.exit(app.exec_())