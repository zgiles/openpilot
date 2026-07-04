#!/usr/bin/env python3
"""fork: decode car-info telemetry from CAN and publish it for logging + Connect.

Reads raw CAN, decodes the Toyota climate / drive-mode / EV signals we reverse-
engineered on the Prius Prime, and publishes them as `customReserved0` (CarInfo)
at ~2Hz. It's logged by loggerd and uploaded to Connect via the qlog. The addresses
are Toyota-specific; on other cars the frames simply never arrive and it publishes
defaults, so it's harmless to run everywhere.
"""
import cereal.messaging as messaging


def decode(frames: dict[int, bytes]) -> dict:
  s = {'acOn': False, 'acSetpoint': 0, 'acDefrost': False, 'cabinTempRaw': 0,
       'fanSpeed': 0, 'evMode': False, 'driveMode': 'NORMAL'}

  d = frames.get(0x382)                          # AIR_CONDITIONER
  if d and len(d) >= 8:
    s['acOn'] = bool(d[6] & 0x40)                # byte6 bit 0x40 = A/C on (confirmed)
    s['acSetpoint'] = d[6] & 0x3f                # low bits = temp setpoint (confirmed)
    s['cabinTempRaw'] = d[0]                     # TODO: calibrate to degF (~0x66 == 60F)

  d = frames.get(0x3b0)                          # AIR_CONDITIONER_2
  if d and len(d) >= 8:
    s['acDefrost'] = bool(d[5] & 0x08)           # WINDSCREEN_DEFOG (confirmed)

  d = frames.get(0x3b6)                          # EV status (unconfirmed decode)
  if d and len(d) >= 8:
    s['evMode'] = bool(d[5] & 0x02)

  d = frames.get(0x3bc)                          # GEAR_PACKET
  if d and len(d) >= 8:
    s['driveMode'] = 'SPORT' if (d[0] & 0x04) else ('ECO' if (d[5] & 0x01) else 'NORMAL')

  # TODO: fanSpeed — not yet located on the tapped bus
  return s


def main():
  sm = messaging.SubMaster(['can'])
  pm = messaging.PubMaster(['customReserved0'])
  frames: dict[int, bytes] = {}
  i = 0
  while True:
    sm.update()
    if sm.updated['can']:
      for c in sm['can']:
        if c.src == 0:                            # car/powertrain bus
          frames[c.address] = bytes(c.dat)

    i += 1
    if i % 50 == 0:                               # can is 100Hz -> publish ~2Hz
      s = decode(frames)
      msg = messaging.new_message('customReserved0')
      ci = msg.customReserved0
      ci.acOn = s['acOn']
      ci.acSetpoint = s['acSetpoint']
      ci.acDefrost = s['acDefrost']
      ci.cabinTempRaw = s['cabinTempRaw']
      ci.fanSpeed = s['fanSpeed']
      ci.evMode = s['evMode']
      ci.driveMode = s['driveMode']
      pm.send('customReserved0', msg)


if __name__ == "__main__":
  main()
