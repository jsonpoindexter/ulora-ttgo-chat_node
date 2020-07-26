import machine, json, btree
import LoRa
import WiFi

# Init LoRa first because it might require a restart
lora = LoRa.init()
WiFi.init()


MAX_MESSAGES_LENGTH = 30
messages = []
# Load store message objs from file in array
try:
    dbFile = open('db.btree', 'r+b')
except OSError:
    dbFile = open('db.tree', 'w+b')
db = btree.open(dbFile)
for value in db.values():
    print("value: ", value)
    messages.append(json.loads(value))
db.close()
print("messages: ", messages)

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
        if messages:
            webSocket.SendTextMessage(json.dumps(messages))

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


def addMessage(payload):
    if len(messages) >= MAX_MESSAGES_LENGTH:
        messages.pop(0)
    message = {
        'timestamp': payload['timestamp'],
        'message': payload['message'],
        'sender': payload['sender']
    }
    messages.append(message)
    # Write messages array to DB
    # TODO: maybe there is a less intense way to implement this
    db = btree.open(dbFile)
    for index in range(len(messages)):
        messages[index] = message
        db[bytes(index)] = json.dumps(message)
    db.flush()
    db.close()
    print("messages: ", messages)


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
    dbFile.close()
