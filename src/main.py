import log
import sys
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


class Shared:
    def __init__(self):
        self.balance = 0
        self.bright_ext = 0.7
        self.bright_int = 0.9
        self.flash = 1
        self.ifconfig = {}
        self.low_power = False
        self.palette_idx = 0
        self.vbat = 0


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
            shared.balance = -0.3
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
imu.set_accel_rate(6)
imu.set_gyro_rate(6)
imu.setAccelDLPFMode(0)
imu.setFullScaleAccelRange(5, 5)
# imu.setFullScaleGyroRange(3, 3)

# imu.setZeroMotionDetectionDuration(1)
# imu.setZeroMotionDetectionThreshold(0x02)
# imu.setIntZeroMotionEnabled(True)

log.debug('imu', 'temperature: {}'.format(imu.getTemperature()))


async def task_vbat(shared):
    while True:
        # Read ADC and convert to voltage
        val = vbat_adc.read()
        # TODO: abstraction
        val = val * (3.3 / 4095) * 2.18  # correction 2.18
        shared.vbat = round(val, 2)

        if(val > 0):
            log.debug('vbat', '%sV', shared.vbat)
            await asyncio.sleep_ms(500)
        else:
            await asyncio.sleep_ms(1500)


async def task_blink(shared):
    # FIXME: concerns
    while True:
        vbat = shared.vbat
        if vbat > 4.0:
            color = (0, 10, 0, 0)
            sleep_time = 1500
        elif vbat > 3.7:
            color = (5, 5, 0, 0)
            sleep_time = 1000
        elif vbat > 3.5:
            color = (10, 0, 0, 0)
            sleep_time = 750
            # FIXME: sync
            shared.balance = -0.3
        elif vbat > 3.2:
            sleep_time = 500
            color = (10, 0, 5, 0)
            # FIXME: sync
            shared.balance = -0.4
            shared.low_power = True
        else:
            sleep_time = 1000
            color = (0, 0, 10, 0)

        led_board[0] = color
        led_board.write()
        await asyncio.sleep_ms(10)
        led_board[0] = (0, 0, 0)
        led_board.write()
        await asyncio.sleep_ms(sleep_time)


async def task_network(shared):
    # https://github.com/mitchins/micropython-wifimanager#asynchronous-usage-event-loop
    WifiManager.start_managing()
    while True:
        if (WifiManager.wlan().status() == 1010):
            shared.ifconfig = WifiManager.ifconfig()
            # got connected
            log.info('net', 'connected: {}'.format(shared.ifconfig))
            # done here
            return
        await asyncio.sleep_ms(250)


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
        bright = shared.bright_ext + shared.balance

        axis_sum = 0
        for a in imu.getRotation():
            axis_sum += abs(a)

        avg = maf.update(axis_sum)
        if (avg < 500):
            avg = 500

        # TODO: abstraction
        mixer_offset += avg / 750000
        # mixer_offset += axis_sum / 600000

        for i in range(NUM_LEDS_EXT):
            offset = mixer_offset + i / NUM_LEDS_EXT
            color = fancy.palette_lookup(mixer_palette[shared.palette_idx], offset)
            color = fancy.gamma_adjust(color, brightness=bright)
            color_packed = color.pack()
            led_ext[i] = ((color_packed & 0xff0000) >> 16, (color_packed & 0xff00) >> 8, color_packed & 0xff)

        led_ext.write()
        await asyncio.sleep_ms(30)


async def task_led_int(shared):
    maf = filters.MovingAverageFilter(4)

    side = 0
    sleep_time = 100
    white = 100

    while True:
        bright = shared.bright_int + shared.balance

        if(not shared.flash):
            sleep_time = 500

            # force off
            led_int[0] = (0,0,0,0)
            led_int[1] = (0,0,0,0)
            led_int.write()
        else:
            axis_sum = 0
            for a in imu.getRotation():
                axis_sum += abs(a)

            avg = maf.update(axis_sum)

            # TODO: abstraction
            if(avg < 4800):
                if(side):
                    sleep_time = 50

                    color = fancy.gamma_adjust(fancy.CRGB(1.0, 1.0, 1.0), brightness=bright)
                    color_packed = color.pack()
                    led_int[0] = ((color_packed & 0xff0000) >> 16, (color_packed & 0xff00) >> 8, color_packed & 0xff, white)
                else:
                    sleep_time = 500

                    color = fancy.gamma_adjust(fancy.CRGB(1.0, 1.0, 1.0), brightness=bright)
                    color_packed = color.pack()
                    led_int[1] = ((color_packed & 0xff0000) >> 16, (color_packed & 0xff00) >> 8, color_packed & 0xff, white)

                led_int.write()
                await asyncio.sleep_ms(20)

                # off
                led_int[0] = (0,0,0,0)
                led_int[1] = (0,0,0,0)
                led_int.write()

        # toggle
        side ^= 1
        await asyncio.sleep_ms(sleep_time)


# TODO: revamp
mixer_palette = []
mixer_palette.append([
    fancy.CRGB(0.8, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.7, 0.4, 0.0),  # Orange
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.8),  # Blue
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.8, 0.0, 0.4),  # Magenta
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.8, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.8, 0.0, 0.4),  # Magenta
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.8),  # Blue
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.7, 0.4, 0.0),  # Orange
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
    fancy.CRGB(0.8, 0.0, 0.0),  # Red
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
    fancy.CRGB(0.8, 0.0, 0.0),  # Red
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])

mixer_palette.append([
    fancy.CRGB(0.1, 0.7, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.6, 0.0, 0.7),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 1.0, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.5, 0.5),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.1, 0.7, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.6, 0.0, 0.7),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 1.0, 0.0),  # Green
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.5, 0.5),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])

mixer_palette.append([
    fancy.CRGB(0.9, 0.4, 0.0),
    fancy.CRGB(0.6, 0.5, 0.3),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.9, 0.4, 0.0),
    fancy.CRGB(0.6, 0.5, 0.3),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.9, 0.4, 0.0),
    fancy.CRGB(0.6, 0.5, 0.3),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.9, 0.4, 0.0),
    fancy.CRGB(0.6, 0.5, 0.3),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),    
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.9, 0.4, 0.0),
    fancy.CRGB(0.6, 0.5, 0.3),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])

mixer_palette.append([
    fancy.CRGB(0.7, 0.0, 0.8),
    fancy.CRGB(0.0, 0.6, 0.0),
    fancy.CRGB(0.0, 0.6, 0.0),
    fancy.CRGB(0.0, 0.6, 0.0),
    fancy.CRGB(0.0, 0.9, 0.0),
    fancy.CRGB(0.0, 0.6, 0.0),
    fancy.CRGB(0.0, 0.6, 0.0),
    fancy.CRGB(0.0, 0.6, 0.0),
    fancy.CRGB(0.0, 0.6, 0.0),
    fancy.CRGB(0.7, 0.0, 0.8),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 1.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
    fancy.CRGB(0.0, 0.0, 0.0),
])

def _stop():
    led_board.fill((0,0,0))
    led_board.write()
    led_int.fill((0,0,0,0))
    led_int.write()
    led_ext.fill((0,0,0))
    led_ext.write()


async def main():
    tasks = []
    shared = Shared()

    # tasks
    tasks.append(asyncio.create_task(task_vbat(shared)))
    tasks.append(asyncio.create_task(task_blink(shared)))
    tasks.append(asyncio.create_task(task_led_int(shared)))
    tasks.append(asyncio.create_task(task_led_ext(shared)))

    tasks.append(asyncio.create_task(eb_press(shared)))
    tasks.append(asyncio.create_task(eb_double(shared)))
    # tasks.append(asyncio.create_task(eb_release(shared)))
    tasks.append(asyncio.create_task(eb_long(shared)))

    # tasks.append(asyncio.create_task(task_network(shared)))
    # gc = asyncio.create_task(task_gc())
    repl = asyncio.create_task(aiorepl.task())
    await asyncio.gather(*tasks, repl)


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
