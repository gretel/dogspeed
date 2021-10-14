#!/usr/bin/env python

import socket
import struct
import time

from rich.console import Console
from rich.live import Live
from rich.table import Table

def generate_table(buf) -> Table:
    table = Table(title="DogSpeed Instrumentation")

    table.add_column("Accel X", style="yellow", width=10)
    table.add_column("Accel Y", style="yellow", width=10)
    table.add_column("Accel Z", style="yellow", width=10)
    table.add_column("Gyro X", style="cyan", width=10)
    table.add_column("Gyro Y", style="cyan", width=10)
    table.add_column("Gyro Z", style="cyan", width=10)
    table.add_column("Pitch", style="green", width=10, justify="right")
    table.add_column("Roll", style="blue", width=10, justify="right")

    table.add_row(f"{buf[7]}", f"{buf[8]}", f"{buf[9]}", f"{buf[10]}", f"{buf[11]}", f"{buf[12]}", f"{buf[13]}", f"{buf[14]}")
    return table

MCAST_GRP = '224.23.23.1'
MCAST_PORT = 2323

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((MCAST_GRP, MCAST_PORT))

mreq = struct.pack('4sl', socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

# # "header"
# buf = ustruct.pack("12sHI", MACHINE_UID, VERSION, utime.ticks_us())
# # "machine"
# buf += ustruct.pack(
#     "4f",
#     axp.read(axp192.BATTERY_VOLTAGE),
#     axp.read(axp192.DISCHARGE_CURRENT),
#     axp.read(axp192.CHARGE_CURRENT),
#     axp.read(axp192.TEMP),
# )
# # "payload"
# buf += ustruct.pack(
#     "8f",
#     imu.acceleration[0],
#     imu.acceleration[1],
#     imu.acceleration[2],
#     imu.gyro[0],
#     imu.gyro[1],
#     imu.gyro[2],
#     fuse.pitch,
#     fuse.roll,
# )

console = Console()

while True:
    r = sock.recv(10240)
    buf = struct.unpack('12sHI4f8f', r)
    #print(buf[8])

    with Live(generate_table(buf), refresh_per_second=10) as live:
        console.clear()
        live.update(generate_table(buf))
