import log

# in the beginning there is the declaration of a protocol version
VERSION = const(0x04)
NUM_LEDS = const(3)

# configuration files to load at runtime
#FILE_MAG_CAL = '/mag_cal.json'
FILE_STREAM_CFG = "/stream.json"
FILE_UID = "/uid.json"

import machine
from machine import Pin, PWM

import neopixel
import fancyled as fancy

board_led = neopixel.NeoPixel(machine.Pin(2), 1)
board_led[0] = (0, 4, 0)
board_led.write()

np = neopixel.NeoPixel(machine.Pin(1), NUM_LEDS, bpp=4)
np[0] = (8, 0, 0, 0)
np[1] = (0, 8, 0, 0)
np[2] = (0, 0, 8, 0)
np.write()

button = Pin(9, Pin.IN, Pin.PULL_UP)
pressed = False

def press_button(o):
    print(o)
    pressed = True

button.irq(
    trigger=Pin.IRQ_FALLING,
    handler=press_button,
    wake=machine.SLEEP | machine.DEEPSLEEP
)

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
i2c = SoftI2C(scl=Pin(7), sda=Pin(6), freq=400000)
log.debug('i2c', i2c)

# # defaults of the magnetometer calibration data
# offset=(0, 0, 0)
# scale=(1, 1, 1)

# try:
#     # read the file hoping for data
#     j = read_json(FILE_MAG_CAL)
#     # override defaults
#     offset=j['offset']
#     scale=j['scale']
# except Exception as e:
#     # whatever failed above - let's go with the defaults
#     log.warning(e, 'unable to parse {}, using defaults'.format(FILE_MAG_CAL))
# finally:
#     log.info('imu', 'magnetometer calibration offset: {}, scale: {}'.format(offset, scale))

# imu
from imu import MPU6050
dummy = MPU6050(i2c) # this opens the "bybass" to access to the AK8963 directly

# finally initialize inertial measurement unit
imu = MPU6050(i2c)
log.debug('imu', imu)

import filters
maf = filters.MovingAverageFilter(14)
maf2 = filters.MovingAverageFilter(6)

# wireless networking
from wifi_manager import WifiManager

# https://github.com/mitchins/micropython-wifimanager#asynchronous-usage-event-loop
WifiManager.start_managing()
ifconfig = WifiManager.ifconfig()

import uasyncio as asyncio
import aiorepl


from fusion_async import Fusion


async def read_coro():
    # TODO: validate sleepy time
    await asyncio.sleep_ms(50)
    # go with what is set right now
    return imu.accel, imu.gyro


# necessary for long term stability
async def mem_manage():
    while True:
        # wait first
        await asyncio.sleep_ms(1000)
        # take the trash down now
        gc.collect()
        # adjust the threshold for the meantime
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())


async def blinken():
    while True:
        board_led[0] = (0, 0, 0)
        board_led.write()
        # at 100ms it looks kinda good
        await asyncio.sleep_ms(500)
        board_led[0] = (0, 8, 0)
        board_led.write()


async def mixer():
    #mixer_offset = 0
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
        for g in imu.gyro.xyz:
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

        for i in range(NUM_LEDS):
            #color = fancy.palette_lookup(mixer_palette, mixer_offset + i / 2)
            color = fancy.palette_lookup(mixer_palette, i)
            color = fancy.gamma_adjust(color, brightness=0.8)
            np[i] = (2,2,0,0)
            #np[i] = color.pack(fancy.gamma_adjust(i / 2))
            np.write()
            #mixer_offset += 0.003  # spin speed
        await asyncio.sleep_ms(50)

# # defaults for socket configuration (target host)
# host = "192.168.4.2"
# port = 2323
# try:
#     j = read_json(FILE_STREAM_CFG)
#     # override defaults with what we got
#     host = j["host"]
#     port = j["port"]
# except Exception as e:
#     # whatever failed above - let's go with the defaults
#     log.warning(
#         "setup", "unable to parse {}, using defaults".format(FILE_STREAM_CFG)
#     )


# import usocket
# import utime
# import ustruct

# async def transmit():
#     # unreliable datagram protocol ("simplex")
#     sock = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
#     # reuse address/port combo
#     sock.setsockopt(usocket.SOL_SOCKET, usocket.SO_REUSEADDR, 1)
#     sock.setblocking(0)
#     # bind socket to remote port
#     sock.bind(("", port))
#     # ok, log
#     log.info("tx", "streaming to {}:{}".format(host, port))

#     # this should not get called using udp (no disconnections) but let's have it anyway
#     def close():
#         # byebye
#         sock.close()
#         log.error("tx", "socket closed")

#     try:
#         # lookup ipaddress
#         serv = usocket.getaddrinfo(host, port)[0][-1]
#         # open socket
#         sock.connect(serv)
#     except OSError as e:
#         # tolerate exception and keep on going (wifi will reconnect asynchronously)
#         log.error("tx", e)
#         return

#     # attach writer to socket
#     swriter = asyncio.StreamWriter(sock, {})

#     # we need to be quick now
#     while True:
#         try:
#             # "header"
#             buf = ustruct.pack("12sHI", MACHINE_UID, VERSION, utime.ticks_us())
#             # "payload"
#             buf += ustruct.pack(
#                 "8f",
#                 imu.accel.x,
#                 imu.accel.y,
#                 imu.accel.z,
#                 imu.gyro.x,
#                 imu.gyro.y,
#                 imu.gyro.z,
#                 fuse.pitch,
#                 fuse.roll,
#             )
#             # send struct on the (invisible) wire
#             await swriter.awrite(buf)
#         except Exception as e:
#             # tolerate exception and keep on going (it's udp anyway)
#             log.error("tx", e)
#             return
#         await asyncio.sleep_ms(250)


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

    # tasks
    t1 = asyncio.create_task(blinken())
    t2 = asyncio.create_task(switches())
    t3 = asyncio.create_task(mixer())
    # # TODO: check
    # if(WifiManager.wlan().status() == 1010):
    #     t4 = asyncio.create_task(transmit())
    #t5 = asyncio.create_task(mem_manage())
    repl = asyncio.create_task(aiorepl.task())

    await asyncio.gather(t1, t2, t3, repl)


# tidy memory
gc.collect()
# and give info for reference
log.debug("gc", micropython.mem_info())

try:
    fuse = Fusion(read_coro)
    asyncio.run(main())
except KeyboardInterrupt:
    # humans
    log.warning("main", "interrupted")
finally:
    # loop
    _ = asyncio.new_event_loop()
