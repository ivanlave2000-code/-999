const socket = io();

let sessionId = localStorage.getItem('client_session_id');
if (!sessionId) {
    sessionId = 'user_' + Math.random().toString(36).substring(2, 9);
    localStorage.setItem('client_session_id', sessionId);
}

socket.on('connect', () => {
    socket.emit('start_chat', { session_id: sessionId });
});
let isSending = false;

function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();

    // Если прямо сейчас идет отправка — игнорируем спам-клики
    if (isSending || !text) return;

    isSending = true;

    socket.emit('client_message', {
        session_id: sessionId,
        text: text
    });

    input.value = '';

    // Разблокируем отправку через 300 мс
    setTimeout(() => {
        isSending = false;
    }, 300);
}
function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();

    if (text) {
        socket.emit('client_message', {
            session_id: sessionId,
            text: text
        });
        input.value = '';
    }
}

function handleKeyPress(e) {
    if (e.key === 'Enter') sendMessage();
}

// Загрузка истории чата
socket.on('chat_history', (messages) => {
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.innerHTML = '';
    messages.forEach(msg => appendMessage(msg));
});

// Новое сообщение
socket.on('receive_message', (msg) => {
    appendMessage(msg);
});

function appendMessage(msg) {
    const messagesDiv = document.getElementById('chat-messages');
    const msgEl = document.createElement('div');
    msgEl.className = `msg ${msg.sender}`;
    msgEl.innerText = msg.text;
    messagesDiv.appendChild(msgEl);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}
