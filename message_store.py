import btree, json


class MessageStore:
    def __init__(self, max_message_length):
        self.__max_message_length = max_message_length  # Max amount of messages our messages array will hold
        self.messages = []  # Array of message objects:  { 'timestamp': number, 'sender': string, 'message': string }
        self.__file = None
        self.__db = None
        self.__load_messages_from_db()

    # Load messages from persistent storage into messages array
    # TODO: handle MAX_MESSAGES_LENGTH change
    def __load_messages_from_db(self):
        try:
            self.__file = open("messages.db", "r+b")
        except OSError:
            print('[BTREE] OSError')
            self.__file = open("messages.db", "w+b")
        self.__db = btree.open(self.__file)
        for messageStr in self.__db.values():
            try:
                self.messages.append(json.loads(messageStr))
            except Exception as error:
                print('[Startup] error load messageObj from btree', error)

    # Add message to messages array and persistent data
    def add_message(self, message):
        try:
            if len(self.messages) >= self.__max_message_length:  # Make sure local messageObj array size is constrained
                popped = self.messages.pop(0)  # Pop oldest message from messageObj
                del self.__db[str(popped['timestamp']).encode()]  # Remove message from message db
                self.__db.flush()
            self.messages.append(message)  # Add to local messageObj array
            self.__db[str(message['timestamp']).encode()] = json.dumps(
                message)  # Add new message to db using [key: messageObj.timestamp, value: messageObj
            self.__db.flush()
        except Exception as error:
            print('[addMessage] ', error)

    # Close everything we going home
    def close(self):
        self.__db.close()
        self.__file.close()
