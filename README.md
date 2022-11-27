# DogSpeed

:snake: `micropython` code to read, fuse and transport data of a inertial measurement unit via a network socket to be processed further.

## Prototype

This is intended to control sound synthesis by physical entities moving through space in time, i.e. a dog playing in his self-induced soundscape. :dog: :computer: :notes:

# Hardware

 * [`Wemos D1 mini`](https://www.banggood.com/5pcs-D1-Mini-V3_0_0-WIFI-Internet-Of-Things-Development-Board-Based-ESP8266-4MB-p-1385321.html)
  * [`M5StickC PLUS`](https://docs.m5stack.com/#/en/core/m5stickc_plus)


## Flash

Due to the use of `uasyncio` version 3 `micropython` (not `pycopy` :tongue:) version `1.13` is required at least.

### `ESP8266`

 At the time of this writing the [`daily builds for 2M or more of flash`](https://micropython.org/download/esp8266/) have been working fine:

```shell
esptool.py --port /dev/cu.usbserial-14310 --baud 1000000 erase_flash
esptool.py --port /dev/cu.usbserial-14310 --baud 1000000 write_flash --flash_size=4MB -fm dio 0 esp8266-20201130-unstable-v1.13-194-gf7225d1c9.bin
```

### `M5StickC PLUS`

 [`GENERIC` builds](https://micropython.org/download/esp32/) should flash fine:

```shell
esptool.py -p /dev/cu.usbserial-29521504FD -b 115200 erase_flash
esptool.py -p /dev/cu.usbserial-29521504FD -b 115200 --before default_reset --after hard_reset write_flash --flash_mode dio --flash_size detect --flash_freq 40m 0x1000 esp32-20210813-unstable-v1.16-201-g671f01230

```

### `M5 Atom Lite`

[`GENERIC` builds](https://micropython.org/download/esp32/) as well:

```shell
esptool.py -p /dev/ttyUSB0 -b 115200 erase_flash
esptool.py --chip esp32 --port /dev/ttyUSB0 write_flash -z 0x1000 firmware.bin

```

## Format Flash

```python
import os
os.umount('/')
os.VfsLfs2.mkfs(bdev)
os.mount(bdev, '/')
```

## Copy

```shell
mpr -d /dev/cu.usbserial-1552E605F3 put main.py boot.py networks.json /
mpr -d /dev/tty.usbserial-1552E605F3 mkdir /lib
mpr -d /dev/tty.usbserial-1552E605F3 put lib/*.py /lib
```

## Sensor

...

## Miscellaneous 

...

# Code

is working fine but documentation is work in progress

## Components

 * https://github.com/peterhinch/micropython-async/tree/master/v3/
 * https://github.com/mitchins/micropython-wifimanager
 * https://github.com/tuupola/micropython-mpu9250
 * https://github.com/micropython-IMU/micropython-fusion
 * https://github.com/micropython/micropython-lib/blob/master/socket/socket.py

## Configuration

 * `networks.json` - wireless network client/server
 * `mag_cal.json` - calibration data for the magnetometer obtained previously
 * `stream.json` - socket connection (target host) to stream data to

## Calibration

Please follow this [instructions](https://github.com/tuupola/micropython-mpu9250#magnetometer-calibration) for now.

# Host

## Reception

For testing a __bsdish__ `netcat` should do:

```shell
$ nc -ukvvl 2323
{"g": [0.0194518, 0.059954, -0.010925], "m": [-14.0693, 23.7082, 23.8688], "a": [-4.65672, 0.0407014, 8.56884], "t": 180389812, "c": 29.5632, "f": {"r": 0.603636, "p": 29.1712, "y":-91.0807}}
```

## Processing

..

## Synthesis

..
