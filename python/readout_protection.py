#!/usr/bin/env python3
# Turns readout protection on / off

import time
import espstlink
from espstlink.flash import Options

class ReadoutProtection(object):
    def __init__(self, dev=None):
        dev = dev or espstlink.STLink()
        dev.init(reset=False)
        self.dev = dev
        self.options = Options(dev)

    def set(self, enable):
        self.options.unlock()
        self.options.enable_rop(enable)
        print('ROP', self.options['ROP'].status())
        self.dev.reset(1)
        time.sleep(0.001)
        self.dev.reset(0, input=True)
        print('ROP', self.options['ROP'].status())

if __name__ == '__main__':
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--device", default='/dev/ttyUSB1',
                        help="The serial device the HC is connected to")
    def str2bool(v):
        if isinstance(v, bool):
            return v
        if v.lower() in ('yes', 'true', 't', 'y', '1', 'on'):
            return True
        elif v.lower() in ('no', 'false', 'f', 'n', '0', 'off'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')

    parser.add_argument("enable_rop", type=str2bool,
                        help="Whether to enable ROP or not (true/false/on/off)", nargs='?')
    args = parser.parse_args()

    r = ReadoutProtection(espstlink.STLink(args.device.encode()))
    print('ROP status before:', r.options['ROP'].status())
    if args.enable_rop is not None:
      r.set(args.enable_rop)
