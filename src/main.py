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
import aioprof
import aiorepl
import filters
#from wifi_manager import WifiManager

class Shared:
    def __init__(self):
        self.balance = 0
        self.palette_idx = 0
        self.rot_avg_short = 0
        self.rot_avg_long = 0
        self.vbat = 0

        self.bright = 0.6
        self.delta = 0
        self.flash = 1
        self.ifconfig = {}
        self.low_power = False
        self.zero_motion = False


# in the beginning there is the declaration of a protocol version
VERSION = const(0x06)
VBAT_CORR = const(218)
NUM_LEDS = const(44)
LOW_ACCEL_THRESH = const(5200)
OFFSET_INCR_DIV = const(640000)
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
        await button.press.wait()  # Wait for button press event
        button.press.clear()  # Clear the event flag
        shared.palette_idx = (shared.palette_idx + 1) % len(mixer_palette)
        # Log the updated palette index directly
        log.info('btn', 'palette: {}'.format(shared.palette_idx))


async def eb_long(shared):
    while True:
        await button.long.wait()  # Wait for long-press event
        button.long.clear()  # Clear the event flag
        shared.low_power = not shared.low_power  # Toggle the low_power state
        shared.balance = -0.4 if shared.low_power else 0
        # Log the current low_power state and balance directly
        log.info('btn', 'low_power: {}, balance: {}'.format(shared.low_power, shared.balance))


async def eb_double(shared):
    while True:
        await button.double.wait()  # Wait for double-click event
        button.double.clear()  # Clear the event flag
        shared.flash = not shared.flash  # Toggle the flash state
        log.info('btn', 'flash: {}'.format(shared.flash))  # Log the current flash state directly


def read_json(filename):
    try:
        with open(filename, "r") as f:
            return ujson.load(f)
    except (OSError, ValueError) as e:
        log.error("json", f"Error reading/parsing {filename}: {e}")
    return None


def write_json(filename, data):
    log.info("json", f"writing {filename}")
    with open(filename, "w") as f:
        ujson.dump(data, f)


MACHINE_UID = ubinascii.hexlify(machine.unique_id()).decode("utf-8")

try:
    stored_uid = read_json(FILE_UID)
except (OSError, ValueError):
    stored_uid = None

if not stored_uid or stored_uid.get("uid") != MACHINE_UID:
    write_json(FILE_UID, {"uid": MACHINE_UID})

log.info("uid", MACHINE_UID)


# frequency high, updates lots
i2c = SoftI2C(scl=Pin(21), sda=Pin(25), freq=400000)  # SCL: GPIO21, SDA: GPIO25
# print(i2c.scan())
log.debug('i2c', i2c)


# Initialize BMI160 IMU
imu = BMI160_I2C(i2c)
# Configure IMU settings
imu.set_accel_rate(7)  # Set accelerometer data rate
imu.setFullScaleAccelRange(0X05)  # Set accelerometer full-scale range to ±4g
imu.set_gyro_rate(7)  # Set gyroscope data rate
imu.setFullScaleGyroRange(3)  # Set gyroscope full-scale range to ±250 deg/s
imu.setZeroMotionDetectionDuration(1)  # Set zero motion detection duration to 1 second
imu.setZeroMotionDetectionThreshold(2)  # Set zero motion detection threshold to 2
imu.setIntZeroMotionEnabled(True)  # Enable zero motion interrupt
log.debug('imu', 'temperature: {}'.format(imu.getTemperature()))


async def task_imu(shared):
   maf_long = filters.MovingAverageFilter(10)
   maf_short = filters.MovingAverageFilter(4)

   prev_rotations = [0, 0, 0]  # Initialize previous rotation values
   sum_rotation = 0  # Initialize sum of absolute rotations

   while True:
       rotations = imu.getRotation()
       # Update sum_rotation incrementally
       sum_rotation -= sum(abs(x) for x in prev_rotations)
       sum_rotation += sum(abs(x) for x in rotations)
       prev_rotations = rotations

       shared.rot_avg_long = maf_long.update(sum_rotation)
       shared.rot_avg_short = maf_short.update(sum_rotation)
       shared.zero_motion = imu.getIntZeroMotionStatus()

       if shared.zero_motion:
           log.info('imu', 'zero motion interrupt')
           sleep_time = 1000
       else:
           # Adjust sleep_time based on the rate of change in sensor data
           shared.delta = int(abs(sum_rotation - shared.rot_avg_long))
           sleep_time = max(50, 200 - shared.delta // 10)

       await asyncio.sleep_ms(sleep_time)


async def task_vbat(shared):
    # Precompute constant for voltage conversion
    VBAT_CONV_FACTOR = 0.00080586 * 2.18  # (3.3 / 4095 * VBAT_CORR / 100)

    while True:
        # Read ADC and convert to voltage
        val = vbat_adc.read()
        shared.vbat = round(val * VBAT_CONV_FACTOR, 2)

        if shared.vbat > 0:
            log.debug('vbat', '%sV', shared.vbat)

        # Adjust sleep time based on voltage level to reduce frequency of checks
        if shared.vbat > 3.5:
            sleep_time = 3000
        elif shared.vbat > 3.2:
            sleep_time = 2000
        else:
            sleep_time = 1000

        await asyncio.sleep_ms(sleep_time)


async def task_blink(shared):
    while True:
        vbat = shared.vbat
        if vbat > 4.0:
            color = (0, 10, 0, 0)
            sleep_time = 1500
            shared.balance = 0
        elif vbat > 3.8:
            color = (5, 5, 0, 0)
            sleep_time = 1000
            shared.balance = -0.1
        elif vbat > 3.5:
            color = (10, 0, 0, 0)
            sleep_time = 750
            shared.balance = -0.3
        elif vbat > 3.2:
            color = (10, 0, 5, 0)
            sleep_time = 500
            shared.balance = -0.5
            shared.low_power = True
        else:
            color = (0, 0, 10, 0)
            sleep_time = 1000
            shared.balance = 0
            shared.low_power = False

        led_board[0] = color
        led_board.write()
        await asyncio.sleep(0.02)
        led_board[0] = (0, 0, 0)
        led_board.write()
        await asyncio.sleep(sleep_time / 1000)


# async def task_network(shared):
#     WifiManager.start_managing()
#     await asyncio.sleep_ms(250)  # Adjust sleep duration as needed
#     try:
#         while True:
#             # Check if WiFi is connected
#             if WifiManager.wlan().status() == 1010:
#                 shared.ifconfig = WifiManager.ifconfig()
#                 log.info('net', 'connected: {}'.format(shared.ifconfig))
#                 return  # Exit function once connected
#             await asyncio.sleep_ms(500)  # Adjust sleep duration as needed
#     except Exception as e:
#         log.error('net', 'error connecting to wifi: {}'.format(e))


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

        sleep_time = max(20, 100 - shared.delta // 10)
        #print(sleep_time)
        await asyncio.sleep_ms(sleep_time)


async def task_twinkle(shared):
    random.seed()
    flash_delay = 20  # Delay in milliseconds for the flash
    no_flash_delay = 1000  # Delay in milliseconds for no flash

    while True:
        if shared.flash:
            rand_led = random.randint(0, NUM_LEDS - 1)
            led_strip[rand_led] = (210, 210, 210) if rand_led % 2 else (0, 0, 0)
            led_strip.write()
            await asyncio.sleep_ms(flash_delay)
            led_strip[rand_led] = (0, 0, 0)  # Turn off the LED
            led_strip.write()
            await asyncio.sleep_ms(600 - flash_delay)  # Compensate for the flash delay
        else:
            await asyncio.sleep_ms(no_flash_delay)


async def task_prof():
    while True:
        aioprof.report()
        await asyncio.sleep_ms(5000)


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

aioprof.enable()

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
    tasks.append(asyncio.create_task(eb_long(shared)))
    # tasks.append(asyncio.create_task(task_network(shared)))

    # gc = asyncio.create_task(task_gc())
    # tasks.append(asyncio.create_task(task_prof()))
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
