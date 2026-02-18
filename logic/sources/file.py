from .base import DataSource
import numpy as np
import h5py

class FileSource(DataSource):
    
    def load_file(self, path):
        with h5py.File(path, "r") as f:
            epochs = f["epochs"][:]
            for ep in epochs:
                self.dataReady.emit(ep, 0.0)