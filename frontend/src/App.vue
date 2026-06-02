<template>
  <div class="app-container">
    <!-- Decorative background glows -->
    <div class="bg-glow"></div>
    <div class="bg-glow-2"></div>
    
    <!-- Top Navigation Header -->
    <header class="app-header">
      <div class="brand-section">
        <div class="brand-logo">S</div>
        <div>
          <h1 class="brand-name">SAR Engine Manager <span class="brand-badge">Admin Service</span></h1>
        </div>
      </div>
      
      <nav class="tab-navigation">
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'ingestion' }"
          @click="activeTab = 'ingestion'"
        >
          📂 Ingestion Manager
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'playground' }"
          @click="activeTab = 'playground'"
        >
          ⚡ API Playground & Tester
        </button>
      </nav>
    </header>

    <!-- Main Content Tab Swapper -->
    <main style="flex: 1;">
      <KeepAlive>
        <component :is="currentTabComponent" />
      </KeepAlive>
    </main>

    <footer style="margin-top: 3rem; border-top: 1px solid var(--border-color); padding: 1.5rem 0; text-align: center; font-size: 0.8rem; color: var(--text-muted);">
      SAR Engine RAG System v3.0 • Powered by Qdrant (Dense + Sparse Hybrid) & gpt-4o-mini
    </footer>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import IngestionDashboard from './components/IngestionDashboard.vue'
import ApiPlayground from './components/ApiPlayground.vue'

const activeTab = ref('ingestion')

const currentTabComponent = computed(() => {
  return activeTab.value === 'ingestion' ? IngestionDashboard : ApiPlayground
})
</script>
