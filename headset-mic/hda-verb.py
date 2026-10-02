#!/usr/bin/env python3
"""Прямые HDA-команды кодеку ALC256 через /dev/snd/hwC0D0 (нужен root).

Тот же механизм, которым пользуется драйвер (hwdep + ioctl). Никакого reconfig,
никакой пересборки и перезагрузки. Состояние живёт в RAM кодека: сброс — перезагрузка.

Использование:
  sudo ./hda-verb.py 0x19 0xf09                 # GET_PIN_SENSE
  sudo ./hda-verb.py 0x23 0x300 0x0200          # SET_AMP_GAIN_MUTE
  sudo ./hda-verb.py 0x20 0x500 0x45            # SET_COEF_INDEX = 0x45
  sudo ./hda-verb.py 0x20 0x400 0xd489          # SET_PROC_COEF = 0xd489

Основные verb'ы:
  0x300 SET_AMP_GAIN_MUTE    payload = (out<<15)|(index<<8)|(mute<<7)|gain
  0x500 SET_COEF_INDEX       0x400 SET_PROC_COEF      0xc00 GET_PROC_COEF
  0x707 SET_PIN_WIDGET_CONTROL  0x20=IN, vref: 0x21=50%, 0x24=80%, 0x25=100%
  0xf07 GET_PIN_WIDGET_CONTROL   0xf09 GET_PIN_SENSE   0xf1c GET_CONFIG_DEFAULT
"""
import fcntl
import os
import struct
import sys

HDA_IOCTL_VERB_WRITE = 0xC0084811  # _IOWR('H', 0x11, struct hda_verb_ioctl)
DEV = "/dev/snd/hwC0D0"


def send(nid, verb, param=0):
    value = (nid << 24) | (verb << 8) | param
    fd = os.open(DEV, os.O_RDWR)
    try:
        out = fcntl.ioctl(fd, HDA_IOCTL_VERB_WRITE, struct.pack("II", value, 0))
    finally:
        os.close(fd)
    return struct.unpack("II", out)[1]


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    if os.geteuid() != 0:
        print("Нужен root: sudo ./hda-verb.py ...")
        return 1
    nid, verb = int(argv[1], 0), int(argv[2], 0)
    param = int(argv[3], 0) if len(argv) > 3 else 0
    res = send(nid, verb, param)
    print(f"0x{nid:02x} verb 0x{verb:03x} param 0x{param:04x} -> 0x{res:08x}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
