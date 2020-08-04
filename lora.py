########## LORA ##########
from time import sleep
from machine import Pin, SPI, reset
from sx127x import SX127x

device_pins = {
    'miso': 19,
    'mosi': 27,
    'ss': 18,
    'sck': 5,
    'dio_0': 26,
    'reset': 16,
    'led': 2,
}

device_spi = SPI(baudrate=10000000,
                 polarity=0, phase=0, bits=8, firstbit=SPI.MSB,
                 sck=Pin(device_pins['sck'], Pin.OUT, Pin.PULL_DOWN),
                 mosi=Pin(device_pins['mosi'], Pin.OUT, Pin.PULL_UP),
                 miso=Pin(device_pins['miso'], Pin.IN, Pin.PULL_UP))

parameters = {
    'frequency': 868E6,
    'tx_power_level': 2,
    'signal_bandwidth': 125E3,
    'spreading_factor': 8,
    'coding_rate': 5,
    'preamble_length': 8,
    'implicit_header': False,
    'sync_word': 0x12,
    'enable_CRC': True,
    'invert_IQ': False,
}

# Restart machine if we get the 'invalid version' error
try:
    lora = SX127x(device_spi, pins=device_pins, parameters=parameters)
except:
    sleep(1)  # this try/except can get caught in an uninterruptible loop, sleep gives us a chance
    reset()

def onLoraRX():
    if lora.received_packet():
        lora.blink_led()
        payload = lora.read_payload()
        print('[LORA] RSSI: ', lora.packet_rssi())
        print('[LORA] received payload: ', payload)
        try:
            payload_obj = json.loads(payload)
            addMessage(payload_obj)
        except (Exception, TypeError) as error:
            print("[LORA] Error parsing JSON payload: ", error)
        # Send messageObj over BLE
        if BLE_ENABLED and ble_peripheral.is_connected():
            ble_peripheral.send(payload)
        # Send message to all web sockets
        if WEBSERVER_ENABLED:
            SendAllWSChatMsg(payload.decode("utf-8"))
