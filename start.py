from PyQt5.QtWidgets import QApplication
import os
import sys
import json


from Window import MainWindow, ArtemMainWindow
from resonance_foreign_driver import Driver

"""Магический класс для подключения потоков с Резонанса"""
class CallDispatcher:
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


# os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = r'C:\Users\hodor\Documents\Eyes\коды\EMG_app\venv\Lib\site-packages\PyQt5\Qt5\plugins'
# # os.environ['PATH'] += r';~qgis directoryqt\apps\qgis\bin;~qgis directory\apps\Qt5\bin'


# # подгрузка настроек для автоматического перетаскивания потоков !!!!!!!!!!!!!!!!!!
# driver.loadConfig(r"R:\`dist_2024_10_25\params\electronic_artem_settings.json")

# main = MainWindow(dispatcher)


# main.show()
# sys.exit(app.exec_())



if __name__ == "__main__":
    app = QApplication(sys.argv)        # initialize qt app
    
    with open(r"settings.json") as json_data:     # вгрузить настройки приложения
        settings = json.load(json_data)

    # "stream_mode": "LSL" (if raw data from NeoRec) or "NVX" (if raw data from Resonance) or "SPEED" (if data from Resonance preprocessed in SPEED) 
    if settings['stream_mode'] in ['NVX', 'SPEED']:         # если данные приходят с Resonance
        driver = Driver("ElectronicArtem_v2")

        dispatcher = CallDispatcher() 
        driver.inputDataStream("data", dispatcher)          # создать входной поток

        driver.loadConfig(r"resonance_settin'stream_mode'gs.json")    # вгрузить настройки резонанса с потоками
    else:
        dispatcher = None                                   # если данные из NeoRec передаются через LSL
    
    artem  = ArtemMainWindow(dispatcher, settings)   # open main window
    # lsl = MainWindow()

    artem.show()
    # lsl.show()
    sys.exit(app.exec_())