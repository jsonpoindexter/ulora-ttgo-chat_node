<script>
	import { onMount } from 'svelte';
	const date = new Date();
	let message = "" // Outgoing message
	let name = "" // Name of sender
	let messageObjs = [
		// TODO: move this over to a testmessage.json or something...
		// {
		// 	index: 0,
		// 	time: `${date.getMonth() + 1}-${date.getDate()}-${date.getFullYear().toString().substr(-2)} ${date.getHours()}:${date.getMinutes()}:${date.getSeconds()}`,
		// 	sender: 'Jason',
		// 	message: "Something is here"
		// },
		// {
		// 	index: 1,
		// 	time: `${date.getMonth() + 1}-${date.getDate()}-${date.getFullYear().toString().substr(-2)} ${date.getHours()}:${date.getMinutes()}:${date.getSeconds()}`,
		// 	sender: 'Jason',
		// 	message: "Something is here"
		// },
		// {
		// 	index: 2,
		// 	time: `${date.getMonth() + 1}-${date.getDate()}-${date.getFullYear().toString().substr(-2)} ${date.getHours()}:${date.getMinutes()}:${date.getSeconds()}`,
		// 	sender: 'Jason',
		// 	message: "Something is here"
		// }
	];
	const dateTimeFormat = new Intl.DateTimeFormat('en', { hour: '2-digit', minute: '2-digit', second: '2-digit',  hour12: false,})

	onMount(async() => {
		await fetchMessages();
		messagesTimeout();
	});

	const fetchMessages = async () => {
		const query = messageObjs.length ? `?timestamp=${messageObjs[0].timestamp}` : '';
		const res = await fetch('/messages' +  query);
		const fetchedMessageObjs = await res.json();
		messageObjs = [...fetchedMessageObjs.reverse(), ...messageObjs]
	};

	const sendMessage = async () => {
		const body  = JSON.stringify({
			message,
			timestamp: new Date().getTime(),
			sender: name
		})
		await fetch('/message', {
			method: "POST",
			body,
			headers: {
				'Content-Type': 'application/json'
			}
		})
	}

	const formatTime = (timeStr) => {
		const date = new Date(timeStr)
		const [{ value: hour },,{ value: minute },,{ value: second }] = dateTimeFormat.formatToParts(date)
		return `${hour}:${minute}:${second}`
	}

	const messagesTimeout = () => {
		setTimeout(async ()=>{
			await fetchMessages();
			messagesTimeout();
		}, 2000);
	};
</script>

<main>
	<h1>Lora Chat</h1>
	<div class="chat-container">
		{#each messageObjs as messageObj}
			<div class="chat-message-container">[{formatTime(messageObj.timestamp)}] &lt;{messageObj.sender}&gt; {messageObj.message}</div>
		{:else}
			<!-- this block renders when messages.length === 0 -->
			<p>loading...</p>
		{/each}
	</div>
	<div class="chat-send-container">
		<label><input type="text" placeholder="Name" bind:value={name}/></label>
		<label><input type="text" placeholder="Send a message" bind:value={message}/></label>
		<label><input type="submit" value="Send" on:click={sendMessage}/></label>
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
