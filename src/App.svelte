<script>
    import {onMount} from 'svelte'
    // Value	State	Description
    // 0	CONNECTING	Socket has been created. The connection is not yet open.
    // 1	OPEN	The connection is open and ready to communicate.
    // 2	CLOSING	The connection is in the process of closing.
    // 3	CLOSED
    let webSocketState
    let baseUrl = '192.168.1.78' // base url used for dev
    let webSocket
    let messageObjs// current chat messages
    let message = window.localStorage.getItem('message') // current message to send
    let messageTimeout // used to debounce name input
    let sentMessageObjStr = '' // last message that was sent. used to verify that the message send back from the server is this message
    $: isSendDisabled = sentMessageObjStr.length > 0 || webSocketState !== 1
    let name = window.localStorage.getItem('name') // sender name
    let nameTimeout // used to debounce name input

    const openWebSocket = () => {
        webSocket = new WebSocket(`ws://${baseUrl ? baseUrl : window.location.hostname}/wschat`)
        webSocketState = webSocket.readyState
        webSocket.onopen = (event) => {
            messageObjs = []
            webSocketState = webSocket.readyState
            onOpen(event)
        };
        webSocket.onclose = (event) => {
            webSocketState = webSocket.readyState
            onClose(event)
        };
        webSocket.onmessage = (event) => {
            webSocketState = webSocket.readyState
            onMessage(event)
        };
        webSocket.onerror = (event) => {
            webSocketState = webSocket.readyState
            onError(event)
        }
        webSocket = webSocket
    }
    openWebSocket()
    const onOpen = (event)  => {
        console.log('[WS] OPENED')
    }
    const onClose = (event)  => {
        console.log('[WS] CONNECTION CLOSED')
    }
    const onError = (error)  => {
        console.log('[WS] CONNECTION ERROR')
        console.log(error)
    }
    const sendMessage = (message, name) => {
        sentMessageObjStr = JSON.stringify({
            message,
            timestamp: new Date().getTime(),
            sender: name
        })
        webSocket.send(sentMessageObjStr)
    }
    const onMessage = (event) => {
        if (event.data === sentMessageObjStr) {
            sentMessageObjStr = ''
            message = ''
            window.localStorage.setItem('message', '')
        }
        try {
            const data =  JSON.parse(event.data)
            // Handle if we are sent an array of previous message objs (on connection open)
            if (Array.isArray(data)) {
                messageObjs = data
            }
            else {
                messageObjs = [...messageObjs, data]
                // TODO: sort messages by timestamp, messageObjs are not ensured to be in order
                console.log(messageObjs)
            }

        } catch (err) {
            console.log(err)
        }

    }
    const formatTime = (timeStr) => {
        const date = new Date(timeStr)
        const [{value: hour}, , {value: minute}, , {value: second}] = dateTimeFormat.formatToParts(date)
        return `${hour}:${minute}:${second}`
    }
    const dateTimeFormat = new Intl.DateTimeFormat('en', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    })

    const saveName = (name) => {
        clearTimeout(nameTimeout)
        nameTimeout = setTimeout(() => {
            window.localStorage.setItem('name', name)
        }, 500)
    }
    const saveMessage= (message) => {
        clearTimeout(messageTimeout)
        nameTimeout = setTimeout(() => {
            window.localStorage.setItem('message', message)
        }, 500)
    }


</script>

<main>
    <h1>Lora Chat</h1>
    <div class="chat-container">
        {#if webSocketState === 0 }
            <p>Connecting...</p>
        {:else if webSocketState === 1}
            {#each messageObjs as messageObj}
                <div class="chat-message-container">[{formatTime(messageObj.timestamp)}] &lt;{messageObj.sender}&gt; {messageObj.message}</div>
            {:else}
                <p>No Messages</p>
            {/each}
        {:else if webSocketState === 2}
            <p>Closing chat...</p>
        {:else}
            <p>Disconnected form chat server</p>
            <label><input type="button" value="Reconnect" on:click={openWebSocket()} /></label>
        {/if}
    </div>
    <div class="chat-send-container">
        <label><input type="text" placeholder="Name" bind:value={name} on:input={saveName(name)} /></label>
        <label><input type="text" placeholder="Send a message" bind:value={message} on:input={saveMessage(message)}/></label>
        <label><input type="submit" value="Send" on:click={sendMessage(message, name)} disabled="{isSendDisabled}"/></label>
    </div>
</main>

<style>
    :global(body) {
        overflow: hidden;
        margin: 0;
        width: 100%;
        padding: 0;
    }

    /*@media (min-width: 640px) {*/
    /*	main {*/
    /*		max-width: none;*/
    /*	}*/
    /*}*/

    main {
        text-align: center;
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
        /*padding: 1em;*/
        /*margin: 0 auto;*/
    }

    h1 {
        color: #ff3e00;
        text-transform: uppercase;
        font-size: 4em;
        font-weight: 100;
    }

    .chat-container {
        font-family: Menlo, Consolas, serif;
        border: 1px solid lightblue;
        padding: 10px;
        flex-grow: 1;
    }

    .chat-message-container {
        display: flex;
        flex-direction: row;

    }

    .chat-send-container {
        margin: 10px 0;
        display: flex;
        justify-content: center;
    }
</style>
