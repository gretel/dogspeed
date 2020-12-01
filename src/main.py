# in the beginning there is the declaration of a protocol version
VERSION = const(0x01)

# configuration files to load at runtime
FILE_STREAM_CFG = '/stream.json'
FILE_MAG_CAL = '/mag_cal.json'

# the past was the future of yesterday so get on logging now
import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('dogspeed')

import neopixel
# single rgb (3 bit) led blinky blinky
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

# initiate sensor bus
from machine import I2C, Pin
# frequency high, updates lots
# datasheet of 'gy-91' states 400000 as maximum but it's running fine at 800000
i2c = I2C(scl=Pin(5), sda=Pin(4), freq=400000)
log.debug(i2c)

import ujson
# inhale json
def read_json(filename):
    with open(filename, 'r') as f:
        j = ujson.loads(f.read())
        f.close()
        return j

# defaults of the magnetometer calibration data
offset=(0, 0, 0)
scale=(1, 1, 1)

try:
    # read the file hoping for data
    j = read_json(FILE_MAG_CAL)
    # override defaults
    offset=j['offset']
    scale=j['scale']
except Exception as e:
    # whatever failed above - let's go with the defaults
    log.warning(e, 'unable to parse {}, using defaults'.format(FILE_MAG_CAL))
finally:
    log.info('magnetometer calibration offset: {}, scale: {}'.format(offset, scale))

# imu
from mpu9250 import MPU9250
dummy = MPU9250(i2c) # this opens the "bybass" to access to the AK8963 directly
from ak8963 import AK8963
# use bypass to pass calibration data
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
    # go with what is set right now
    return imu.acceleration, imu.gyro, imu.magnetic
fuse = Fusion(read_coro)

# necessary for long term stability
async def mem_manage(): # 
    while True:
        # wait first
        await asyncio.sleep_ms(100)
        # take the trash down now
        gc.collect()
        # adjust the threshold for the meantime
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())

async def display():
    # template
    fs = 'yaw: {:4.0f} pitch: {:4.0f} roll: {:4.0f}'
    while True:
        log.info(fs.format(fuse.heading, fuse.pitch, fuse.roll))
        # this not urgent
        await asyncio.sleep_ms(500)

async def blinken():
    def convert(f):
        # the imu returns signed floats (+/-) so we just get rid of the prefix and (up)scale the value
        return int(abs(f)*8)%255
    while True:
        # TODO: some nice hsv color math
        pixel(convert(imu.gyro[0]), convert(imu.gyro[1]), convert(imu.gyro[2]))
        # at 100ms it looks kinda good
        await asyncio.sleep_ms(100)

# defaults for socket configuration (target host)
host = '192.168.4.2'
port = 2323

try:
    j = read_json(FILE_STREAM_CFG)
    # override defaults with what we got
    host=j['host']
    port=j['port']
except Exception as e:
    # whatever failed above - let's go with the defaults
    log.warning(e, 'unable to parse {}, using defaults'.format(FILE_STREAM_CFG))
finally:
    log.info('streaming to {}:{}'.format(host, port))

import usocket
import utime
async def transmit():
    # unreliable datagram protocol ("simplex")
    sock = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
    # this should not get called using udp (no disconnections) but let's have it anyway
    def close():
        # byebye
        sock.close()
        log.error('server disconnected')

    log.info('socket to {} on port {}'.format(host, port))
    try:
        # get ipaddress
        serv = usocket.getaddrinfo(host, port)[0][-1]
        # open socket
        sock.connect(serv)
    except OSError as e:
        # tolerate exception and keep on going (wifi will reconnect asynchronously)
        log.error(e)
        return

    # identify ourselves uniquely
    import ubinascii
    # unique client id
    MACHINE_UID = ubinascii.hexlify(machine.unique_id()).decode('utf-8')
    log.debug('machine uid {}'.format(MACHINE_UID))

    # attach writer and socket
    swriter = asyncio.StreamWriter(sock, {})

    # sort of protocol header - we say hi telling our name and number ;)
    await swriter.awrite('\n' + ujson.dumps({'uid': MACHINE_UID, 'ver': VERSION}))

    # we need to be quick now
    # TODO: try without the catch (latency is a biatch)
    while True:
        try:
            # encode and send the actual payload on the (invisible) wire
            await swriter.awrite(ujson.dumps({'t':utime.ticks_us(),
                'c':imu.temperature, 
                'a':imu.acceleration, 
                'g':imu.gyro, 
                'm':imu.magnetic, 
                'f' : {'y':fuse.heading, 'p':fuse.pitch, 'r':fuse.roll}}))
        except Exception as e:
            # tolerate exception and keep on going (it's udp anyway)
            # TODO: this might flood out - remove when robustnes is proven
            log.error(e)
            return
        await asyncio.sleep_ms(20)

async def main():
    # esp8266 not superfast - https://github.com/micropython-IMU/micropython-fusion#311-methods
    await fuse.start(slow_platform=True)
    await display()

# tidy memory
gc.collect()
# and give info for reference
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
    # humans
    pixel(16, 0, 8)
    log.warning('interrupted')
finally:
    # loop
    _ = asyncio.new_event_loop()
