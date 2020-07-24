<script>
    import {onMount} from 'svelte'
    let baseUrl = '192.168.1.78'
    let messageObjs = []
    let message = ''
    let name = ''
    const webSocket = new WebSocket(`ws://${baseUrl ? baseUrl : window.location.hostname}/wschat`)
    const onOpen = (event)  => {
        console.log(event)
        // Get all previous chat messages, order, and concatenate them
        // if(event.data && event.data.length) messageObjs = [...event.data.reverse(), ...messageObjs]
    }
    const onClose = (event)  => {
        console.log('[WS] CONNECTION CLOSED')
    }
    const onError = (error)  => {
        console.log('[WS] CONNECTION ERROR')
        console.log(error)
    }
    const sendMessage = (message, name) => {
        webSocket.send(JSON.stringify({
            message,
            timestamp: new Date().getTime(),
            sender: name
        }))
    }
    const onMessage = (event) => {
        console.log(event)
        try {
            const messageObj = JSON.parse(event.data)
            messageObjs = [messageObj, ...messageObjs]
            console.log(messageObjs)
        } catch (err) {
            console.log(err)
        }

    }
    onMount(async () => {
        webSocket.onopen = (event) => {
            onOpen(event)
        };
        webSocket.onclose = (event) => {
            onClose(event)
        };
        webSocket.onmessage = (event) => {
            onMessage(event)
        };
        webSocket.onerror = (event) => {
            onError(event)
        }
    });

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

</script>

<main>
    <h1>Lora Chat</h1>
    <div class="chat-container">
        {#each messageObjs as messageObj}
            <div class="chat-message-container">[{formatTime(messageObj.timestamp)}]&lt;{messageObj.sender}&gt;{messageObj.message}</div>
        {:else}
        <!-- this block renders when messages.length === 0 -->
            <p>loading...</p>
        {/each}
    </div>
    <div class="chat-send-container">
        <label><input type="text" placeholder="Name" bind:value={name}/></label>
        <label><input type="text" placeholder="Send a message" bind:value={message}/></label>
        <label><input type="submit" value="Send" on:click={sendMessage(message, name)}/></label>
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
