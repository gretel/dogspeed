_A=None
class AverageFilter:
    def __init__(A):A.__k=1;A.__val=0
    def update(A,value):B=(A.__k-1)/A.__k;A.__val=B*A.__val+(1-B)*value;A.__k=A.__k+1;return A.__val
    def get(A):return A.__val
class MovingAverageFilter:
    def __init__(A,window=1):A.__val=0;A.__window=window;A.__data=_A
    def update(A,value):
        B=value
        if A.__data is _A:A.__data=[B]*A.__window;A.__val=B
        A.__data.pop(0);A.__data.append(B);A.__val=A.__val+(B-A.__data[0])/A.__window;return A.__val
    def get(A):return A.__val
class LowPass1Filter:
    def __init__(A,alpha):A.__val=_A;A.__alpha=alpha
    def update(A,value):
        B=value
        if A.__val==_A:A.__val=B
        A.__val=A.__alpha*A.__val+(1-A.__alpha)*B;return A.__val
    def get(A):return A.__val