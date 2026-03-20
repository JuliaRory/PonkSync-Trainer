import json
import time
import sys

from drivers.resonance_foreign_driver import Driver
from PyQt5.QtCore import QCoreApplication, QTimer   # без этого никуда... 

""" Функции для обработки входных потоков """

def process_messages(message, ts):
    msg = json.load(message)
    print(msg)


def process_data(data, ts):
    """
    data: np.array [n_samples, n_channels]
    ts:   int        
        Resonance timestamps in nanaseconds.
    """
    print(f"Data shape: {data.shape}, {ts//1E6:.0f} ms") 


if __name__ == "__main__":
    app = QCoreApplication(sys.argv)    

    """ Объявление класса драйвера (передаётся название потока) """
    driver = Driver("Test")


    """ Привязка функций для обработки входных данных """

    # === Привязка функций напрямую ===
    driver.inputMessageStream("messages", process_messages)  # привязка пустышки
    driver.inputDataStream("data", process_data)             # привязка пустышки

    # === АЛЬТЕРАТИВО: Привязка функций через "посредника" ===

    # class CallDispatcher:       # Класс-пустышка для привязки функций
    #     def __init__(self):
    #         self.reset()
            
    #     def reset(self):
    #         self._call = self._none
            
    #     def set_callback(self, callback):
    #         self._call = callback
            
    #     def _none(self, *kargs, **kwargs):
    #         pass
        
    #     def __call__(self, *kargs, **kwargs):
    #         self._call(*kargs, **kwargs)
            
    # dispatcher_messages = CallDispatcher() 
    # dispatcher_data = CallDispatcher() 

    # driver.inputMessageStream("messages", dispatcher_messages)  # привязка пустышки
    # driver.inputDataStream("data", dispatcher_data)             # привязка пустышки

    # dispatcher_messages.set_callback(process_messages)          # установка нужной функции к пустышке
    # dispatcher_data.set_callback(process_data)                  # установка нужной функции к пустышке

    # === Подгрузка настроек с потоками ===
    filename = "bla-bla.json"         # создай файл с помощью функциии save в конфигураторе, после того как соединишь потоки
    driver.loadConfig(filename)       

    # === Чтобы скрипт не закрывался === 

    # таймер, чтобы цикл событий Qt не завершался сразу
    timer = QTimer()
    timer.start(1000)  
    timer.timeout.connect(lambda: None)
    
    sys.exit(app.exec_())