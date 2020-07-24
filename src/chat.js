class Chat {
    constructor() {
        this.baseUrl = '192.168.1.78'
        this.messageObjs = []
        this.webSocket = new WebSocket(`ws://${this.baseUrl ? this.baseUrl : window.location.hostname}/wschat`)
        this.webSocket.onopen = (event) => {
            this.onOpen(event)
        };
        this.webSocket.onclose = (event) => {
            this.onClose(event)
        };
        this.webSocket.onmessage = (event) => {
            this.onMessage(event)
        };
        this.webSocket.onerror = (event) => {
            this.onError(event)
        }
    }
    onOpen(event) {
        console.log(event)
        // Get all previous chat messages, order, and concatenate them
        // if(event.data && event.data.length) this.messageObjs = [...event.data.reverse(), ...this.messageObjs]
    }
    onClose(event) {
        console.log('[WS] CONNECTION CLOSED')
    }
    onError(error) {
        console.log('[WS] CONNECTION ERROR')
        console.log(error)
    }
    sendMessage(message, name) {
        this.webSocket.send(JSON.stringify({
            message,
            timestamp: new Date().getTime(),
            sender: name
        }))
    }
    onMessage(event) {
        console.log(event)
        try {
            const messageObj = JSON.parse(event.data)
            this.messageObjs = [messageObj, ...this.messageObjs]
            console.log(this.messageObjs)
        } catch (err) {
            console.log(err)
        }

    }
}
export default new Chat()
