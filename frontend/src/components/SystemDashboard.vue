<template>
  <div class="dashboard-grid">
    <div class="panel-card" style="width: 100%; min-height: 500px">
      <h2>📊 System Dashboard</h2>
      <br />
      <div
        style="
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 2rem;
        "
      >
        <button
          class="btn-primary"
          @click="refreshStats"
          :disabled="store.loading"
        >
          <span
            v-if="store.loading"
            class="spinner"
            style="width: 14px; height: 14px; border-width: 2px"
          ></span>
          <span v-else>🔄 Refresh</span>
        </button>
      </div>

      <div
        v-if="store.loading && store.collectionStats.length === 0"
        style="text-align: center; padding: 3rem; color: var(--text-muted)"
      >
        <div
          class="spinner"
          style="
            width: 40px;
            height: 40px;
            border-top-color: var(--accent-purple);
            margin: 0 auto 1rem;
          "
        ></div>
        <p>Loading database statistics...</p>
      </div>

      <div
        v-else-if="store.collectionStats.length === 0"
        style="text-align: center; padding: 3rem; color: var(--text-muted)"
      >
        <p>No databases found. Go to the Ingestion Manager to create one!</p>
      </div>

      <div v-else class="stats-grid">
        <div
          v-for="stat in store.collectionStats"
          :key="stat.name"
          class="stat-card"
          @click="openFaqModal(stat.name)"
        >
          <div class="stat-header">
            <h3>{{ stat.name }}</h3>
            <span
              class="status-badge"
              :class="stat.status === 'green' ? 'status-green' : 'status-gray'"
            >
              {{ stat.status === "green" ? "Active" : stat.status }}
            </span>
          </div>
          <div class="stat-body">
            <div class="stat-item">
              <span class="stat-label">Total Documents / FAQ Points</span>
              <span class="stat-value">{{
                stat.points_count.toLocaleString()
              }}</span>
            </div>
            <!-- More stats can be added here if available in the future -->
          </div>
        </div>
      </div>
    </div>

    <!-- FAQ Viewer Modal Overlay -->
    <div v-if="isModalOpen" class="modal-overlay" @click.self="closeModal">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ activeCollection }} FAQs</h2>
          <button
            class="btn-danger-text"
            style="font-size: 1.5rem; line-height: 1; padding: 0.25rem 0.5rem"
            @click="closeModal"
          >
            &times;
          </button>
        </div>

        <div v-if="isLoadingFaqs" style="text-align: center; padding: 3rem">
          <div
            class="spinner"
            style="
              width: 40px;
              height: 40px;
              border-top-color: var(--accent-purple);
              margin: 0 auto 1rem;
            "
          ></div>
          <p>Fetching FAQs from database...</p>
        </div>

        <div
          v-else-if="faqs.length === 0"
          style="text-align: center; padding: 3rem; color: var(--text-muted)"
        >
          <p>No FAQs found in this database.</p>
        </div>

        <div v-else class="faq-list">
          <p
            style="
              font-size: 0.85rem;
              color: var(--text-muted);
              margin-bottom: 1rem;
            "
          >
            Showing up to 50 sample FAQs from this collection.
          </p>
          <div v-for="faq in faqs" :key="faq.id" class="faq-item-card">
            <div class="faq-item-header">
              <span class="faq-category">{{
                faq.category || "Uncategorized"
              }}</span>
              <span class="faq-source"
                >📄 {{ faq.filename }} | ⚙️ {{ faq.source_type }}</span
              >
            </div>
            <div class="faq-question">
              <strong>Q:</strong> {{ faq.question }}
            </div>
            <div class="faq-answer"><strong>A:</strong> {{ faq.answer }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useSarStore } from "../stores/sarStore";

const store = useSarStore();

const isModalOpen = ref(false);
const activeCollection = ref("");
const isLoadingFaqs = ref(false);
const faqs = ref([]);

const refreshStats = () => {
  store.fetchCollectionStats();
};

const openFaqModal = async (collectionName) => {
  activeCollection.value = collectionName;
  isModalOpen.value = true;
  isLoadingFaqs.value = true;
  faqs.value = [];

  faqs.value = await store.fetchCollectionFaqs(collectionName);
  isLoadingFaqs.value = false;
};

const closeModal = () => {
  isModalOpen.value = false;
  activeCollection.value = "";
  faqs.value = [];
};

onMounted(() => {
  refreshStats();
});
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1rem;
}

.stat-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1rem;
  cursor: pointer;
  transition:
    transform 0.2s,
    box-shadow 0.2s,
    border-color 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: var(--accent-purple);
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.stat-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-primary);
  word-break: break-all;
}

.status-badge {
  font-size: 0.65rem;
  padding: 0.2rem 0.4rem;
  border-radius: 9999px;
  font-weight: 600;
  text-transform: uppercase;
}

.status-green {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.status-gray {
  background: rgba(107, 114, 128, 0.1);
  color: #6b7280;
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--accent-purple);
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  width: 90%;
  max-width: 800px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
}

.faq-list {
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.faq-item-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1rem;
}

.faq-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  font-size: 0.75rem;
}

.faq-category {
  background: rgba(139, 92, 246, 0.1);
  color: var(--accent-purple);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;
}

.faq-source {
  color: var(--text-muted);
}

.faq-question {
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
}

.faq-answer {
  color: var(--text-secondary);
  font-size: 0.9rem;
  white-space: pre-wrap;
}
</style>
