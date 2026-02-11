import bisect
from collections import deque
import copy
import logging




class RollingMean:
    def __init__(self, data, n_max, save_all=False):
        self.n = n_max
        self.trim_last = not save_all
        self.window = deque(data[:n_max], maxlen=n_max if self.trim_last else None)
        self.sum = sum(self.window)

    
    def add(self, value):
        if len(self.window) == self.n and self.trim_last:
            old = self.window.popleft()
            self.sum -= old
        self.window.append(value)
        self.sum += value

    def calculate(self):
        if len(self.window) == 0:
            return None
        return self.sum * (1.0 / len(self.window)) # sround(self.sum / len(self.window), 2)
    
class RollingMedian:
    def __init__(self, data, n_max, save_all=False):
        self.n = n_max
        self.trim_last = not save_all
        self.window = deque(data[:n_max])
        self.sorted_window = copy.deepcopy(list(data[:n_max]))
        self.sorted_window.sort()

    def add(self, value):
        # добавляем новое значение
        bisect.insort(self.sorted_window, value)
        self.window.append(value)

        # если превысили размер окна — удаляем самое старое
        if (len(self.window) > self.n) & self.trim_last:
            old = self.window.popleft()
            self.sorted_window.remove(old)

    def calculate(self):
        m = len(self.sorted_window)
        if m == 0:
            return None
        if m % 2 == 1:
            return round(self.sorted_window[m // 2], 2)
        else:
            return round((self.sorted_window[m // 2 - 1] + self.sorted_window[m // 2]) / 2, 2)


class RollingTrimMean:
    def __init__(self, data, n_max, proportiontocut=0.1, save_all=False):
        self.n = n_max
        self.trim_last = not save_all
        self.deque = deque(data[:n_max])
        self.proportiontocut = proportiontocut
        self.sorted_list = copy.deepcopy(list(data[:n_max]))
        self.sorted_list.sort()

    def add(self, value):
        # добавляем новое значение в очередь и отсортированный список
        self.deque.append(value)
        bisect.insort(self.sorted_list, value)

        # если превысили n, выкидываем старое
        if (len(self.deque) > self.n) & self.trim_last:
            old = self.deque.popleft()
            idx = bisect.bisect_left(self.sorted_list, old)
            self.sorted_list.pop(idx)

    def calculate(self):
        m = len(self.sorted_list)
        if m == 0:
            return None

        k = int(self.proportiontocut * m)   # пересчёт сколько данных обрезать
        if m < 2 * k + 1:
            return None  # мало данных для усечения
        trimmed = self.sorted_list[k:m - k]
        return round(sum(trimmed) / len(trimmed), 2)
    

