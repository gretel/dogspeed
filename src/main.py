import log
from machine import ADC, Pin, SoftI2C
import neopixel
import ujson
import ubinascii
import fancyled as fancy
from BMI160 import BMI160_I2C
import filters
from wifi_manager import WifiManager
import uasyncio as asyncio
from primitives import EButton
import aiorepl
# from time import sleep_ms
# from fusion_async import Fusion


class Shared:
    def __init__(self):
        self.vbat = 0
        self.palette_idx = 0
        self.flash = 1
        self.save = 0


# in the beginning there is the declaration of a protocol version
VERSION = const(0x05)

NUM_LEDS_INT = const(2)
NUM_LEDS_EXT = const(44)

# configuration files to load at runtime
FILE_UID = "/uid.json"

led_board = neopixel.NeoPixel(machine.Pin(27, Pin.OUT), 1)  # GPIO27
led_board[0] = (50, 0, 50, 0)
led_board.write()

led_int = neopixel.NeoPixel(machine.Pin(22), NUM_LEDS_INT, bpp=4)  # GPIO22
led_int[0] = (0, 50, 0, 0)
led_int[1] = (50, 0, 0, 0)
led_int.write()

led_ext = neopixel.NeoPixel(machine.Pin(32), NUM_LEDS_EXT, bpp=3)  # GPIO32

vbat_pin = Pin(33, Pin.IN)  # GPIO33
vbat_adc = ADC(vbat_pin)
vbat_adc.atten(ADC.ATTN_11DB)  # 3.3V

infra_pin = Pin(12, Pin.IN)  # GPIO12

button_pin = Pin(39, Pin.IN, Pin.PULL_DOWN)  # GPIO39
button = EButton(button_pin, sense=1, suppress=1)
button.double_click_ms = 1000


async def eb_press(shared):
    while True:
        button.press.clear()
        await button.press.wait()
        log.debug('btn', 'press')
        if(shared.palette_idx == len(mixer_palette) - 1):
            shared.palette_idx = 0
        else:
            shared.palette_idx += 1
        
        log.info('btn', 'palette: {}'.format(shared.palette_idx))


async def eb_long(shared):
    while True:
        button.long.clear()
        await button.long.wait()
        log.debug('btn', 'long')
        shared.save ^= 1


async def eb_double(shared):
    while True:
        button.double.clear()
        await button.double.wait()
        log.debug('btn', 'double')
        shared.flash ^= 1


async def eb_release(shared):
    while True:
        button.release.clear()
        await button.release.wait()
        log.debug('btn', 'release')


# inhale json
def read_json(filename):
    log.debug("json", "reading {}".format(filename))
    with open(filename, "r") as f:
        j = ujson.loads(f.read())
        f.close()
        return j


# exhale json
def write_json(filename, j):
    log.info("json", "writing {}".format(filename))
    with open(filename, "w") as f:
        ujson.dump(j, f)
        f.close()


# identify ourselves uniquely
MACHINE_UID = ubinascii.hexlify(machine.unique_id()).decode("utf-8")

try:
    # if exist read last stored uid to prevent wearing flash if no change is required
    r = read_json(FILE_UID)
except OSError as e:
    r = None
finally:
    log.info("uid", MACHINE_UID)

# store if nonexistent or different
if r is None or r["uid"] != MACHINE_UID:
    write_json(FILE_UID, {"uid": MACHINE_UID})


# frequency high, updates lots
i2c = SoftI2C(scl=Pin(21), sda=Pin(25), freq=400000)  # SCL: GPIO21, SDA: GPIO25
# print(i2c.scan())
log.debug('i2c', i2c)


# imu
imu = BMI160_I2C(i2c)
log.debug('imu', imu)


async def task_vbat(shared):
    while True:
        # Read ADC and convert to voltage
        val = vbat_adc.read()
        # val = val * (3.3 / 4095)
        val = val * 3 * 1400 / 4095 /1000
        shared.vbat = val
        log.debug('vbat', '%sV', round(val, 2)) # Keep only 2 digits

        await asyncio.sleep_ms(5000)


async def task_blink(shared):
    while True:
        led_board[0] = (0, 0, 10)
        led_board.write()
        await asyncio.sleep_ms(10)
        led_board[0] = (0, 0, 0)
        led_board.write()
        await asyncio.sleep_ms(500)


# async def task_network():
#     # https://github.com/mitchins/micropython-wifimanager#asynchronous-usage-event-loop
#     WifiManager.start_managing()
#
#     while True:
#         if (WifiManager.wlan().status() == 1010):
#             # got connected
#             log.info('net', 'connected: %s', WifiManager.ifconfig())
#             # done here
#             return
#         await asyncio.sleep_ms(250)

# async def read_coro():
#     # TODO: validate sleepy time
#     await asyncio.sleep_ms(50)
#     # go with what is set right now
#     imu_acc = imu.getAcceleration()
#     imu_rot = imu.getRotation()
#     return imu_acc, imu_rot


# # necessary for long term stability
# async def task_gc():
#     while True:
#         # wait first
#         await asyncio.sleep_ms(5000)
#         log.debug("gc", "running")
#         # take the trash down now
#         gc.collect()
#         # adjust the threshold for the meantime
#         gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
#         # and give info for reference
#         log.debug('gc', 'free: {}, allocated: {}'.format(gc.mem_free(), gc.mem_alloc()))


async def task_led_ext(shared):
    maf = filters.MovingAverageFilter(12)
    mixer_offset = 0

    while True:
        axis_sum = 0
        for a in imu.getRotation():
            axis_sum += abs(a)

        avg = maf.update(axis_sum)

        if(shared.save):
            bright = 0.4
        else:
            bright = 0.7

        if(avg > 7000):
            bright -= 0.2
        elif (avg < 1000):
            avg = 500
            bright += 0.2

        mixer_offset += avg / 700000
        # mixer_offset += axis_sum / 600000

        for i in range(NUM_LEDS_EXT):
            offset = mixer_offset + i / NUM_LEDS_EXT
            color = fancy.palette_lookup(mixer_palette[shared.palette_idx], offset)
            color = fancy.gamma_adjust(color, brightness=bright)

            color_packed = color.pack()
            led_ext[i] = ((color_packed & 0xff0000) >> 16, (color_packed & 0xff00) >> 8, color_packed & 0xff)

        led_ext.write()
        await asyncio.sleep_ms(20)


async def task_led_int(shared):
    maf = filters.MovingAverageFilter(4)

    bright = 0.9
    side = 0
    sleep_time = 100
    white = 50

    while True:
        if(not shared.flash):
            sleep_time = 500

            # force off
            led_int[0] = (0,0,0,0)
            led_int[1] = (0,0,0,0)
            led_int.write()
        else:
            # if(shared.save):
            #     bright = 0.4
            # else:
            #     bright = 0.9

            axis_sum = 0
            for a in imu.getRotation():
                axis_sum += abs(a)

            avg = maf.update(axis_sum)

            if(avg < 4900):
                sleep_time = 330

                if(side):
                    color = fancy.gamma_adjust(fancy.CRGB(1.0, 1.0, 1.0), brightness=bright)
                    color_packed = color.pack()
                    led_int[0] = ((color_packed & 0xff0000) >> 16, (color_packed & 0xff00) >> 8, color_packed & 0xff, white)
                else:
                    color = fancy.gamma_adjust(fancy.CRGB(1.0, 1.0, 1.0), brightness=bright)
                    color_packed = color.pack()
                    led_int[1] = ((color_packed & 0xff0000) >> 16, (color_packed & 0xff00) >> 8, color_packed & 0xff, white)

                led_int.write()
                await asyncio.sleep_ms(20)

                led_int[0] = (0,0,0,0)
                led_int[1] = (0,0,0,0)
                led_int.write()

        # toggle
        side ^= 1
        await asyncio.sleep_ms(sleep_time)


# TODO: revamp
mixer_palette = []
mixer_palette.append([
    fancy.CRGB(1.0, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(1.0, 0.0, 0.5),  # Magenta
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 1.0),  # Blue
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.6, 0.4, 0.0),  # Orange
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.9, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.9, 0.0, 0.4),  # Magenta
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.4, 0.0, 0.9),  # Purple
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.6, 0.4, 0.0),  # Orange
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),

])

mixer_palette.append([
    fancy.CRGB(1.0, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(1.0, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(1.0, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(1.0, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])

mixer_palette.append([
    fancy.CRGB(0.0, 1.0, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.7, 0.0, 0.7),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 1.0, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.7, 0.7),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 1.0, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.7, 0.0, 0.7),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 1.0, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.7, 0.7),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])

mixer_palette.append([
    fancy.CRGB(1.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.5, 1.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 1.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 1.0, 0.5),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(1.0, 0.5, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])


async def main():
    # await fuse.start()

    tasks = []
    shared = Shared()

    # tasks
    tasks.append(asyncio.create_task(task_vbat(shared)))
    tasks.append(asyncio.create_task(task_blink(shared)))
    tasks.append(asyncio.create_task(task_led_int(shared)))
    tasks.append(asyncio.create_task(task_led_ext(shared)))

    tasks.append(asyncio.create_task(eb_press(shared)))
    tasks.append(asyncio.create_task(eb_double(shared)))
    tasks.append(asyncio.create_task(eb_release(shared)))
    tasks.append(asyncio.create_task(eb_long(shared)))

    # net = asyncio.create_task(task_network())
    # gc = asyncio.create_task(task_gc())
    repl = asyncio.create_task(aiorepl.task())

    await asyncio.gather(*tasks, repl)


# tidy memory
gc.collect()
# and give info for reference
micropython.mem_info()

try:
    # fuse = Fusion(read_coro)
    log.info("main", "running")
    asyncio.run(main())
except KeyboardInterrupt:
    # humans
    log.warning("main", "interrupted")
finally:
    # loop
    _ = asyncio.new_event_loop()
