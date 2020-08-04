import machine, json, gc, time
import credentials

########## CONSTANTS ##########
IS_BEACON = True  # Used for testing range
BLE_ENABLED = True  # Used for testing
BLE_NAME = 'ulora2' if IS_BEACON else 'ulora'  # Name BLE will use when advertising

########## LORA ##########
from lora import *
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


########## BTREE ##########
import btree

# Storage of general persistent data
try:
    dbFile = open("db", "r+b")
except OSError:
    print('[BTREE] OSError')
    dbFile = open("db", "w+b")
db = btree.open(dbFile)

# Storage of message objects
try:
    messagesDbFile = open("messages.db", "r+b")
except OSError:
    print('[BTREE] OSError')
    messagesDbFile = open("messages.db", "w+b")
messagesDb = btree.open(messagesDbFile)


def byte_str_to_bool(string):
    if string == b'0':
        return False
    else:
        return True


########## WEB_SERVER_ENABLED ##########
try:
    WEBSERVER_ENABLED = byte_str_to_bool(db[b'WEBSERVER_ENABLED'])  # Used to enable/disable web server
    db.flush()
except KeyError:
    print('key error')
    db[b'WEBSERVER_ENABLED'] = b'0'  # btree wont let us use bool
    db.flush()
    WEBSERVER_ENABLED = False
button = Pin(0, Pin.IN, Pin.PULL_UP)  # onboard momentary push button, True when open / False when closed
prev_button_value = False

######### PRINT CONST ########
print("######### CONFIG VARIABLES ########")
print("IS_BEACON: ", IS_BEACON)
print("WEBSERVER_ENABLED: ", WEBSERVER_ENABLED)
print("BLE_ENABLED: ", BLE_ENABLED)
print("BLE_NAME: ", BLE_NAME)
print("######### CONFIG VARIABLES ########")

########## MESSAGES ##########
MAX_MESSAGES_LENGTH = 30
messages = []
for messageStr in messagesDb.values():
    try:
        messages.append(json.loads(messageStr))
    except Exception as error:
        print('[Startup] error load messageObj from btree', error)
print('Loaded Messages: ', messages)


def addMessage(payload):
    try:
        message = {
            'timestamp': payload['timestamp'],
            'message': payload['message'],
            'sender': payload['sender']
        }
        if len(messages) >= MAX_MESSAGES_LENGTH:  # Make sure local messageObj array size is constrained
            popped = messages.pop(0)  # Pop oldest message from messageObj
            del messagesDb[str(popped['timestamp']).encode()]  # Remove message from message db
            messagesDb.flush()
        messages.append(message)  # Add to local messageObj array
        messagesDb[str(message['timestamp']).encode()] = json.dumps(message)
        messagesDb.flush()
    except Exception as error:
        print('[addMessage] ', error)


#  Helper to find message index
def find(lst, key, value):
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return i
    return -1


########## BLE ##########
if BLE_ENABLED:
    from BLEPeripheral import *
    from ble_advertising import advertising_payload

    ble = bluetooth.BLE()
    ble_peripheral = BLESPeripheral(ble, BLE_NAME)


    def on_ble_rx(value):
        try:
            print("[BLE] Received Message: ", value)
            payload = str(value, 'utf-8')
            if payload == "ALL":  # Received request to TX all messages
                for message in messages:
                    print("[BLE] sending message: ", json.dumps(message))
                    ble_peripheral.send(json.dumps(message))
                    gc.collect()
                    print('[Memory - free: {}   allocated: {}]'.format(gc.mem_free(), gc.mem_alloc()))
            else:  # Received a normal message
                lora.println(payload)  # Send message over Lora
                addMessage(json.loads(payload))  # Add message to local array and storage
                # Send message to all web sockets
                if WEBSERVER_ENABLED:
                    SendAllWSChatMsg(payload)
        except Exception as error:
            print('[on_ble_rx] ', error)


    ble_peripheral.on_write(on_ble_rx)


# Toggle WEBSERVER_ENABLE and restart on button push
# TODO: toggle WIFI without restart
# TODO: implement press/hold
def on_button_push():
    global prev_button_value
    button_value = button.value()
    if button_value != prev_button_value:
        prev_button_value = button_value
        if not button_value:
            print('setting WEBSERVER_ENABLED: ', b'1' if not WEBSERVER_ENABLED else b'0')
            db[b'WEBSERVER_ENABLED'] = b'1' if not WEBSERVER_ENABLED else b'0'  # toggle value
            db.flush()
            db.close()  # close database
            dbFile.close()  # close database file
            messagesDb.close()
            messagesDbFile.close()
            if WEBSERVER_ENABLED:  # Stop web server if running
                mws2.Stop()
            machine.reset()  # restart


if WEBSERVER_ENABLED:
    # WIFI Setup
    import network


    def startAccessPoint():
        global WEBSERVER_ENABLED
        global wlan
        wlan = network.WLAN(network.AP_IF)
        wlan.active(True)
        wlan.config(essid=credentials.WIFI_AP['SSID'], password=credentials.WIFI_AP['PASSWORD'],
                    authmode=network.AUTH_WPA_WPA2_PSK)
        # TODO: check if there is a better way than time out
        total_time = 5000  # Give wifi 5 seconds to start AP
        start_time = time.ticks_ms()
        while not wlan.active() and (time.ticks_ms() - start_time) < total_time:
            pass


    # Try to connect to WiFi if Station SSID is specified
    if credentials.WIFI_STA['SSID']:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(credentials.WIFI_STA['SSID'], credentials.WIFI_STA['PASSWORD'])
        total_time = 5000  # Give wifi 5 seconds to connect
        start_time = time.ticks_ms()
        while wlan.status() != network.STAT_GOT_IP and (time.ticks_ms() - start_time) < total_time:
            pass
        # Start ip an Access Point
        if not wlan.isconnected():
            wlan.active(False)
            startAccessPoint()
    else:
        startAccessPoint()

    # If we cant host an AP or connect to WIFI then no need for web server
    if not wlan.active() and not wlan.isconnected():
        print('wifi error: ', wlan.active(), wlan.isconnected())
        WEBSERVER_ENABLED = False
        db[b'WEBSERVER_ENABLED'] = b'0'
        db.flush()
    else:
        print('[WLAN] Connection successful')
        print(wlan.ifconfig())

        from MicroWebSrv2 import *

        global _chatWebSockets
        _chatWebSockets = []

        global _chatLock
        _chatLock = allocate_lock()


        def WSJoinChat(webSocket):
            webSocket.OnTextMessage = OnWSChatTextMsg
            webSocket.OnClosed = OnWSChatClosed
            addr = webSocket.Request.UserAddress
            with _chatLock:
                _chatWebSockets.append(webSocket)
                print('[WS] WSJoinChat %s:%s connected' % addr)
                if messages:
                    webSocket.SendTextMessage(json.dumps(messages))


        def OnWebSocketTextMsg(webSocket, message):
            print('[WS] OnWebSocketTextMsg message: %s' % message)
            # addMessage(json.loads(message)) NOTE: are these needed, when does this fire?
            # lora.println(message)
            webSocket.SendTextMessage(message)


        def OnWebSocketBinaryMsg(webSocket, msg):
            print('WebSocket binary message: %s' % msg)


        def OnWSChatTextMsg(webSocket, message):
            print('[WS] OnWSChatTextMsg message: %s' % message)
            lora.println(message)  # Send message over Lora
            addMessage(json.loads(message))  # Add message to local array and storage
            if BLE_ENABLED and ble_peripheral.is_connected():
                ble_peripheral.send(message)  # Send message over BLE
            SendAllWSChatMsg(message)


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


        # Send chat message to all WS clients
        def SendAllWSChatMsg(message):
            with _chatLock:
                for ws in _chatWebSockets:
                    ws.SendTextMessage(message)

gc.collect()
print('[Memory - free: {}   allocated: {}]'.format(gc.mem_free(), gc.mem_alloc()))

messageCount = 0
if __name__ == '__main__':
    if WEBSERVER_ENABLED:
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
        while True:
            if IS_BEACON:
                messageCount += 1
                messageObj = {
                    "timestamp": time.ticks_ms(),
                    "message": 'Message #' + str(messageCount),
                    "sender": "BEACON"
                }
                print('[LORA] send payload: ', messageObj)
                print('[LORA] RSSI: ', lora.packet_rssi())

                lora.println(json.dumps(messageObj))
                sleep(5)
            else:
                onLoraRX()
            on_button_push()


    except KeyboardInterrupt:
        pass

    # End,
    mws2.Stop()
    messagesDbFile.close()
    messagesDb.close()
    db.close()
    dbFile.close()
