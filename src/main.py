# in the beginning there is the declaration of a protocol version
VERSION = const(0x02)

# configuration files to load at runtime
FILE_STREAM_CFG = '/stream.json'
FILE_UID = '/uid.json'

# the past was the future of yesterday so get on logging now
import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('dogspeed')

from machine import Pin, PWM
# onboard led
red_led = Pin(10, Pin.OUT)
red_led.value(0)

import neopixel
np = neopixel.NeoPixel(machine.Pin(32), 2)
np[0] = (64,0,0)
np[1] = (0,0,64)
np.write()

# buzzer
# buz = PWM(Pin(2, Pin.OUT))
# buz.duty(0)

import ujson
# inhale json
def read_json(filename):
    log.debug('reading {}'.format(filename))
    with open(filename, 'r') as f:
        j = ujson.loads(f.read())
        f.close()
        return j

# exhale json
def write_json(filename, j):
    log.debug('writing {}'.format(filename))
    with open(filename, 'w') as f:
        ujson.dump(j, f)
        f.close()

# identify ourselves uniquely
import ubinascii
# unique client id
MACHINE_UID = ubinascii.hexlify(machine.unique_id()).decode('utf-8')

try:
    # if exist read last stored uid to prevent wearing flash if no change is required
    r = read_json(FILE_UID)
except OSError as e:
    r = None
finally:
    log.info('machine uid {}'.format(MACHINE_UID))

# store if nonexistant or different
if(r == None or r['uid'] != MACHINE_UID):
    write_json(FILE_UID, {'uid': MACHINE_UID})

# initiate sensor bus
from machine import SoftI2C
# frequency high, updates lots
i2c = SoftI2C(scl=Pin(22), sda=Pin(21), freq=400000)
log.debug(i2c)

try:
    del sys.modules['axp192']
except KeyError:
    pass
from axp192 import AXP192
axp = AXP192(i2c)
axp.setup()

# disable backlight
axp.set_LD02(False)
# turn led off
red_led.value(1)

import st7789
import vga1_bold_16x16 as font
spi = machine.SPI(2,
    baudrate=30000000, polarity=1,
    sck=machine.Pin(13),
    mosi=machine.Pin(15))
lcd = st7789.ST7789(spi,
    135, 240, 
    reset=machine.Pin(18, machine.Pin.OUT),
    cs=machine.Pin(5, machine.Pin.OUT),
    dc=machine.Pin(23, machine.Pin.OUT))
log.debug(lcd)
lcd.init()
lcd.fill(st7789.YELLOW)
# lcd backlight
axp.set_LD02(True)

from mpu6886 import MPU6886, SF_M_S2, SF_DEG_S
# meters per second, degrees per second
imu = MPU6886(i2c, accel_sf=SF_M_S2, gyro_sf=SF_DEG_S)
log.debug(imu)

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
    await asyncio.sleep_ms(20)
    # go with what is set right now
    return imu.acceleration, imu.gyro
fuse = Fusion(read_coro)

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
    if((lo > 0 and lo >= val) or (hi > 0 and hi <= val)):
        return ret_false
    return ret_true

async def display():
    while True:
        lcd.rotation(0)
        lcd.text(font, 'dogspeed', 2, 0, st7789.BLACK, 0xAAAA)
        lcd.rotation(1)
        lcd.text(font, MACHINE_UID, 16, 0, st7789.MAGENTA)
        lcd.text(font, ifconfig[0], 16, 16, st7789.WHITE)

        v = axp.battery_voltage()
        f = 'battery: {:2.2f}V'.format(v)
        lcd.text(font, f, 16, 32, notch_cond(v, lo=3.3))

        f = 'current: {:1.0f}mA'.format(axp.battery_current())
        lcd.text(font, f, 16, 48, st7789.YELLOW)

        f = ' charge: {:1.0f}mA'.format(axp.battery_charge_current())
        lcd.text(font, f, 16, 64, st7789.YELLOW)

        v = axp.temperature()
        f = '   temp: {:1.0f}C'.format(v)
        lcd.text(font, f, 16, 80, notch_cond(v, hi=45))

        f = '  pitch: {:1.0f}'.format(fuse.pitch)
        lcd.text(font, f, 16, 96, st7789.CYAN)

        f = '   roll: {:1.0f}'.format(fuse.roll)
        lcd.text(font, f, 16, 112, st7789.BLUE)
        await asyncio.sleep_ms(500)

async def blinken():
    while True:
        red_led.value(1)
        # at 100ms it looks kinda good
        await asyncio.sleep_ms(250)
        red_led.value(0)

# defaults for socket configuration (target host)
host = '192.168.4.2'
port = 2323
try:
    j = read_json(FILE_STREAM_CFG)
    # override defaults with what we got
    host=j['host']
    port=j['port']
except TypeError as e:
    # whatever failed above - let's go with the defaults
    log.warning(e, 'unable to parse {}, using defaults'.format(FILE_STREAM_CFG))

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
    sock.bind(('', port))
    # ok, log
    log.info('streaming to {}:{}'.format(host, port))

    # this should not get called using udp (no disconnections) but let's have it anyway
    def close():
        # byebye
        sock.close()
        log.error('socket closed')

    try:
        # lookup ipaddress
        serv = usocket.getaddrinfo(host, port)[0][-1]
        # open socket
        sock.connect(serv)
    except OSError as e:
        # tolerate exception and keep on going (wifi will reconnect asynchronously)
        log.error(e)
        return

    # attach writer to socket
    swriter = asyncio.StreamWriter(sock, {})

    # we need to be quick now
    while True:
        try:
            # "header"
            buf = ustruct.pack('12sHI', MACHINE_UID, VERSION, utime.ticks_us())
            # "machine"
            buf += ustruct.pack('4f', axp.battery_voltage(), axp.battery_current(), axp.battery_charge_current(), axp.temperature())
            # "payload"
            buf += ustruct.pack('8f', imu.acceleration[0], imu.acceleration[1], imu.acceleration[2], imu.gyro[0], imu.gyro[1], imu.gyro[2], fuse.pitch, fuse.roll)
            # send struct on the (invisible) wire
            await swriter.awrite(buf)
        except Exception as e:
            # tolerate exception and keep on going (it's udp anyway)
            log.error(e)
            return
        await asyncio.sleep_ms(20)

async def main():
    await fuse.start()
    await display()

# tidy memory
gc.collect()
# and give info for reference
log.debug(micropython.mem_info())

lcd.fill(st7789.BLACK)

try:
    # tasks
    asyncio.create_task(mem_manage())
    asyncio.create_task(display())
    asyncio.create_task(blinken())
    asyncio.create_task(transmit())
    # runner
    asyncio.run(main())
except KeyboardInterrupt:
    # humans
    log.warning('interrupted')
finally:
    # loop
    _ = asyncio.new_event_loop()
