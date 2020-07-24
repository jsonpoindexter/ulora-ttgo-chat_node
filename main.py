import machine, json, gc
from time import sleep
import config_lora
from machine import Pin, SPI
from sx127x import SX127x

MAX_MESSAGES_LENGTH = 30
messages = []

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

# WIFI Stuff
import network

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect('***REMOVED***', '***REMOVED***')
while wlan.isconnected() == False:
    pass

print('Connection successful')
print(wlan.ifconfig())


#  Helper to find message index
def find(lst, key, value):
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return i
    return -1


# WEB SERVER stuff
from MicroWebSrv2 import *


def WSJoinChat(webSocket):
    webSocket.OnTextMessage = OnWSChatTextMsg
    webSocket.OnClosed = OnWSChatClosed
    addr = webSocket.Request.UserAddress
    with _chatLock:
        _chatWebSockets.append(webSocket)
        print('[WS] WSJoinChat %s:%s connected' % addr)
        # webSocket.SendTextMessage(messages)

def OnWebSocketTextMsg(webSocket, message) :
    print('[WS] OnWebSocketTextMsg message: %s' % message)
    addMessage(json.loads(message))
    lora.println(message)
    webSocket.SendTextMessage(message)

def OnWebSocketBinaryMsg(webSocket, msg) :
    print('WebSocket binary message: %s' % msg)


def OnWSChatTextMsg(webSocket, message):
    print('[WS] OnWSChatTextMsg message: %s' % message)
    addMessage(json.loads(message))
    lora.println(message)
    with _chatLock:
        for ws in _chatWebSockets:
            ws.SendTextMessage(message)


def OnWSChatClosed(webSocket):
    addr = webSocket.Request.UserAddress
    print('[WS] OnWSChatClosed message:  %s:%s' % addr)
    with _chatLock:
        if webSocket in _chatWebSockets:
            _chatWebSockets.remove(webSocket)

def OnWebSocketClosed(webSocket):
    print('[WS] OnWebSocketClosed %s:%s closed' % webSocket.Request.UserAddress)

def OnWebSocketAccepted(microWebSrv2, webSocket):
    print('Example WebSocket accepted:')
    print('   - User   : %s:%s' % webSocket.Request.UserAddress)
    print('   - Path   : %s' % webSocket.Request.Path)
    print('   - Origin : %s' % webSocket.Request.Origin)
    if webSocket.Request.Path.lower() == '/wschat':
        WSJoinChat(webSocket)
    else:
        webSocket.OnTextMessage = OnWebSocketTextMsg
        webSocket.OnBinaryMessage = OnWebSocketBinaryMsg
        webSocket.OnClosed = OnWebSocketClosed

global _chatWebSockets
_chatWebSockets = []

global _chatLock
_chatLock = allocate_lock()


# Return Lora messages from an index
@WebRoute(GET, '/messages')
def RequestHandler(microWebSrv2, request):
    timestamp = request.QueryParams.get('timestamp')
    if timestamp is not None:
        timestamp = int(timestamp)
        # Find the index of the message where the message's { index: number } == start_index
        # https://stackoverflow.com/questions/4391697/find-the-index-of-a-dict-within-a-list-by-matching-the-dicts-value
        # message_index = next((index for (index, d) in enumerate(messages) if d["index"] == start_index), None)
        message_index = find(messages, "timestamp", timestamp)
        print(timestamp)
        print(messages)
        print('message_index: ', message_index)
        if message_index == -1:
            request.Response.ReturnJSON(200, [])
        else:
            request.Response.ReturnJSON(200, messages[(message_index + 1):])

    else:
        request.Response.ReturnJSON(200, messages)


# Send receive message over HTTP and sned out over Lora
@WebRoute(POST, '/message')
def RequestHandler(microWebSrv2, request):
    body = request.GetPostedJSONObject()
    print('body: ', body)
    lora.println(json.dumps(body))
    addMessage(body)
    request.Response.ReturnOk()


def addMessage(payload):
    print(messages)
    if len(messages) >= MAX_MESSAGES_LENGTH:
        messages.pop(0)
    messages.append({
        'timestamp': payload['timestamp'],
        'message': payload['message'],
        'sender': payload['sender']
    })


if __name__ == '__main__':
    # Loads the WebSockets module globally and configure it,
    wsMod = MicroWebSrv2.LoadModule('WebSockets')
    wsMod.OnWebSocketAccepted = OnWebSocketAccepted

    # Instantiates the MicroWebSrv2 class,
    mws2 = MicroWebSrv2()
    mws2.AllowAllOrigins = True  # TODO: remove after testing
    mws2.CORSAllowAll = True  # TODO: remove after testing

    # For embedded MicroPython, use a very light configuration,
    mws2.SetEmbeddedConfig()

    # All pages not found will be redirected to the home '/',
    # mws2.NotFoundURL = '/'

    # Starts the server as easily as possible in managed mode,
    mws2.StartManaged()
    # Main program loop until keyboard interrupt,
    try:
        while mws2.IsRunning:
            if lora.received_packet():
                lora.blink_led()
                payload = lora.read_payload()
                print('[LORA] received payload: ', payload)
                try:
                    payload = json.loads(payload)
                    addMessage(payload)
                except (Exception, TypeError) as error:
                    print("[LORA] Error parsing JSON payload: ", error)


    except KeyboardInterrupt:
        pass

    # End,
    mws2.Stop()
