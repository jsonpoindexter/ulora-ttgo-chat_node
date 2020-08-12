import machine, json, gc, time
from machine import Pin
import credentials
from message_store import MessageStore
from config_lora import get_nodename

########## CONSTANTS ##########
IS_BEACON = False  # Used for testing range
BLE_ENABLED = True  # Used for testing
BLE_NAME = 'ulora2' if IS_BEACON else 'ulora'  # Name BLE will use when advertising
# BLE_NAME = 'ulora2' if get_nodename() == "ESP_30aea4bfbe88" else "ulora"  # NOTE: USE ONLY FOR DEV
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
    global previous_sync_time
    if lora.received_packet():
        lora.blink_led()
        payload = lora.read_payload()
        print('[LORA] RSSI: ', lora.packet_rssi())
        print('[LORA] received payload: ', payload)
        try:
            payload_obj = json.loads(payload)
        except (Exception, TypeError) as error:
            print("[LORA] Error parsing JSON payload: ", error)
            return

        # Handle message types that are not user messages (ex SYN)
        if "type" in payload_obj:
            if payload_obj["type"] == "SYN":  # Handle sync packets
                previous_sync_time = time.ticks_ms() - SYNC_INTERVAL / 2 # Offset SYN packets by half the interval time NOTE: assumes only 2 node network
                timestamp = payload_obj['timestamp']
                message_obj = message_store.latest_message(is_sender=True)  # Get latest sent message
                if message_obj:
                    if timestamp < message_obj['timestamp']: # Reply to SYN with latest message they are missing
                        message_obj = {  # Do not send 'is_sender' property since its only used locally
                            'timestamp': message_obj['timestamp'],
                            'message': message_obj['message'],
                            'sender': message_obj['sender']
                        }
                        send_lora_message(message_obj)
                    elif timestamp == message_obj['timestamp'] and not message_obj['ack']:  # if we know that the last message was received but we havent acknolesged uit yet
                        try:
                            message_store.set_message_ack(timestamp)
                            if BLE_ENABLED and ble_peripheral.is_connected():
                                ble_peripheral.send(json.dumps({
                                    'type': 'ACK',
                                    'timestamp': timestamp
                                }))
                        except Exception as err:
                            print('[LORA] Error setting message ack: ', err)
        else:  # Handle user messages
            message_store.add_message(payload_obj)
            # Send message_obj over BLE
            if BLE_ENABLED and ble_peripheral.is_connected():
                payload_obj['isSender'] = False  # TODO: we shouldn't do this twice (also in message_store.add_message)
                payload_obj['ack'] = True
                payload_obj['type'] = 'MSG'
                ble_peripheral.send(json.dumps(payload_obj))
            # Send message to all web sockets
            if WEBSERVER_ENABLED:
                SendAllWSChatMsg(payload.decode("utf-8"))


previous_sync_time = 0


# Send a syn packet SYNC_INTERVAL after last message was sent
def sync_interval():
    global previous_sync_time
    current_millis = time.ticks_ms()
    if current_millis - previous_sync_time > SYNC_INTERVAL:
        send_lora_sync()
        previous_sync_time = time.ticks_ms()


# TODO: use enum for Type?
# Send sync packet with the timestamp of the latest received message_obj
def send_lora_sync():
    latest_message = message_store.latest_message(is_sender=False)
    message_obj = {
        'type': 'SYN',
        'timestamp': latest_message['timestamp'] if latest_message else 0
    }
    send_lora_message(message_obj)


# Send a message obj over lora and reset sync time
# so we only send syn packets SYNC_INTERVAL time after last sent message
# NOTE: accepts stringify-d dict or dict
def send_lora_message(message):
    if type(message) is dict:
        print('[LORA] sending payload: ', message)
        lora.println(json.dumps(message))
    elif type(message) is str:
        print('[LORA] sending payload: ', message)
        lora.println(message)
    else:
        print('[ERROR] send_lora_message(message): message must be type dict or str')


messageCount = 0


def lora_beacon():
    global messageCount
    messageCount += 1
    message_obj = {
        "timestamp": time.ticks_ms(),
        "message": 'Message #' + str(messageCount),
        "sender": "BEACON"
    }
    print('[LORA] send payload: ', message_obj)
    print('[LORA] RSSI: ', lora.packet_rssi())
    send_lora_message(json.dumps(message_obj))
    message_store.add_message(message_obj, True)
    time.sleep(5)


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


try:
    WEBSERVER_ENABLED = byte_str_to_bool(db[b'WEBSERVER_ENABLED'])  # Used to enable/disable web server
    db.flush()
except KeyError:
    print('key error')
    db[b'WEBSERVER_ENABLED'] = b'0'  # btree wont let us use bool
    db.flush()
    WEBSERVER_ENABLED = False
WEBSERVER_ENABLED = False  # NOTE: override until BLE/Wifi clash is fixed

button = Pin(0, Pin.IN, Pin.PULL_UP)  # onboard momentary push button, True when open / False when closed
prev_button_value = False

######### PRINT CONST ########
print("######### CONFIG VARIABLES ########")
print('NODE_NAME: ', get_nodename())
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
                for message_obj in message_store.messages:
                    message_obj['type'] = 'MSG'
                    print("[BLE] sending message: ", json.dumps(message_obj))
                    ble_peripheral.send(json.dumps(message_obj))
                    gc.collect()
                    print('[Memory - free: {}   allocated: {}]'.format(gc.mem_free(), gc.mem_alloc()))
            else:  # Received a normal message
                message_obj = json.loads(payload)
                message_obj = {  # Do not send 'is_sender', or 'ack' property since its only used locally
                    'timestamp': message_obj['timestamp'],
                    'message': message_obj['message'],
                    'sender': message_obj['sender']
                }
                send_lora_message(message_obj)  # Send message over Lora
                message_store.add_message(json.loads(payload), True)  # Add message to local array and storage
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
            # message_store.add_message(json.loads(message), True) NOTE: are these needed, when does this fire?
            # send_lora_message(message)
            webSocket.SendTextMessage(message)


        def OnWebSocketBinaryMsg(webSocket, msg):
            print('WebSocket binary message: %s' % msg)


        def OnWSChatTextMsg(webSocket, message):
            print('[WS] OnWSChatTextMsg message: %s' % message)
            send_lora_message(message)  # Send message over Lora
            message_store.add_message(json.loads(message), True)  # Add message to local array and storage
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
                on_lora_rx()  # Handle receiving lora messages
                sync_interval()  # Send sync packet every X seconds after last message sent
            on_button_push()


    except KeyboardInterrupt:
        pass

    # End,
    mws2.Stop()
    message_store.close()
    db.close()
    dbFile.close()
