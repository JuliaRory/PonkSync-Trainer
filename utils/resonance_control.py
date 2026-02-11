import subprocess
import json
from pathlib import Path
import os

from utils.dispatcher import CallDispatcher
from drivers.resonance_foreign_driver import Driver

class ServiceProxy:
    """Объект конкретного сервиса"""
    def __init__(self, name, stream):
        self.name = name
        self._stream = stream

    def sendParameter(self, param, value):
        # check whether works or not
        """Отправка команды в QML-поток"""
        message = {
            "service": self.name,
            "type": "parameter",
            "param": param,
            "value": value
        }
        # stream должен иметь метод send(), который шлёт JSON в QML
        self._stream(json.dumps(message))
        print(f"[Proxy] Sent to {self.name}: {param}={value}")

    def sendTransition(self, command, stream=None, add_stimuli=None, filename=None):
        # works
        """Отправка команды в QML-поток"""
        message = {
            "service": self.name,
            "type": "command",
            "command": command, 
            "stream": stream,
            "filename": filename
        }
        if add_stimuli:
            message["add_stimuli"] = add_stimuli
        # stream должен иметь метод send(), который шлёт JSON в QML
        self._stream(json.dumps(message))
        print(f"[Proxy] Sent to {self.name}: command={command}")
    
    def checkState(self):
        self._stream(json.dumps({"service": self.name, "type": "check"}))
        print(f"[Proxy] Sent to {self.name}: get state")

class ResonanceAppProxy:
    """Псевдо-ResonanceApp для Python"""
    def __init__(self, qml_stream):
        self._stream = qml_stream
        self._services = {}

    def getService(self, name):
        """Возвращает объект сервиса (создаёт, если ещё нет)"""
        if name not in self._services:
            self._services[name] = ServiceProxy(name, self._stream)
        return self._services[name]