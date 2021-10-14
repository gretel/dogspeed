import micropython, gc

# https://docs.micropython.org/en/latest/library/micropython.html#micropython.alloc_emergency_exception_buf
micropython.alloc_emergency_exception_buf(100)

# https://docs.micropython.org/en/latest/library/micropython.html#micropython.opt_level
#micropython.opt_level(1)
print('__debug__', __debug__)

import machine
# if something goes really wrong like exceptions on boot we can at least see what caused the reset
print('reset_cause', machine.reset_cause())
