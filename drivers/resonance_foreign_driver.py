import ctypes
import platform
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
class Driver:
    def __init__(self, name):
        
        if platform.system() == "Windows":
            try:
                os.add_dll_directory(os.environ['RESONANCE_PATH'])
            except:
                pass
            dll_path = os.path.join(BASE_DIR, "ResonanceForeignDriver.dll")
            ctypes.windll.kernel32.LoadLibraryA(dll_path.encode('utf-8'))
            self._lib = ctypes.cdll.LoadLibrary(dll_path)
            
        else:
            self._lib = ctypes.CDLL("libResonanceForeignDriver.so")
        
        self._lib.setUp.argtypes = [ctypes.c_char_p]
        
        self._lib.pollEvents.argtypes = []
        
        self._lib.outputMessageStream.restype = ctypes.c_size_t
        self._lib.outputMessageStream.argtypes = [ctypes.c_char_p]
        
        self._lib.sendMessage.argtypes = (ctypes.c_size_t, ctypes.c_char_p)
        
        self._messageCallback = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_uint64)
        self._dataCallback = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_double), ctypes.c_uint, ctypes.c_uint, ctypes.c_uint64)
        
        self._callbacks = []
        
        self._lib.inputMessageStream.argtypes = (ctypes.c_char_p, self._messageCallback)
        self._lib.inputDataStream.argtypes = (ctypes.c_char_p, self._dataCallback)
        
        self._lib.loadConfig.argtypes = [ctypes.c_char_p]
        
        self._lib.setUp(bytes(name, 'utf-8'))
        
    def loadConfig(self, fileName):
        self._lib.loadConfig(bytes(fileName, 'utf-8'))
        
    def pollEvents(self):
        self._lib.pollEvents()
        
    def outputMessageStream(self, name):
        id = self._lib.outputMessageStream(bytes(name, 'utf-8'))
        
        def sendMessage(message):
            self._lib.sendMessage(id, bytes(message, 'utf-8'))
            
        return sendMessage
    
    
    def inputMessageStream(self, name, callback):
        cb = self._messageCallback(callback)
        self._callbacks.append(cb)
        self._lib.inputMessageStream(bytes(name, 'utf-8'), cb)
        
    def inputDataStream(self, name, callback, no_numpy=False):
        def cb_wrapper(data, channels, samples, timestamp):
            if no_numpy:
                arr = []
                i = 0
                for s in range(0, samples):
                    v = []
                    for c in range(0, channels):
                        v.append(data[i])
                        i += 1
                    arr.append(v)
            else:
                import numpy as np
                arr = np.zeros((samples, channels))
                i = 0
                for s in range(0, samples):
                    for c in range(0, channels):
                        arr[s,c] = data[i]
                        i += 1
            callback(arr, timestamp)
            
        cb = self._dataCallback(cb_wrapper)
        self._callbacks.append(cb)
        self._lib.inputDataStream(bytes(name, 'utf-8'), cb)
