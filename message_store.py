import btree, json


class MessageStore:
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
            print('[BTREE] OSError')
            self._file = open("messages.db", "w+b")
        self._db = btree.open(self._file)
        for messageStr in self._db.values():
            try:
                self.messages.append(json.loads(messageStr))
            except Exception as error:
                print('[Startup] error load messageObj from btree', error)

    # Add message to messages array and persistent data
    def add_message(self, message):
        try:
            if len(self.messages) >= self._max_message_length:  # Make sure local messageObj array size is constrained
                popped = self.messages.pop(0)  # Pop oldest message from messageObj
                del self._db[str(popped['timestamp']).encode()]  # Remove message from message db
                self._db.flush()
            self.messages.append(message)  # Add to local messageObj array
            self._db[str(message['timestamp']).encode()] = json.dumps(
                message)  # Add new message to db using [key: messageObj.timestamp, value: messageObj
            self._db.flush()
        except Exception as error:
            print('[addMessage] ', error)

    #  Return the timestamp from the newest message
    def latest_timestamp(self):
        return self.messages[len(self.messages) - 1]['timestamp']

    def get_index_from_timestamp(self, timestamp):
        for i, dic in enumerate(self.messages):
            if dic['timestamp'] == timestamp:
                return i
        return -1

    # Close everything we going home
    def close(self):
        self._db.close()
        self._file.close()
