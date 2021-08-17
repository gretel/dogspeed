#!/usr/bin/env python

import socket
import struct
import time

MCAST_GRP = '224.23.23.1'
MCAST_PORT = 2323

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((MCAST_GRP, MCAST_PORT))

mreq = struct.pack('4sl', socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

while True:
  r = sock.recv(10240)
  buf = struct.unpack('12sHI4f8f', r)
  print(buf)
  time.sleep(0.01)
