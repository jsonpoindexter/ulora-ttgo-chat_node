import machine
from time import sleep
import gc

import config_lora
from machine import Pin, SPI
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

# Restart machine if we get the 'invalid version' error
try:
    lora = SX127x(device_spi, pins=device_pins)
except:
    machine.reset()
gc.collect()

# WIFI Stuff
import network

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect('***REMOVED***', '***REMOVED***')
while wlan.isconnected() == False:
    pass

print('Connection successful')
print(wlan.ifconfig())
gc.collect()

#  Helper to find message index
def find(lst, key, value):
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return i
    return -1

# WEB SERVER stuff
from MicroWebSrv2 import *

# Return Lora messages from an index
@WebRoute(GET, '/messages')
def RequestHandler(microWebSrv2, request):
    start_index = request.QueryParams.get('start_index')
    if start_index is not None:
        start_index = int(start_index)
        print('start_index: ', start_index)
        # Find the index of the message where the message's { index: number } == start_index
        # https://stackoverflow.com/questions/4391697/find-the-index-of-a-dict-within-a-list-by-matching-the-dicts-value
        # message_index = next((index for (index, d) in enumerate(messages) if d["index"] == start_index), None)
        message_index = find(messages, "index", start_index)
        print('message_index: ', message_index)
        request.Response.ReturnJSON(200, messages[(message_index + 1):])
    else:
        request.Response.ReturnJSON(200, messages)


count = 0
MAX_MESSAGES_LENGTH = 30
messages = []

if __name__ == '__main__':
    # Instanciates the MicroWebSrv2 class, 
    mws2 = MicroWebSrv2()
    mws2.AllowAllOrigins = True  # TODO: remove after testing
    mws2.CORSAllowAll = True  # TODO: remove after testing

    # For embedded MicroPython, use a very light configuration,
    mws2.SetEmbeddedConfig()
    print(mws2.BufferSlotsCount)

    # All pages not found will be redirected to the home '/',
    # mws2.NotFoundURL = '/'

    # Starts the server as easily as possible in managed mode,
    mws2.StartManaged()
    print(gc.mem_free())
    gc.collect()
    print(gc.mem_free())
    # Main program loop until keyboard interrupt,
    try:
        while mws2.IsRunning:
            if lora.received_packet():
                lora.blink_led()
                count += 1
                payload = lora.read_payload()
                print('lora recieved[', count, ']: ', payload)
                if len(messages) >= MAX_MESSAGES_LENGTH: messages.pop(0)
                messages.append(
                    {
                        'index': count,
                        'time': '010101-202020',
                        'message': payload,
                        # 'message': payload.decode("utf-8"),
                        'sender': 'other'
                    }
                )
    except KeyboardInterrupt:
        pass

    # End,
    print()
    mws2.Stop()
    print('Bye')
    print()