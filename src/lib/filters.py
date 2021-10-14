# https://github.com/jojo-/filters4micropy
class AverageFilter:

    def __init__(self):
        self.__k = 1
        self.__val = 0

    def update(self, value):
        alpha = (self.__k - 1) / self.__k
        self.__val = alpha * self.__val + (1 - alpha) * value
        self.__k = self.__k + 1
        return self.__val

    def get(self):
        return self.__val

class MovingAverageFilter:

    def __init__(self, window = 1):
        self.__val = 0
        self.__window = window
        self.__data = None

    def update(self, value):

        if self.__data is None:
            self.__data = [value] * self.__window
            self.__val = value

        self.__data.pop(0)
        self.__data.append(value)
        self.__val = self.__val + (value - self.__data[0]) / self.__window

        return self.__val

    def get(self):
        return self.__val

class LowPass1Filter:

    def __init__(self, alpha):
        self.__val = None
        self.__alpha = alpha

    def update(self, value):

        if self.__val == None:
            self.__val = value

        self.__val = self.__alpha  * self.__val + (1 - self.__alpha) * value
        
        return self.__val

    def get(self):
        return self.__val