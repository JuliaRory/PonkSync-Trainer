from PyQt5.QtCore import pyqtSignal, QObject
from typing import List, Tuple, Optional
from numpy import ndarray

class DataSource(QObject):
    """
    Базовый класс для источника данных.

    Attributes: 
        is_active (bool): флаг запущен ли приёмщик
        packs (list): packs of signal [n_samples x n_channels]
        timestamps (list): время прихода пакета (от резонанса) 

    Signals:
        dataReady(object, float): испускается с аргументами packs и timestamp

    Methods: 
        start(): Запускает источник данных 
        stop(): Останавливает источник данных
    
    """
    dataReady = pyqtSignal(object, float)  # epoch, timestamp

    def __init__(self):
        super().__init__()
        self.is_active = False  

        self.packs = []                          
        self.timestamps = []      

    def start(self): 
        self.is_active = True

    def stop(self): 
        self.is_active = False
