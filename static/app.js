// ============================================
// LIKABILITY SCORE - Streaming Chat Application
// ============================================

const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');

// Session ID for conversation tracking
const sessionId = 'session_' + Date.now();

// ============================================
// Initialize
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    checkApiStatus();
    messageInput.focus();
});

async function checkApiStatus() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        
        updateStatus('status-openai', config.openai);
        updateStatus('status-newsapi', config.newsapi);
        updateStatus('status-reddit', config.reddit);
        updateStatus('status-rss', config.rss);
    } catch (error) {
        console.error('Failed to check API status:', error);
    }
}

function updateStatus(elementId, isActive) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.toggle('active', isActive);
        element.classList.toggle('inactive', !isActive);
    }
}

// ============================================
// Streaming Message Handling
// ============================================

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;
    
    // Disable input while processing
    messageInput.disabled = true;
    sendBtn.disabled = true;
    
    // Add user message to chat
    addMessage(message, 'user');
    messageInput.value = '';
    
    // Create assistant message container for streaming
    const assistantMessage = createStreamingMessage();
    
    try {
        // Use fetch with streaming
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let buffer = '';
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            // Process complete SSE messages
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handleStreamEvent(data, assistantMessage);
                    } catch (e) {
                        console.error('Failed to parse SSE data:', e);
                    }
                }
            }
        }
        
    } catch (error) {
        console.error('Stream error:', error);
        updateStreamingMessage(assistantMessage, 'text', 'Sorry, something went wrong. Please try again.');
    }
    
    // Remove status indicator when done
    const statusEl = assistantMessage.querySelector('.stream-status');
    if (statusEl) statusEl.remove();
    
    // Re-enable input
    messageInput.disabled = false;
    sendBtn.disabled = false;
    messageInput.focus();
}

function sendQuickMessage(message) {
    messageInput.value = message;
    sendMessage();
}

// ============================================
// Streaming UI Components
// ============================================

function createStreamingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    
    messageDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="stream-status">
                <div class="loading">
                    <div class="loading-dot"></div>
                    <div class="loading-dot"></div>
                    <div class="loading-dot"></div>
                </div>
                <span class="status-text">Thinking...</span>
            </div>
            <div class="message-text stream-text"></div>
            <div class="score-cards"></div>
            <div class="rankings-container"></div>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    
    return messageDiv;
}

function handleStreamEvent(data, messageEl) {
    switch (data.type) {
        case 'status':
            updateStreamStatus(messageEl, data.message);
            break;
            
        case 'intent':
            // Show initial response
            if (data.response) {
                const textEl = messageEl.querySelector('.stream-text');
                textEl.innerHTML = `<p class="intent-response">${escapeHtml(data.response)}</p>`;
            }
            break;
            
        case 'text':
            appendStreamingText(messageEl, data.content);
            break;
            
        case 'score':
            addScoreCard(messageEl, data.politician);
            break;
            
        case 'rankings':
            addRankings(messageEl, data.data);
            break;
            
        case 'done':
            // Hide status when complete
            const statusEl = messageEl.querySelector('.stream-status');
            if (statusEl) {
                statusEl.style.display = 'none';
            }
            break;
    }
    
    scrollToBottom();
}

function updateStreamStatus(messageEl, status) {
    const statusText = messageEl.querySelector('.status-text');
    if (statusText) {
        statusText.textContent = status;
    }
}

function appendStreamingText(messageEl, content) {
    const textEl = messageEl.querySelector('.stream-text');
    
    // Find or create the streaming paragraph
    let streamPara = textEl.querySelector('.streaming-para');
    if (!streamPara) {
        streamPara = document.createElement('p');
        streamPara.className = 'streaming-para';
        textEl.appendChild(streamPara);
    }
    
    // Append content with cursor effect
    streamPara.innerHTML += escapeHtml(content);
    
    // Handle paragraph breaks
    if (content.includes('\n\n')) {
        streamPara.classList.remove('streaming-para');
        streamPara = document.createElement('p');
        streamPara.className = 'streaming-para';
        textEl.appendChild(streamPara);
    }
}

function addScoreCard(messageEl, politician) {
    const cardsContainer = messageEl.querySelector('.score-cards');
    
    const score = politician.score || 0;
    const breakdown = politician.breakdown || {};
    
    const card = document.createElement('div');
    card.className = 'score-card';
    card.innerHTML = `
        <div class="score-header">
            <span class="score-name">${escapeHtml(politician.name)}</span>
            <span class="score-value">${score.toFixed(1)}</span>
        </div>
        <div class="score-bar">
            <div class="score-bar-fill" style="width: 0%"></div>
        </div>
        <div class="score-breakdown">
            <div class="breakdown-item">
                <span>News</span>
                <span>${(breakdown.news || 50).toFixed(0)}</span>
            </div>
            <div class="breakdown-item">
                <span>Trending</span>
                <span>${(breakdown.rss || 50).toFixed(0)}</span>
            </div>
            <div class="breakdown-item">
                <span>Social</span>
                <span>${(breakdown.reddit || 50).toFixed(0)}</span>
            </div>
            <div class="breakdown-item">
                <span>Engagement</span>
                <span>${(breakdown.engagement || 50).toFixed(0)}</span>
            </div>
        </div>
        ${politician.cached ? '<p style="font-size: 11px; color: var(--text-muted); margin-top: 8px;">📦 Cached</p>' : ''}
    `;
    
    cardsContainer.appendChild(card);
    
    // Animate the score bar
    setTimeout(() => {
        const bar = card.querySelector('.score-bar-fill');
        bar.style.width = `${score}%`;
    }, 100);
}

function addRankings(messageEl, rankings) {
    const container = messageEl.querySelector('.rankings-container');
    
    let html = '<div class="rankings"><strong>🏆 Rankings</strong>';
    
    rankings.forEach((item, index) => {
        let positionClass = 'other';
        if (index === 0) positionClass = 'first';
        else if (index === 1) positionClass = 'second';
        else if (index === 2) positionClass = 'third';
        
        const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `${index + 1}`;
        
        html += `
            <div class="ranking-item">
                <div class="ranking-position ${positionClass}">${medal}</div>
                <span class="ranking-name">${escapeHtml(item.name)}</span>
                <span class="ranking-score">${item.score.toFixed(1)}</span>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// ============================================
// Message Display (Non-streaming)
// ============================================

function addMessage(text, sender, isError = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const avatar = sender === 'user' ? '👤' : '🤖';
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-text ${isError ? 'error' : ''}">
                <p>${escapeHtml(text)}</p>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// ============================================
// Utilities
// ============================================

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function clearChat() {
    // Keep only the welcome message
    const messages = chatMessages.querySelectorAll('.message');
    messages.forEach((msg, index) => {
        if (index > 0) {
            msg.remove();
        }
    });
}
