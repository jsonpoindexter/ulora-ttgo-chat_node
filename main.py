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
NODE_NAME = get_nodename()

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

        print('[LORA] received payload: ', payload)
        try:
            payload_obj = json.loads(payload)
        except (Exception, TypeError) as error:
            print("[LORA] Error parsing JSON payload: ", error)
            return

        # Handle message types that are not user messages (ex SYN)
        if "type" in payload_obj:
            if payload_obj["type"] == "SYN":  # Handle sync packets
                previous_sync_time = time.ticks_ms() - SYNC_INTERVAL / 2  # Offset SYN packets by half the interval time NOTE: assumes only 2 node network
                timestamp = payload_obj['timestamp']
                message_obj = message_store.latest_message(is_sender=True)  # Get latest sent message
                if message_obj:
                    if timestamp < message_obj['timestamp']:  # Reply to SYN with latest message they are missing
                        message_obj = {  # Do not send 'is_sender' property since its only used locally
                            'timestamp': message_obj['timestamp'],
                            'message': message_obj['message'],
                            'sender': message_obj['sender']
                        }
                        send_lora_message(message_obj)
                    elif timestamp == message_obj['timestamp'] and not message_obj[
                        'ack']:  # if we know that the last message was received but we haven't acknowledged uit yet
                        try:
                            message_store.set_message_ack(timestamp)
                            if BLE_ENABLED and ble_peripheral.is_connected():
                                ble_peripheral.send(json.dumps({
                                    'type': 'ACK',
                                    'timestamp': timestamp
                                }))
                        except Exception as err:
                            print('[LORA] Error setting message ack: ', err)
                    if BLE_ENABLED and ble_peripheral.is_connected():
                        ble_peripheral.send(json.dumps({
                            'type': 'SYN',
                            'address': NODE_NAME,
                            'rssi': lora.packet_rssi()
                        }))
        else:  # Handle user messages
            message_store.add_message(payload_obj)
            # Send message_obj over BLE
            if BLE_ENABLED and ble_peripheral.is_connected():
                payload_obj['isSender'] = False  # TODO: we shouldn't do this twice (also in message_store.add_message)
                payload_obj['ack'] = True
                payload_obj['type'] = 'MSG'
                ble_peripheral.send(json.dumps(payload_obj))


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
    print('[BTREE] Creating new db file...')
    dbFile = open("db", "w+b")
db = btree.open(dbFile)


def byte_str_to_bool(string):
    if string == b'0':
        return False
    else:
        return True


######### PRINT CONST ########
print("######### CONFIG VARIABLES ########")
print('NODE_NAME: ', get_nodename())
print("IS_BEACON: ", IS_BEACON)
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
                    print("[BLE] sending message: ", message_obj)
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
                message_obj = message_store.add_message(json.loads(payload), True)  # Add message to local array and storage
                print("[BLE] sending message: ", message_obj)
                ble_peripheral.send(json.dumps(message_obj))  # Send message to all BLE devices

        except Exception as error:
            print('[on_ble_rx] ', error)


    ble_peripheral.on_write(on_ble_rx)

gc.collect()
print('[Memory - free: {}   allocated: {}]'.format(gc.mem_free(), gc.mem_alloc()))

if __name__ == '__main__':
    try:
        while True:
            if IS_BEACON:
                lora_beacon()
            else:
                on_lora_rx()  # Handle receiving lora messages
                sync_interval()  # Send sync packet every X seconds after last message sent


    except KeyboardInterrupt:
        pass

    # End,
    message_store.close()
    db.close()
    dbFile.close()
