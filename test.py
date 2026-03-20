import sys
import os
import json
    
from drivers.resonance_foreign_driver import Driver


""" Объявление класса драйвера (передаётся название потока) """
driver = Driver("Test")

""" Функции для обработки входных потоков """

def process_messages(message, ts):
    msg = json.load(message)
    print(msg)


def process_data(data, ts):
    """
    data: np.array [n_samples, n_channels]
    ts:   ?        
        Resonance timestamps in nanaseconds.
    """
    print(type(ts))
    print(f"Data shape: {data.shape}, {ts//1E6} ms") 


""" Привязка функций для обработки входных данных """

# === Привязка функций напрямую ===


# === Привязка функций через "посредника" ===
class CallDispatcher:       # Класс-пустышка для привязки функций
    def __init__(self):
        self.reset()
        
    def reset(self):
        self._call = self._none
        
    def set_callback(self, callback):
        self._call = callback
        
    def _none(self, *kargs, **kwargs):
        pass
    
    def __call__(self, *kargs, **kwargs):
        self._call(*kargs, **kwargs)
        
dispatcher_messages = CallDispatcher() 
dispatcher_data = CallDispatcher() 

driver.inputMessageStream("messages", dispatcher_messages)  # привязка пустышки
driver.inputDataStream("data", dispatcher_data)             # привязка пустышки

dispatcher_messages.set_callback(process_messages)          # установка нужной функции к пустышке
dispatcher_data.set_callback(process_data)                  # установка нужной функции к пустышке