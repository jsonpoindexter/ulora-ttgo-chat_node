<script>
	import { onMount } from 'svelte';
	const date = new Date();
	let messageObjs = [
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

	onMount(async() => {
		await fetchMessages();
		messagesTimeout();
	});

	const fetchMessages = async () => {
		console.log(messageObjs);
		const query = messageObjs.length ? `?start_index=${messageObjs[0].index}` : '';
		const res = await fetch('http://192.168.1.78/messages' +  query);
		const fetchedMessageObjs = await res.json();
		messageObjs = [...fetchedMessageObjs.reverse(), ...messageObjs]
	};

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
			<div class="chat-message-container">[{messageObj.index}] &lt;{messageObj.sender}&gt; {messageObj.message}</div>
		{:else}
		<!-- this block renders when messages.length === 0 -->
			<p>loading...</p>
		{/each}
	</div>
</main>

<style>
	main {
		text-align: center;
		padding: 1em;
		margin: 0 auto;
	}

	h1 {
		color: #ff3e00;
		text-transform: uppercase;
		font-size: 4em;
		font-weight: 100;
	}

	@media (min-width: 640px) {
		main {
			max-width: none;
		}
	}
	.chat-container {
		margin: 10px;
		border: 1px solid lightblue;
		padding: 10px;
	}
	.chat-message-container {
		display: flex;
		flex-direction: row;
	}
</style>
