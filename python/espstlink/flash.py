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
    self.stlink.write(0x505B, 0x80)
    self.stlink.write(0x505C, 0x7F)

  def unlock_data(self):
    """unlocks the data area (eeprom, option bytes)"""
    self['FLASH_DUKR'].value = 0xAE
    self['FLASH_DUKR'].value = 0x56
    # assert self['FLASH_IAPSR']['DUL'], 'not unlocked'  # read unreliable

  def unlock_prog(self):
    """unlocks the main program area"""
    self['FLASH_PUKR'].value = 0x56
    self['FLASH_PUKR'].value = 0xAE
    # assert self['FLASH_IAPSR']['PUL'], 'not unlocked'  # read unreliable

  def lock(self):
    self['FLASH_IAPSR']['DUL'] = 0

  def wait_till_ready(self):
    while not self['FLASH_IAPSR']['EOP']: time.sleep(0.0001)
  
  def write(self, addr: int, block: bytes):
    assert (addr & 0x3f) == 0, "addr must be on a 64 byte boundary"
    assert len(block) == 64, "block must be exactly 64 bytes long"

    # Set PRG=1 in FLASH_CR2 and ~PRG in FLASH_NCR2 (direct write, no read-back)
    self.stlink.write_bytes(self['FLASH_CR2'].offset, bytes([0x01, 0xFE]))
    self.stlink.write_bytes(addr, block)

    # Fixed delay instead of EOP polling (SWIM reads are unreliable)
    time.sleep(0.045)
    return
