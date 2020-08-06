from MicroWebSrv2 import *
import json


def start():
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

    def OnWSChatTextMsg(webSocket, message):
        print('[WS] OnWSChatTextMsg message: %s' % message)
        lora.println(message)  # Send message over Lora
        message_store.add_message(json.loads(message))  # Add message to local array and storage
        if BLE_ENABLED and ble_peripheral.is_connected():
            ble_peripheral.send(message)  # Send message over BLE
        SendAllWSChatMsg(message)

    def OnWebSocketTextMsg(webSocket, message):
        print('[WS] OnWebSocketTextMsg message: %s' % message)
        # message_store.add_message(json.loads(message)) NOTE: are these needed, when does this fire?
        # lora.println(message)
        webSocket.SendTextMessage(message)

    def OnWebSocketBinaryMsg(webSocket, msg):
        print('WebSocket binary message: %s' % msg)


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
