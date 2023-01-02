import log
import sys
from machine import ADC, Pin, SoftI2C
import random
import ujson
import ubinascii
import neopixel
import fancyled as fancy
from BMI160 import BMI160_I2C
import uasyncio as asyncio
from primitives import EButton
import aiorepl
import filters
# from wifi_manager import WifiManager


class Shared:
    def __init__(self):
        self.balance = 0
        self.palette_idx = 0
        self.rot_avg_short = 0
        self.rot_avg_long = 0
        self.vbat = 0

        self.bright = 0.6
        self.flash = 1
        self.ifconfig = {}
        self.low_power = False
        self.zero_motion = False


# in the beginning there is the declaration of a protocol version
VERSION = const(0x06)
VBAT_CORR = const(218)
NUM_LEDS = const(44)
LOW_ACCEL_THRESH = const(5200)
OFFSET_INCR_DIV = const(650000)
FILE_UID = "/uid.json"


led_board = neopixel.NeoPixel(machine.Pin(27, Pin.OUT), 1)  # GPIO27
led_board[0] = (30, 0, 30, 0)
led_board.write()

led_strip = neopixel.NeoPixel(machine.Pin(32), NUM_LEDS, bpp=3)  # GPIO32
led_strip.fill((0,0,0))
led_strip.write()

vbat_pin = Pin(33, Pin.IN)  # GPIO33
vbat_adc = ADC(vbat_pin)
vbat_adc.atten(ADC.ATTN_11DB)  # 3.3V

# infra_pin = Pin(12, Pin.IN)  # GPIO12

button_pin = Pin(39, Pin.IN, Pin.PULL_DOWN)  # GPIO39
button = EButton(button_pin, sense=1, suppress=1)
button.double_click_ms = 1000


async def eb_press(shared):
    while True:
        button.press.clear()
        await button.press.wait()
        if(shared.palette_idx == len(mixer_palette) - 1):
            shared.palette_idx = 0
        else:
            shared.palette_idx += 1
        log.info('btn', 'palette: {}'.format(shared.palette_idx))


async def eb_long(shared):
    while True:
        button.long.clear()
        await button.long.wait()
        shared.low_power ^= True
        if(shared.low_power):
            # TODO: abstraction
            shared.balance = -0.4
        else:
            shared.balance = 0
        log.info('btn', 'low_power: {}, balance: {}'.format(shared.low_power, shared.balance))


async def eb_double(shared):
    while True:
        button.double.clear()
        await button.double.wait()
        shared.flash ^= True
        log.info('btn', 'flash: {}'.format(shared.flash))


# async def eb_release(shared):
#     while True:
#         button.release.clear()
#         await button.release.wait()
#         # log.debug('btn', 'release')


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
imu.set_accel_rate(7)
imu.set_gyro_rate(7)
# imu.setAccelDLPFMode(0)
imu.setFullScaleAccelRange(0X05, 4)
imu.setFullScaleGyroRange(3, 250)

imu.setZeroMotionDetectionDuration(1)
imu.setZeroMotionDetectionThreshold(2)
imu.setIntZeroMotionEnabled(True)

log.debug('imu', 'temperature: {}'.format(imu.getTemperature()))


async def task_imu(shared):
    maf_long = filters.MovingAverageFilter(10)
    maf_short = filters.MovingAverageFilter(4)

    while True:
        sleep_time = 200
        sum = 0
        for a in imu.getRotation():
            sum += abs(a)
        shared.rot_avg_long = maf_long.update(sum)
        shared.rot_avg_short = maf_short.update(sum)
        shared.zero_motion = imu.getIntZeroMotionStatus()
        if(shared.zero_motion):
            log.info('imu', 'zero motion')
            sleep_time = 1000
        await asyncio.sleep_ms(sleep_time)


async def task_vbat(shared):
    while True:
        # Read ADC and convert to voltage
        val = vbat_adc.read()
        val = val * (3.3 / 4095) * (VBAT_CORR / 100)  # correction
        shared.vbat = round(val, 2)
        if(val > 0):
            log.debug('vbat', '%sV', shared.vbat)
        await asyncio.sleep_ms(2000)


# FIXME: sync     
async def task_blink(shared):
    while True:
        sleep_time = 1000
        color = (0, 0, 10, 0)

        vbat = shared.vbat
        if vbat > 4.0:
            color = (0, 10, 0, 0)
            sleep_time = 1500
            shared.balance = 0
        elif vbat > 3.8:
            color = (5, 5, 0, 0)
            shared.balance = -0.1
        elif vbat > 3.5:
            color = (10, 0, 0, 0)
            sleep_time = 750
            shared.balance = -0.3
        elif vbat > 3.2:
            sleep_time = 500
            color = (10, 0, 5, 0)
            shared.balance = -0.5
            shared.low_power = True
        else:
            shared.balance = 0
            shared.low_power = False     

        led_board[0] = color
        led_board.write()
        await asyncio.sleep_ms(20)
        led_board[0] = (0, 0, 0)
        led_board.write()
        await asyncio.sleep_ms(sleep_time)


# async def task_network(shared):
#     # https://github.com/mitchins/micropython-wifimanager#asynchronous-usage-event-loop
#     WifiManager.start_managing()
#     while True:
#         if (WifiManager.wlan().status() == 1010):
#             shared.ifconfig = WifiManager.ifconfig()
#             # got connected
#             log.info('net', 'connected: {}'.format(shared.ifconfig))
#             # done here
#             return
#         await asyncio.sleep_ms(250)


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


async def task_led_strip(shared):
    mixer_offset = 0
    while True:
        bright = shared.bright + shared.balance
        avg = shared.rot_avg_long
        if (avg < 500):
            avg = 500
        mixer_offset += avg / OFFSET_INCR_DIV
        for i in range(NUM_LEDS):
            offset = mixer_offset + i / NUM_LEDS
            color = fancy.palette_lookup(mixer_palette[shared.palette_idx], offset)
            color = fancy.gamma_adjust(color, brightness=bright)
            color_packed = color.pack()
            led_strip[i] = ((color_packed & 0xff0000) >> 16, (color_packed & 0xff00) >> 8, color_packed & 0xff)
        led_strip.write()
        await asyncio.sleep_ms(20)


async def task_twinkle(shared):
    random.seed()
    while True:
        if(shared.flash):
            rand_led = random.randint(0, NUM_LEDS - 1)
            if(rand_led % 2):
                led_strip[rand_led] = (230,220,220)
                led_strip.write()
                await asyncio.sleep_ms(20)
            await asyncio.sleep_ms(500)
        else:
            await asyncio.sleep_ms(1000)


# TODO: revamp
mixer_palette = []

# yoko
mixer_palette.append([
    fancy.CRGB(0.7, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.7, 0.4, 0.0),  # Orange
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.7),  # Blue
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.7, 0.0, 0.4),  # Magenta
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.7, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.7, 0.0, 0.4),  # Magenta
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.7),  # Blue
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.7, 0.4, 0.0),  # Orange
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])

# efficient
mixer_palette.append([
    fancy.CRGB(0.9, 0.0, 0.1),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.8, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.9, 0.0, 0.1),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.8, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])

# brightsafe
mixer_palette.append([
    fancy.CRGB(0.0, 0.4, 0.5),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.5, 0.0, 0.6),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.8, 0.0, 0.7),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.4, 0.6),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.4, 0.5),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.5, 0.0, 0.6),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.8, 0.0, 0.7),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.4, 0.6),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])

# xmas
mixer_palette.append([
    fancy.CRGB(0.0, 0.0, 0.4),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.4, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.8),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.7, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.4),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.4, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.8),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.7, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])


async def main():
    tasks = []
    shared = Shared()
    # tasks
    tasks.append(asyncio.create_task(task_vbat(shared)))
    tasks.append(asyncio.create_task(task_imu(shared)))
    tasks.append(asyncio.create_task(task_blink(shared)))
    tasks.append(asyncio.create_task(task_twinkle(shared)))
    tasks.append(asyncio.create_task(task_led_strip(shared)))
    tasks.append(asyncio.create_task(eb_press(shared)))
    tasks.append(asyncio.create_task(eb_double(shared)))
    # tasks.append(asyncio.create_task(eb_release(shared)))
    tasks.append(asyncio.create_task(eb_long(shared)))
    # tasks.append(asyncio.create_task(task_network(shared)))
    # gc = asyncio.create_task(task_gc())
    repl = asyncio.create_task(aiorepl.task())
    await asyncio.gather(*tasks, repl)


def _stop():
    led_board.fill((0,0,0))
    led_board.write()
    led_strip.fill((0,0,0))
    led_strip.write()


# tidy memory
gc.collect()
# and give info for reference
micropython.mem_info()


try:
    log.info("main", "running")
    asyncio.run(main())
except Exception as excp:
    log.error("main", "exception")
    sys.print_exception(excp)
finally:
    _stop()
    asyncio.new_event_loop()
