from .base import DataSource
import numpy as np
import json

class StreamSource(DataSource):
    """
    Источник потоковых данных.
    
    Добавляет: 
    Args: 
        input_stream: функция-пустышка для прикрепления приёмника входных данных

    Private methods:
        _receive_data(): принимает новый пакет данных от потока и обновляет списки для их хранения

    """
    def __init__(self, input_data_stream, input_message_stream):
        super().__init__()
        
        input_data_stream.set_callback(self._receive_data)     
        input_message_stream.set_callback(self._receive_message_data)         

            
    def _receive_data(self, msg, timestamp):
        """
            Args:
                msg(ndarray): пакет данных [n_samples x n_channels]
                timestamp(int): таймстемп по времени резонанса
            
            Signals:
                dataReady(object, float): испускается с аргументами packs и timestamp -> DataProcessor
        """

        data = np.array(msg)                 
        self.dataReady.emit(data, timestamp)  
    
    def _receive_message_data(self, msg, timestamp):
        """
            Args:
                msg(ndarray): пакет данных dict{"data": [n_samples x n_channels]}
                timestamp(int): таймстемп по времени резонанса
            
            Signals:
                dataReady(object, float): испускается с аргументами packs и timestamp -> DataProcessor
        """

        data = np.array(json.loads(msg)["data"]) # [n_channels x n_samples]       
        self.dataReady.emit(data, timestamp)  


