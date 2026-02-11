class CallDispatcher:       # заготовка для обработки входящего потока
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