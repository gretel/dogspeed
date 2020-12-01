# in the beginning there is a declaration of a version string
VERSION = const(0x01)

FILE_STREAM_CFG = '/stream.json'
FILE_MAG_CAL = '/mag_cal.json'

# bring the noise
import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('dogspeed')

import neopixel
# single rgb (3 bit) led
np = neopixel.NeoPixel(machine.Pin(15), 1, bpp=3)

# one neopixel led
def pixel(r=0, g=0, b=0):
    np[0] = (r, g, b)
    np.write()

# code red
pixel(0, 0, 32)

# wireless networking
from wifi_manager import WifiManager
# https://github.com/mitchins/micropython-wifimanager#asynchronous-usage-event-loop
log.info(WifiManager.start_managing())

# code green
pixel(0, 32, 0)

# inititate sensor bus
from machine import I2C, Pin
# frequency high, updates lots
i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000)
log.debug(i2c)

import ujson

# inhale json
def read_json(filename):
    with open(filename, 'r') as f:
        j = ujson.loads(f.read())
        f.close()
        return j

# defaults
offset=(0, 0, 0)
scale=(1, 1, 1)

try:
    # magnetometer calibration data
    j = read_json(FILE_MAG_CAL)
    # override defaults
    offset=j['offset']
    scale=j['scale']
except Exception as e:
    log.warning(e, 'unable to parse {}, using defaults'.format(FILE_MAG_CAL))
finally:
    log.info('magnetometer calibration offset: {}, scale: {}'.format(offset, scale))

from mpu9250 import MPU9250
dummy = MPU9250(i2c) # this opens the bybass to access to the AK8963
from ak8963 import AK8963
# use bypass to set calibration data
ak8963 = AK8963(
    i2c,
    offset=offset,
    scale=scale
)
# finally initialize inertial measurement unit
imu = MPU9250(i2c, ak8963=ak8963)
log.debug(imu)

import uasyncio as asyncio
from fusion_async import Fusion

async def read_coro():
    # TODO: validate sleepy time
    await asyncio.sleep_ms(10)
    return imu.acceleration, imu.gyro, imu.magnetic

fuse = Fusion(read_coro)

# necessary for long term stability
async def mem_manage(): # 
    while True:
        await asyncio.sleep_ms(100)
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())

async def display():
    fs = 'yaw: {:4.0f} pitch: {:4.0f} roll: {:4.0f}'
    while True:
        log.info(fs.format(fuse.heading, fuse.pitch, fuse.roll))
        await asyncio.sleep_ms(500)

async def blinken():
    def convert(f):
        return int(abs(f)*8)%255

    while True:
        pixel(convert(imu.gyro[0]), convert(imu.gyro[1]), convert(imu.gyro[2]))
        await asyncio.sleep_ms(100)

# defaults
host = '192.168.4.2'
port = 2323

try:
    j = read_json(FILE_STREAM_CFG)
    # override defaults
    host=j['host']
    port=j['port']
except Exception as e:
    log.warning(e, 'unable to parse {}, using defaults'.format(FILE_STREAM_CFG))
finally:
    log.info('streaming to {}:{}'.format(host, port))

import usocket
import utime

async def transmit():
    # unreliable datagrams ("simplex")
    sock = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)

    def close():
        sock.close()
        log.error('server disconnected')

    log.info('socket to {} on port {}'.format(host, port))
    try:
        # get ipaddress
        serv = usocket.getaddrinfo(host, port)[0][-1]
        # open socket
        sock.connect(serv)
    except OSError as e:
        close()
        #return
        raise

    # identify ourselves uniquely
    import ubinascii
    # unique client id
    MACHINE_UID = ubinascii.hexlify(machine.unique_id()).decode('utf-8')
    log.debug('machine uid {}'.format(MACHINE_UID))

    # say hi
    data = {'uid': MACHINE_UID, 'ver': VERSION}

    # attach writer and socket
    swriter = asyncio.StreamWriter(sock, {})
    await swriter.awrite('\n' + ujson.dumps(data))

    while True:
        # compose data to stream
        data = {'t':utime.ticks_us(),
        'c':imu.temperature, 
        'a':imu.acceleration, 
        'g':imu.gyro, 
        'm':imu.magnetic, 
        'f' : {'y':fuse.heading, 'p':fuse.pitch, 'r':fuse.roll}}
        try:
            # encode and put on the (invisible) wire
            await swriter.awrite(ujson.dumps(data))
        except Exception as e:
            log.error(e)
            # gracefully
            return
        await asyncio.sleep_ms(20)

async def main():
    # esp8266 - https://github.com/micropython-IMU/micropython-fusion#311-methods
    await fuse.start(slow_platform=True)
    await display()

# tidy memory
gc.collect()
# and give info
log.debug(micropython.mem_info())

# all lights green
pixel(0, 64, 0)

try:
    # tasks
    asyncio.create_task(mem_manage())
    asyncio.create_task(display())
    asyncio.create_task(blinken())
    asyncio.create_task(transmit())
    # runner
    asyncio.run(main())
except KeyboardInterrupt:
    pixel(16, 0, 8)
    log.warning('interrupted')
finally:
    # loop
    _ = asyncio.new_event_loop()
