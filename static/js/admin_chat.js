const socket = io();
let currentSelectedSession = null;

socket.on('connect', () => {
    console.log("🛠 Админ успешно подключен к WebSocket");
});

// 1. Получаем список всех активных чатов
socket.on('update_chat_list', (chats) => {
    console.log("Обновление списка чатов:", chats);
    const chatList = document.getElementById('chat-list');
    if (!chatList) return;
    
    chatList.innerHTML = '';

    const keys = Object.keys(chats);
    if (keys.length === 0) {
        chatList.innerHTML = '<p class="empty-text">Ожидание сообщений...</p>';
        return;
    }

    keys.forEach(id => {
        const item = document.createElement('div');
        item.className = `dialog-item ${id === currentSelectedSession ? 'active' : ''}`;
        
        // Показываем последнее сообщение в списке
        const lastMsgObj = chats[id].messages[chats[id].messages.length - 1];
        const lastMsgText = lastMsgObj ? lastMsgObj.text : 'Новый чат';

        item.innerHTML = `
            <strong>💬 ${id}</strong>
            <div style="font-size: 12px; color: #94a3b8; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
                ${lastMsgText}
            </div>
        `;
        item.onclick = () => selectChat(id);
        chatList.appendChild(item);
    });
});

// 2. Выбор чата при клике мышкой
function selectChat(sessionId) {
    currentSelectedSession = sessionId;
    
    const title = document.getElementById('active-chat-title');
    if (title) title.innerText = `Чат с клиентом: ${sessionId}`;
    
    document.getElementById('admin-input').disabled = false;
    document.getElementById('admin-send-btn').disabled = false;

    // Входим в WebSocket-комнату этого конкретного клиента
    socket.emit('join_admin_room', { session_id: sessionId });
}

// 3. Загрузка истории выбранного чата
socket.on('chat_history', (messages) => {
    const messagesDiv = document.getElementById('admin-chat-messages');
    if (!messagesDiv) return;
    
    messagesDiv.innerHTML = '';
    messages.forEach(msg => appendAdminMessage(msg));
});

// 4. Новое входящее сообщение от клиента в РЕАЛЬНОМ ВРЕМЕНИ
socket.on('new_message_for_admin', (data) => {
    console.log("Новое сообщение для админа:", data);
    // Если открыт именно этот чат — сразу рисуем сообщение
    if (data.session_id === currentSelectedSession) {
        appendAdminMessage(data.message);
    }
});

function appendAdminMessage(msg) {
    const messagesDiv = document.getElementById('admin-chat-messages');
    if (!messagesDiv) return;

    const msgEl = document.createElement('div');
    msgEl.className = `msg ${msg.sender}`;
    msgEl.innerText = msg.text;
    messagesDiv.appendChild(msgEl);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// 5. Отправка ответа админа
function sendAdminMessage() {
    const input = document.getElementById('admin-input');
    const text = input.value.trim();

    if (text && currentSelectedSession) {
        socket.emit('admin_message', {
            session_id: currentSelectedSession,
            text: text
        });
        
        // Отображаем сообщение у себя в окне
        appendAdminMessage({ sender: 'admin', text: text });
        input.value = '';
    }
}

function handleAdminKeyPress(e) {
    if (e.key === 'Enter') sendAdminMessage();
}