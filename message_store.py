import btree, json


class MessageStore:

    # Note: interface message_obj: { timestamp: int, message: str, sender: str, ack: bool, is_sender: bool}
    def __init__(self, max_message_length):
        self._max_message_length = max_message_length  # Max amount of messages our messages array will hold
        self.messages = []  # Array of message objects:  { 'timestamp': number, 'sender': string, 'message': string }
        self._file = None
        self._db = None
        self._load_messages_from_db()

    # Load messages from persistent storage into messages array
    # TODO: handle MAX_MESSAGES_LENGTH change
    def _load_messages_from_db(self):
        try:
            self._file = open("messages.db", "r+b")
        except OSError:
            print('[BTREE] Creating new messages.db file...')
            self._file = open("messages.db", "w+b")
        self._db = btree.open(self._file)
        for messageStr in self._db.values():
            try:
                self.messages.append(json.loads(messageStr))
            except Exception as error:
                print('[Startup] error load message_obj from btree', error)

    # Add message to messages array and persistent data
    # is_sender [boolean]: if this is a message this node sent over Lora (True)
    # or a message received from a different node over Lora (True)
    def add_message(self, message_obj, is_sender=False):
        try:
            if not 'timestamp' or not 'sender' or not 'message' or \
                    not message_obj['timestamp'] or not message_obj['sender'] or not message_obj['message']:
                print(
                    '[message_store:add_message] message did not contain "timestamp" or not "sender" or not "message" '
                    'key or is blank value')
            message_obj['isSender'] = is_sender
            message_obj['ack'] = not is_sender
            print('[message_store:add_message] adding message ', message_obj)
            if len(self.messages) >= self._max_message_length:  # Make sure local message_obj array size is constrained
                popped = self.messages.pop(0)  # Pop oldest message from message_obj
                del self._db[str(popped['timestamp']).encode()]  # Remove message from message db
                self._db.flush()
            self.messages.append(message_obj)  # Add to local message_obj array
            self.add_message_to_db(message_obj)
        except Exception as error:
            print('[addMessage] Error: ', error)

    #  Return the newest sent or received message_obj
    #  is_sender [boolean]:
    #       (True) returns latest sent message
    #       (False) returns latest received message
    def latest_message(self, is_sender=False):
        if len(self.messages):
            messages = sorted(self.messages, key=lambda i: i['timestamp'])  # Sort by timestamp
            messages = [d for d in messages if d['isSender'] is is_sender]  # Filter on is_sender
            if len(messages):
                return messages[len(messages) - 1]
            else:
                return None
        else:  # If no messages
            return None

    # set message_obj['ack'] = true
    def set_message_ack(self, timestamp):
        index = self.get_index_from_timestamp(timestamp)
        if index >= 0:
            message_obj = self.messages[index]
            message_obj['ack'] = True
            self.add_message_to_db(message_obj)
        else:
            raise Exception("Unable to get index for message_obj timestamp: ", timestamp)

    # Add new message to db using [key: message_obj.timestamp, value: message_obj]
    def add_message_to_db(self, message_obj):
        self._db[str(message_obj['timestamp']).encode()] = json.dumps(message_obj)
        self._db.flush()

    def get_index_from_timestamp(self, timestamp):
        for i, dic in enumerate(self.messages):
            if dic['timestamp'] == timestamp:
                return i
        return -1

    # Close everything we going home
    def close(self):
        self._db.close()
        self._file.close()
