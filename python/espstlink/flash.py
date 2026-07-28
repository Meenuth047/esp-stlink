from . import register
import time

class FlashRegister(register.Register):
  def __init__(self, flash, *args, **kwargs):
    self.flash = flash
    super().__init__(*args, **kwargs)

  def __setitem__(self, name, value):
    super().__setitem__(name, value)
    self.flash.wait_till_ready()

class Options(register.Collection):
  def __init__(self, stlink):
    self.stlink = stlink
    self.flash = Flash(stlink)
    self.add_register( 'ROP', 0x4800)
    self.add_register( 'UBC', 0x4801)
    self.add_register('NUBC', 0x4802)
    self.add_register( 'OPT4', 0x4807, {'EXTCLK': 3})
    self.add_register('NOPT4', 0x4808, {'EXTCLK': 3})

  def add_register(self, name, offset, bits={}):
    self[name] = FlashRegister(self.flash, self.stlink, name, offset, bits)

  def enable_rop(self, enable=True):
    self['ROP'].value = 0xAA if enable else 0

  def unlock(self):
    self.flash.unlock_option_bytes()
    self.flash.unlock_data()
    self.flash.unlock_prog()

class Flash(register.Collection):
  def __init__(self, stlink):
    self.stlink = stlink
    self.add_register('FLASH_PUKR', 0x5062)
    self.add_register('FLASH_DUKR', 0x5064)
    self.add_register('FLASH_FPR', 0x505D)
    self.add_register('FLASH_NFPR', 0x505D)
    self.add_register('FLASH_IAPSR', 0x505F, {'HVOFF': 6, 'DUL': 3, 'EOP': 2, 'PUL': 1, 'WR_PG_DIS': 0})
    self.add_register('FLASH_CR1', 0x505A)
    self.add_register('FLASH_CR2', 0x505B, {'OPT': 7, 'PRG': 0})
    self.add_register('FLASH_NCR2', 0x505C, {'OPT': 7, 'PRG': 0})

  def unlock_option_bytes(self):
    self['FLASH_CR2']['OPT'] = 1
    self['FLASH_NCR2']['OPT'] = 0

  def unlock_data(self):
    """unlocks the data area (eeprom, option bytes)"""
    self['FLASH_DUKR'].value = 0xAE
    self['FLASH_DUKR'].value = 0x56
    assert self['FLASH_IAPSR']['DUL'], 'not unlocked'

  def unlock_prog(self):
    """unlocks the main program area"""
    self['FLASH_PUKR'].value = 0x56
    self['FLASH_PUKR'].value = 0xAE
    assert self['FLASH_IAPSR']['PUL'], 'not unlocked'

  def lock(self):
    self['FLASH_IAPSR']['DUL'] = 0

  def wait_till_ready(self):
    while not self['FLASH_IAPSR']['EOP']: time.sleep(0.0001)
  
  def write(self, addr: int, block: bytes):
    assert (addr & 0x3f) == 0, "addr must be on a 64 byte boundary"
    assert len(block) == 64, "block must be exactly 64 bytes long"
    
    # we do this manually for speed
    vals = self.stlink.read_bytes(self['FLASH_CR2'].offset, 2)
    assert (vals[0] & 1) == 0, "FLASH_CR2.PRG bit is still set"
    assert (vals[1] & 1) == 1, "FLASH_NCR2.PRG bit is still unset"
    vals[0] |= 1
    vals[1] -= 1
    self.stlink.write_bytes(self['FLASH_CR2'].offset, vals)
    self.stlink.write_bytes(addr, block)
    # SWIM is inaccessible while the flash controller holds the bus.
    # Programming time depends on CPU clock:
    #   ~6ms  at 16 MHz (firmware-configured)
    #   ~48ms at  2 MHz (STM8 reset-default: CLK_CKDIVR = 0x18 = /8)
    # Poll FLASH_IAPSR.EOP every 5ms; SWIM errors during the window are
    # treated as "still programming" and retried.
    deadline = time.monotonic() + 0.120  # 120ms hard ceiling
    while time.monotonic() < deadline:
      time.sleep(0.005)
      try:
        iapsr = self.stlink.read_bytes(self['FLASH_IAPSR'].offset, 1)[0]
      except Exception:
        continue  # SWIM busy during flash programming window
      if iapsr & 0x04:  # EOP bit set → programming complete
        if iapsr & 0x01:  # WR_PG_DIS → page is write-protected
          raise RuntimeError('Flash @%04x write-protected.' % addr)
        return
    raise RuntimeError('Flash @%04x timed out (EOP never set).' % addr)
