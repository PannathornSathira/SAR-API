<template>
  <div class="playground-grid">
    <!-- Left Column: DB selector & API details -->
    <div class="left-column">
      <div class="panel-card">
        <h3 style="margin-bottom: 1rem;">Target Database</h3>
        <div class="form-group">
          <label class="form-label">Active Database</label>
          <select 
            class="input-control" 
            v-model="store.selectedCollection"
            @change="clearChat"
          >
            <option value="" disabled>-- Select a database to test --</option>
            <option v-for="col in store.collections" :key="col" :value="col">
              {{ col }}
            </option>
          </select>
        </div>
      </div>

      <!-- API Details Card -->
      <div v-if="store.selectedCollection" class="panel-card" style="margin-top: 1rem;">
        <h3 style="margin-bottom: 0.75rem;">REST API Endpoint</h3>
        <p style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 1rem;">
          External systems can query this database by calling this URL.
        </p>

        <label class="form-label">Endpoint URL</label>
        <div class="copy-endpoint-box">
          <span class="endpoint-text">{{ endpointUrl }}</span>
          <button class="btn-copy" @click="copyText(endpointUrl, 'url')">
            {{ copiedUrl ? 'Copied!' : 'Copy' }}
          </button>
        </div>

        <label class="form-label" style="margin-top: 1.5rem;">CURL Integration</label>
        <div class="codebox-curl">
          {{ curlCommand }}
        </div>
        <button 
          class="btn-secondary" 
          style="margin-top: 0.75rem; width: 100%; font-size: 0.8rem; padding: 0.4rem 0;"
          @click="copyText(curlCommand, 'curl')"
        >
          {{ copiedCurl ? 'Curl Command Copied!' : 'Copy Curl Command' }}
        </button>
      </div>
      
      <div v-else class="panel-card" style="margin-top: 1rem; text-align: center; color: var(--text-muted); padding: 2rem 1.5rem;">
        <p style="font-size: 0.85rem;">Select an active database to view API endpoints and curl examples.</p>
      </div>
    </div>

    <!-- Right Column: Interactive Chat Simulation -->
    <div class="right-column panel-card" style="padding: 1.5rem; display: flex; flex-direction: column;">
      <div class="card-title-bar" style="margin-bottom: 1rem; padding-bottom: 0.75rem;">
        <div>
          <h2>Chat Simulation & RAG Tester</h2>
          <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.15rem;">
            Test retrieval score thresholding and context synthesis.
          </p>
        </div>
        <button 
          class="btn-secondary" 
          style="padding: 0.35rem 0.75rem; font-size: 0.8rem;" 
          @click="clearChat"
          :disabled="messages.length === 0"
        >
          Clear History
        </button>
      </div>

      <!-- Chat workspace pane -->
      <div class="chat-workspace">
        <!-- Welcoming simulator screen -->
        <div v-if="!store.selectedCollection" class="welcome-sim">
          <div class="welcome-sim-icon">💬</div>
          <h3>Select a Database</h3>
          <p style="font-size: 0.85rem; max-width: 350px;">
            Choose one of your indexed collections from the left panel to begin querying.
          </p>
        </div>
        
        <div v-else-if="messages.length === 0" class="welcome-sim">
          <div class="welcome-sim-icon">🤖</div>
          <h3>Simulating: {{ store.selectedCollection }}</h3>
          <p style="font-size: 0.85rem; max-width: 350px;">
            Ask a question in Thai or English to test RAG matching.
          </p>
        </div>

        <!-- Scrollable messages container -->
        <div v-else class="chat-messages" ref="chatScrollContainer">
          <div 
            v-for="(msg, index) in messages" 
            :key="index"
            class="chat-bubble-container"
            :class="msg.role"
          >
            <!-- Chat bubble -->
            <div class="chat-bubble">
              {{ msg.content }}
            </div>
            
            <!-- Metadata & Debugger panel -->
            <div v-if="msg.role === 'bot'" class="bubble-meta">
              <span class="badge" :class="msg.matchType">
                {{ getMatchLabel(msg.matchType) }}
              </span>
              <span v-if="msg.matchType !== 'none' && msg.matchType !== 'own_knowledge'">
                Score: <strong>{{ msg.score.toFixed(3) }}</strong>
              </span>
              <button 
                v-if="msg.context && msg.context.length > 0" 
                class="debug-details-link"
                @click="msg.showDebug = !msg.showDebug"
              >
                {{ msg.showDebug ? 'Hide Debug' : 'Debug Logs' }}
              </button>
            </div>

            <!-- Debug collapse panel -->
            <div v-if="msg.role === 'bot' && msg.showDebug" class="chat-debug-card">
              <div class="debug-metric-row">
                <span>Reranker Match Score</span>
                <strong>{{ msg.score.toFixed(4) }}</strong>
              </div>
              <div class="debug-metric-row">
                <span>Sources Refereed</span>
                <span style="color: #60a5fa;">{{ msg.sources.join(', ') || 'None' }}</span>
              </div>
              
              <div class="debug-contexts-title" style="margin-top: 0.25rem;">Retrieved Database Passages</div>
              <div 
                v-for="(ctx, cIdx) in msg.context" 
                :key="cIdx" 
                class="debug-context-item"
              >
                <div class="debug-context-meta">
                  <span>File: {{ ctx.source_file }}</span>
                  <span v-if="ctx.category">Category: {{ ctx.category }}</span>
                </div>
                <div class="debug-context-body">{{ ctx.content }}</div>
              </div>
            </div>
          </div>

          <!-- Typing loading state -->
          <div v-if="botTyping" class="chat-bubble-container bot">
            <div class="chat-bubble" style="display: flex; align-items: center; gap: 0.25rem;">
              <span class="spinner" style="border-top-color: var(--text-secondary); width: 12px; height: 12px; margin-left: 0;"></span>
              <span style="font-size: 0.85rem; color: var(--text-secondary);">Querying database...</span>
            </div>
          </div>
        </div>

        <!-- Chat Input Bar -->
        <div class="chat-input-bar">
          <input 
            type="text" 
            class="input-control chat-input" 
            v-model="userInput" 
            placeholder="Type your test query..."
            @keyup.enter="sendMessage"
            :disabled="!store.selectedCollection || botTyping"
          />
          <button 
            class="btn-send" 
            @click="sendMessage"
            :disabled="!store.selectedCollection || botTyping || !userInput.trim()"
          >
            <svg viewBox="0 0 24 24">
              <path d="M2,21L23,12L2,3V10L17,12L2,14V21Z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useSarStore } from '../stores/sarStore'

const store = useSarStore()

const userInput = ref('')
const messages = ref([])
const botTyping = ref(false)
const chatScrollContainer = ref(null)

const copiedUrl = ref(false)
const copiedCurl = ref(false)

const endpointUrl = computed(() => {
  if (!store.selectedCollection) return ''
  return `http://localhost:8000/api/v1/query/${store.selectedCollection}`
})

const curlCommand = computed(() => {
  if (!store.selectedCollection) return ''
  return `curl -X POST "${endpointUrl.value}" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "คำถามของคุณ", "chat_history": []}'`
})

const getMatchLabel = (type) => {
  switch (type) {
    case 'exact': return 'Exact Match (>= 0.525)'
    case 'related': return 'Related Match (>= 0.30)'
    case 'own_knowledge': return 'General Knowledge'
    default: return 'No Match (< 0.30)'
  }
}

// Send user question to FastAPI dynamic endpoint
const sendMessage = async () => {
  const query = userInput.value.trim()
  if (!query || botTyping.value || !store.selectedCollection) return

  // 1. Append User Bubble
  messages.value.push({
    role: 'user',
    content: query
  })
  userInput.value = ''
  
  await scrollToBottom()
  botTyping.value = true

  // 2. Format chat history payload for query rewriter
  const chatHistory = messages.value
    .slice(0, -1) // Exclude current query
    .map(m => ({
      role: m.role === 'user' ? 'user' : 'assistant',
      content: m.content
    }))

  try {
    const data = await store.queryCollection(store.selectedCollection, query, chatHistory)
    
    // 3. Append Bot Bubble
    messages.value.push({
      role: 'bot',
      content: data.response,
      matchType: data.match_type,
      score: data.score,
      sources: data.sources || [],
      context: data.context || [],
      showDebug: false
    })
  } catch (err) {
    messages.value.push({
      role: 'bot',
      content: `⚠️ Failed to query service. Connection issue or bad API response: ${err.message}`,
      matchType: 'none',
      score: 0,
      sources: [],
      context: [],
      showDebug: false
    })
  } finally {
    botTyping.value = false
    await scrollToBottom()
  }
}

const clearChat = () => {
  messages.value = []
  store.error = null
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatScrollContainer.value) {
    chatScrollContainer.value.scrollTop = chatScrollContainer.value.scrollHeight
  }
}

const copyText = (text, type) => {
  navigator.clipboard.writeText(text).then(() => {
    if (type === 'url') {
      copiedUrl.value = true
      setTimeout(() => { copiedUrl.value = false }, 2000)
    } else if (type === 'curl') {
      copiedCurl.value = true
      setTimeout(() => { copiedCurl.value = false }, 2000)
    }
  })
}
</script>
