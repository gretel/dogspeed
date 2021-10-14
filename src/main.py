import log

# in the beginning there is the declaration of a protocol version
VERSION = const(0x03)

# configuration files to load at runtime
FILE_STREAM_CFG = "/stream.json"
FILE_UID = "/uid.json"

import machine
from machine import Pin, PWM

# onboard led
red_led = Pin(10, Pin.OUT)
red_led.value(0)

import neopixel
import fancyled as fancy

np = neopixel.NeoPixel(machine.Pin(32), 2)
np[0] = (8, 0, 0)
np[1] = (8, 0, 0)
np.write()

button = Pin(37, Pin.IN, Pin.PULL_UP)
pressed = False

def press_button(o):
    print(o)
    pressed = True


button.irq(
    trigger=Pin.IRQ_FALLING,
    handler=press_button,
    wake=machine.SLEEP | machine.DEEPSLEEP
)

# buzzer
buz = PWM(Pin(2, Pin.OUT), freq=440, duty=512)
buz.init()

import ujson

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
import ubinascii

# unique client id
MACHINE_UID = ubinascii.hexlify(machine.unique_id()).decode("utf-8")

try:
    # if exist read last stored uid to prevent wearing flash if no change is required
    r = read_json(FILE_UID)
except OSError as e:
    r = None
finally:
    log.info("uid", MACHINE_UID)

# store if nonexistant or different
if r == None or r["uid"] != MACHINE_UID:
    write_json(FILE_UID, {"uid": MACHINE_UID})

# initiate sensor bus
from machine import SoftI2C

# frequency high, updates lots
i2c = SoftI2C(scl=Pin(22), sda=Pin(21), freq=400000)
log.debug("setup", i2c)

# try:
#     del sys.modules["axp192"]
# except KeyError:
#     pass

import axp192
axp = axp192.AXP192(i2c)

# disable backlight
axp.write(axp192.LDO2_VOLTAGE, 0)

# turn led off
red_led.value(1)

import st7789
import vga1_bold_16x16 as font

spi = machine.SPI(
    2, baudrate=30000000, polarity=1, sck=machine.Pin(13), mosi=machine.Pin(15)
)

lcd = st7789.ST7789(
    spi,
    135,
    240,
    reset=machine.Pin(18, machine.Pin.OUT),
    cs=machine.Pin(5, machine.Pin.OUT),
    dc=machine.Pin(23, machine.Pin.OUT),
)
log.debug("lcd", lcd)
lcd.init()
lcd.fill(st7789.YELLOW)

# enable backlight
axp.write(axp192.LDO2_VOLTAGE, 2.8)

#from mpu6886 import MPU6886, SF_M_S2, SF_DEG_S
from mpu6886 import MPU6886

imu = MPU6886(i2c)
# meters per second, degrees per second
#imu = MPU6886(i2c, accel_sf=SF_M_S2, gyro_sf=SF_DEG_S)
log.debug("imu", imu)
imu_calib = imu.calibrate()
log.info("imu_calib", imu_calib)

import filters
maf = filters.MovingAverageFilter(14)
maf2 = filters.MovingAverageFilter(6)

buz.deinit()

# wireless networking
from wifi_manager import WifiManager

# https://github.com/mitchins/micropython-wifimanager#asynchronous-usage-event-loop
WifiManager.start_managing()
ifconfig = WifiManager.ifconfig()

lcd.fill(st7789.GREEN)

import uasyncio as asyncio
from fusion_async import Fusion

async def read_coro():
    # TODO: validate sleepy time
    await asyncio.sleep_ms(50)
    # go with what is set right now
    return imu.acceleration, imu.gyro

# necessary for long term stability
async def mem_manage():
    while True:
        # wait first
        await asyncio.sleep_ms(100)
        # take the trash down now
        gc.collect()
        # adjust the threshold for the meantime
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())


def notch_cond(val, hi=0, lo=0, ret_true=st7789.WHITE, ret_false=st7789.RED):
    if (lo > 0 and lo >= val) or (hi > 0 and hi <= val):
        return ret_false
    return ret_true


async def display():
    while True:
        lcd.rotation(0)
        lcd.text(font, "dogspeed", 2, 0, st7789.BLACK, 0xAAAA)
        lcd.rotation(1)
        lcd.text(font, MACHINE_UID, 16, 0, st7789.MAGENTA)
        lcd.text(font, ifconfig[0], 16, 16, st7789.WHITE)

        v = axp.read(axp192.BATTERY_VOLTAGE)
        f = "battery: {:2.2f}V".format(v)
        lcd.text(font, f, 16, 32, notch_cond(v, lo=3.3))

        f = "current: {:1.0f}mA".format(axp.read(axp192.DISCHARGE_CURRENT))
        lcd.text(font, f, 16, 48, st7789.YELLOW)

        f = " charge: {:1.0f}mA".format(axp.read(axp192.CHARGE_CURRENT))
        lcd.text(font, f, 16, 64, st7789.YELLOW)

        v = axp.read(axp192.TEMP)
        f = "   temp: {:1.0f}C".format(v)
        lcd.text(font, f, 16, 80, notch_cond(v, hi=45))

        lcd.text(font, "                ", 16, 96, st7789.CYAN)
        f = "  pitch: {:1.0f}".format(fuse.pitch)
        lcd.text(font, f, 16, 96, st7789.CYAN)

        f = "   roll: {:1.0f}".format(fuse.roll)
        lcd.text(font, f, 16, 112, st7789.BLUE)

        await asyncio.sleep_ms(500)


async def blinken():
    while True:
        red_led.value(1)
        # at 100ms it looks kinda good
        await asyncio.sleep_ms(250)
        red_led.value(0)


async def mixer():
    mixer_offset = 0
    mixer_palette = [
        fancy.CRGB(1.0, 0.0, 0.0),  # Red
        fancy.CRGB(0.5, 0.5, 0.0),  # Yellow
        fancy.CRGB(0.0, 1.0, 0.0),  # Green
        fancy.CRGB(0.0, 0.5, 0.5),  # Cyan
        fancy.CRGB(0.0, 0.0, 1.0),  # Blue
        fancy.CRGB(0.5, 0.0, 0.5),  # Magenta
        fancy.CRGB(1.0, 0.0, 1.0),
        fancy.CRGB(1.0, 1.0, 0.0),
        fancy.CRGB(0.0, 1.0, 1.0),
        fancy.CRGB(0.5, 0.0, 0.0),
        fancy.CRGB(0.0, 0.5, 0.0),
        fancy.CRGB(0.0, 0.0, 0.5),
        fancy.CRGB(0.0, 0.0, 0.0),
        fancy.CRGB(0.3, 0.3, 0.3),
    ]

    while True:
        gyro_sum = 0
        for g in imu.gyro:
            gyro_sum += abs(g)

        avg2 = maf2.update(gyro_sum)
        if(avg2 > 5.0):
            print('!avg2', avg2)
        else:
            print(' avg2', avg2)
        
        avg = maf.update(gyro_sum)
        if(avg > 1.5):
            print('!avg ', avg)
        else:
            print(' avg ', avg)

        for i in range(2):
            color = fancy.palette_lookup(mixer_palette, mixer_offset + i / 2)
            color = fancy.gamma_adjust(color, brightness=0.9)
            np[i] = color.plain()
            np.write()
            mixer_offset += 0.003  # spin speed
        await asyncio.sleep_ms(50)

# defaults for socket configuration (target host)
host = "192.168.4.2"
port = 2323
try:
    j = read_json(FILE_STREAM_CFG)
    # override defaults with what we got
    host = j["host"]
    port = j["port"]
except Exception as e:
    # whatever failed above - let's go with the defaults
    log.warning(
        "setup", "unable to parse {}, using defaults".format(FILE_STREAM_CFG)
    )

import usocket
import utime
import ustruct


async def transmit():
    # unreliable datagram protocol ("simplex")
    sock = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
    # reuse address/port combo
    sock.setsockopt(usocket.SOL_SOCKET, usocket.SO_REUSEADDR, 1)
    sock.setblocking(0)
    # bind socket to remote port
    sock.bind(("", port))
    # ok, log
    log.info("tx", "streaming to {}:{}".format(host, port))

    # this should not get called using udp (no disconnections) but let's have it anyway
    def close():
        # byebye
        sock.close()
        log.error("tx", "socket closed")

    try:
        # lookup ipaddress
        serv = usocket.getaddrinfo(host, port)[0][-1]
        # open socket
        sock.connect(serv)
    except OSError as e:
        # tolerate exception and keep on going (wifi will reconnect asynchronously)
        log.error("tx", e)
        return

    # attach writer to socket
    swriter = asyncio.StreamWriter(sock, {})

    # we need to be quick now
    while True:
        try:
            # "header"
            buf = ustruct.pack("12sHI", MACHINE_UID, VERSION, utime.ticks_us())
            # "machine"
            buf += ustruct.pack(
                "4f",
                axp.read(axp192.BATTERY_VOLTAGE),
                axp.read(axp192.DISCHARGE_CURRENT),
                axp.read(axp192.CHARGE_CURRENT),
                axp.read(axp192.TEMP),
            )
            # "payload"
            buf += ustruct.pack(
                "8f",
                imu.acceleration[0],
                imu.acceleration[1],
                imu.acceleration[2],
                imu.gyro[0],
                imu.gyro[1],
                imu.gyro[2],
                fuse.pitch,
                fuse.roll,
            )
            # send struct on the (invisible) wire
            await swriter.awrite(buf)
        except Exception as e:
            # tolerate exception and keep on going (it's udp anyway)
            log.error("tx", e)
            return
        await asyncio.sleep_ms(250)


async def switches():
    global pressed
    while True:
        if pressed:
            await asyncio.sleep_ms(50)
            log.info("pressed!")
            pressed = False
        await asyncio.sleep_ms(100)


async def main():
    await fuse.start()
    await display()

fuse = Fusion(read_coro)

# tidy memory
gc.collect()
# and give info for reference
log.debug("gc", micropython.mem_info())

lcd.fill(st7789.BLACK)

try:
    # tasks
    asyncio.create_task(blinken())
    asyncio.create_task(switches())
    asyncio.create_task(display())
    asyncio.create_task(mixer())
    # TODO: check
    if(WifiManager.wlan().status() == 1010):
        asyncio.create_task(transmit())
    asyncio.create_task(mem_manage())
    # runner
    asyncio.run(main())
except KeyboardInterrupt:
    # humans
    log.warning("main", "interrupted")
finally:
    # loop
    _ = asyncio.new_event_loop()
