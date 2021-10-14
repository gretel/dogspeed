try:import utime as time
except ImportError:import time
is_micropython=hasattr(time,'ticks_diff')
class DeltaT:
    def __init__(self,timediff):
        if timediff is None:
            self.expect_ts=False
            if is_micropython:self.timediff=lambda start,end:time.ticks_diff(start,end)/1000000
            else:raise ValueError('You must define a timediff function')
        else:self.expect_ts=True;self.timediff=timediff
        self.start_time=None
    def __call__(self,ts):
        if self.expect_ts:
            if ts is None:raise ValueError('Timestamp expected but not supplied.')
        elif is_micropython:ts=time.ticks_us()
        else:raise RuntimeError('Not MicroPython: provide timestamps and a timediff function')
        if self.start_time is None:self.start_time=ts;return 0.0001
        dt=self.timediff(ts,self.start_time);self.start_time=ts;return dt
