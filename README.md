# DogSpeed

:snake: `micropython` code to read, fuse and transport data of a inertial measurement unit via a network socket to be processed further.

## Prototype

This is intended to control sound synthesis by physical entities moving through space in time, i.e. a dog playing in his self-induced soundscape. :dog: :computer: :notes:

# Hardware

 * `Wemos D1 mini` 

## Flash

Due to the use of `uasyncio` version 3 `micropython` (not `pycopy` :tongue:) version `1.13` is required at least. At the time of this writing the [`daily builds for 2M or more of flash`](https://micropython.org/download/esp8266/) have been working fine.

```
esptool.py --port /dev/cu.usbserial-14310 --baud 1000000 erase_flash
esptool.py --port /dev/cu.usbserial-14310 --baud 1000000 write_flash --flash_size=4MB -fm dio 0 esp8266-20201130-unstable-v1.13-194-gf7225d1c9.bin
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

...

## Usage

...

# Host

## Processing

..

## Synthesis

..
