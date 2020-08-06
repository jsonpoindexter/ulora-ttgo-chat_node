import machine, json, gc, time
from machine import Pin
import credentials
from message_store import MessageStore

########## CONSTANTS ##########
IS_BEACON = True  # Used for testing range
BLE_ENABLED = True  # Used for testing
BLE_NAME = 'ulora2' if IS_BEACON else 'ulora'  # Name BLE will use when advertising
SYNC_INTERVAL = 5000  # How often (ms) to send sync packet after last packet was sent

########## LORA ##########
from config_lora import parameters, device_spi, device_pins
from sx127x import SX127x

# Restart machine if we get the 'invalid version' error
try:
    lora = SX127x(device_spi, pins=device_pins, parameters=parameters)
except:
    time.sleep(1)  # this try/except can get caught in an uninterruptible loop, sleep gives us a chance
    machine.reset()


def on_lora_rx():
    if lora.received_packet():
        lora.blink_led()
        payload = lora.read_payload()
        print('[LORA] RSSI: ', lora.packet_rssi())
        print('[LORA] received payload: ', payload)
        try:
            payload_obj = json.loads(payload)
            message_store.add_message(payload_obj)
        except (Exception, TypeError) as error:
            print("[LORA] Error parsing JSON payload: ", error)
        # Send messageObj over BLE
        if BLE_ENABLED and ble_peripheral.is_connected():
            ble_peripheral.send(payload)
        # Send message to all web sockets
        if WEBSERVER_ENABLED:
            SendAllWSChatMsg(payload.decode("utf-8"))


previous_sync_time = 0


# Send a syn packet SYNC_INTERVAL after last message was sent
def sync_interval():
    current_millis = time.ticks_ms()
    if current_millis - previous_sync_time > SYNC_INTERVAL:
        send_lora_sync()


# Send sync packet with the timestamp of the newest messageObj
def send_lora_sync():
    messageObj = {
        'type': 'SYNC',
        'timestamp': message_store.messages[len(message_store.messages) - 1]
    }
    send_lora_message(messageObj)


# Send a message obj over lora and reset sync time
# so we only send syn packets SYNC_INTERVAL time after last sent message
# NOTE: accepts stringify-d dict or dict
def send_lora_message(message):
    global previous_sync_time
    if type(message) is dict:
        lora.println(json.dumps(message))
        previous_sync_time = time.ticks_ms()
    elif type(message) is str:
        lora.println(message)
        previous_sync_time = time.ticks_ms()
    else:
        print('[ERROR] send_lora_message(message): message must be type dict or str')

messageCount = 0
def lora_beacon():
    global messageCount
    messageCount += 1
    messageObj = {
        "timestamp": time.ticks_ms(),
        "message": 'Message #' + str(messageCount),
        "sender": "BEACON"
    }
    print('[LORA] send payload: ', messageObj)
    print('[LORA] RSSI: ', lora.packet_rssi())

    send_lora_message(json.dumps(messageObj))
    sleep(5)


########## DATABASE ##########
import btree

# Storage of general persistent data
try:
    dbFile = open("db", "r+b")
except OSError:
    print('[BTREE] OSError')
    dbFile = open("db", "w+b")
db = btree.open(dbFile)


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
MAX_MESSAGES_LENGTH = 30  # Max amount of messages we will retain before removing old ones
message_store = MessageStore(MAX_MESSAGES_LENGTH)
print('Current Messages: ', message_store.messages)

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
                for message in message_store.messages:
                    print("[BLE] sending message: ", json.dumps(message))
                    ble_peripheral.send(json.dumps(message))
                    gc.collect()
                    print('[Memory - free: {}   allocated: {}]'.format(gc.mem_free(), gc.mem_alloc()))
            else:  # Received a normal message
                send_lora_message()
                send_lora_message(payload)  # Send message over Lora
                message_store.add_message(json.loads(payload))  # Add message to local array and storage
                # Send message to all web sockets
                if WEBSERVER_ENABLED:
                    SendAllWSChatMsg(payload)
        except Exception as error:
            print('[on_ble_rx] ', error)


    ble_peripheral.on_write(on_ble_rx)


# Toggle WEBSERVER_ENABLE and restart on button push
# TODO: toggle WIFI without restart
# TODO: implement press/hold and interupt
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
            message_store.close()
            if WEBSERVER_ENABLED:  # Stop web server if running
                mws2.Stop()
            machine.reset()  # restart


if WEBSERVER_ENABLED:
    from wlan import WLAN

    wlan = WLAN()

    # If we cant host an AP or connect to WIFI then no need for web server
    if wlan.isNotReady():
        print('[WIFI] error: active: ', wlan.interface.active(), ' isconnected" ', wlan.interface.isconnected())
        WEBSERVER_ENABLED = False
        db[b'WEBSERVER_ENABLED'] = b'0'
        db.flush()
    else:
        print('[WLAN] Connection successful')
        print(wlan.interface.ifconfig())

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
                if message_store.messages:
                    webSocket.SendTextMessage(json.dumps(message_store.messages))


        def OnWebSocketTextMsg(webSocket, message):
            print('[WS] OnWebSocketTextMsg message: %s' % message)
            # message_store.add_message(json.loads(message)) NOTE: are these needed, when does this fire?
            # send_lora_message(message)
            webSocket.SendTextMessage(message)


        def OnWebSocketBinaryMsg(webSocket, msg):
            print('WebSocket binary message: %s' % msg)


        def OnWSChatTextMsg(webSocket, message):
            print('[WS] OnWSChatTextMsg message: %s' % message)
            send_lora_message(message)  # Send message over Lora
            message_store.add_message(json.loads(message))  # Add message to local array and storage
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
                lora_beacon()
            else:
                on_lora_rx()
            on_button_push()


    except KeyboardInterrupt:
        pass

    # End,
    mws2.Stop()
    message_store.close()
    db.close()
    dbFile.close()
