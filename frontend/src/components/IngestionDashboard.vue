<template>
  <div class="dashboard-grid">
    <!-- Left Panel: Configuration & Processing Timeline -->
    <div class="left-column">
      <div class="panel-card">
        <h3 style="margin-bottom: 1.25rem">Ingestion Target</h3>

        <!-- Target Database Toggle -->
        <div class="toggle-group">
          <div
            class="toggle-option"
            :class="{ active: targetMode === 'create' }"
            @click="setTargetMode('create')"
          >
            Create New DB
          </div>
          <div
            class="toggle-option"
            :class="{ active: targetMode === 'append' }"
            @click="setTargetMode('append')"
          >
            Append to Existing
          </div>
        </div>

        <!-- Database Selection Fields -->
        <div v-if="targetMode === 'create'" class="form-group">
          <label class="form-label">New Database Name</label>
          <input
            type="text"
            class="input-control"
            v-model="newDbName"
            placeholder="e.g. hr_faq_2026"
            :disabled="store.statusStep > 0"
          />
        </div>

        <div v-else class="form-group">
          <label class="form-label">Select Database</label>
          <select
            class="input-control"
            v-model="store.selectedCollection"
            :disabled="store.statusStep > 0"
          >
            <option value="" disabled>-- Choose a Collection --</option>
            <option v-for="col in store.collections" :key="col" :value="col">
              {{ col }}
            </option>
          </select>
          <p
            v-if="store.collections.length === 0"
            style="
              font-size: 0.75rem;
              color: var(--text-muted);
              margin-top: 0.25rem;
            "
          >
            No databases found. Create one first!
          </p>
          <button
            v-if="store.selectedCollection && targetMode !== 'create'"
            class="btn-secondary"
            style="margin-top: 0.75rem; width: 100%; padding: 0.4rem"
            @click="downloadDbCsv(store.selectedCollection)"
          >
            📥 Download Full DB CSV
          </button>
        </div>
      </div>

      <!-- Settings Panel -->
      <div class="panel-card" style="margin-top: 1rem">
        <h3 style="margin-bottom: 1.25rem">FAQ Settings</h3>
        <div class="form-group">
          <label class="form-label">Language</label>
          <select
            class="input-control"
            v-model="store.language"
            :disabled="store.statusStep > 0"
          >
            <option value="Thai">Thai</option>
            <option value="English">English</option>
            <option value="Chinese (Simplified)">Chinese (Simplified)</option>
            <option value="Japanese">Japanese</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Approximate Questions per Doc</label>
          <input
            type="number"
            class="input-control"
            v-model="store.numQuestions"
            min="1"
            :disabled="store.statusStep > 0"
          />
        </div>
      </div>

      <!-- File Upload Zone -->
      <div class="panel-card" style="margin-top: 1rem">
        <h3 style="margin-bottom: 1.25rem">Upload Document(s)</h3>

        <div
          class="dropzone"
          :class="{ active: isDragActive, disabled: !isTargetValid }"
          @dragover.prevent="onDragOver"
          @dragleave.prevent="onDragLeave"
          @drop.prevent="onDrop"
          @click="isTargetValid ? triggerFileInput() : null"
          v-if="store.statusStep === 0"
        >
          <div class="upload-icon">📥</div>
          <p v-if="!isTargetValid" style="color: var(--text-muted)">
            Please configure Target Database first
          </p>
          <p v-else>Drag & Drop your documents here</p>
          <span>Supports .pdf, .docx, .txt</span>
          <input
            type="file"
            ref="fileInput"
            style="display: none"
            accept=".pdf,.docx,.txt"
            multiple
            @change="onFileSelected"
            :disabled="!isTargetValid"
          />
        </div>

        <!-- Pending Files Badge -->
        <div
          v-if="store.statusStep === 0 && pendingFiles.length > 0"
          style="margin-top: 1rem"
        >
          <h4 style="margin-bottom: 0.5rem; font-size: 0.9rem">
            Staged Files:
          </h4>
          <div
            v-for="(file, index) in pendingFiles"
            :key="index"
            class="file-info-badge"
            style="margin-bottom: 0.5rem"
          >
            <span class="file-name" :title="file.name">{{ file.name }}</span>
            <button
              class="btn-danger-text"
              style="padding: 0 0.25rem"
              @click="removePendingFile(index)"
            >
              Remove
            </button>
          </div>
          <button
            class="btn-primary"
            style="width: 100%; margin-top: 0.5rem"
            @click="processStagedFiles"
          >
            Process {{ pendingFiles.length }} Document(s)
          </button>
        </div>

        <!-- Processing Status -->
        <div
          v-if="store.statusStep > 0 && store.statusStep < 3"
          class="file-info-badge"
          style="margin-top: 1rem"
        >
          <span v-if="store.statusStep === 1"
            >Processing: {{ store.processedFiles + 1 }} /
            {{ store.totalFiles }}</span
          >
          <span class="file-name" :title="store.currentFileName">{{
            store.currentFileName
          }}</span>
          <span class="spinner" style="width: 16px; height: 16px"></span>
        </div>

        <!-- Processing Cost (Shown when done) -->
        <div
          v-if="store.statusStep >= 3"
          class="file-info-badge"
          style="
            margin-top: 1rem;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 0.25rem;
          "
        >
          <span><strong>Total Files:</strong> {{ store.totalFiles }}</span>
          <span
            ><strong>Extraction Cost:</strong> ${{
              store.totalExtractionCost.toFixed(4)
            }}</span
          >
          <span v-if="store.statusStep >= 5"
            ><strong>Expansion Cost:</strong> ${{
              store.totalExpansionCost.toFixed(4)
            }}</span
          >
          <span
            v-if="store.statusStep >= 5"
            style="color: var(--accent-purple); font-weight: bold"
          >
            <strong>Total Cost:</strong> ${{
              (store.totalExtractionCost + store.totalExpansionCost).toFixed(4)
            }}
          </span>
        </div>

        <!-- Step timeline status tracker -->
        <div
          v-if="store.statusStep > 0"
          class="timeline-tracker"
          style="margin-top: 1.5rem"
        >
          <!-- Step 1: Text extraction -->
          <div
            class="timeline-step"
            :class="{
              active: store.statusStep === 1,
              completed: store.statusStep > 1,
            }"
          >
            <div class="step-indicator">
              <span v-if="store.statusStep > 1">✓</span>
              <span v-else>1</span>
            </div>
            <div class="step-details">
              <div class="step-title">
                Extracting & Generating FAQs
                <span v-if="store.statusStep === 1" class="spinner"></span>
              </div>
              <div class="step-desc">Processing all selected documents</div>
            </div>
          </div>

          <!-- Step 3: Review Grid -->
          <div
            class="timeline-step"
            :class="{
              active: store.statusStep === 3,
              completed: store.statusStep > 3,
            }"
          >
            <div class="step-indicator">
              <span v-if="store.statusStep > 3">✓</span>
              <span v-else>2</span>
            </div>
            <div class="step-details">
              <div class="step-title">Administrative Review</div>
              <div class="step-desc">Modify question content & categories</div>
            </div>
          </div>

          <!-- Step 4: Vector Store Ingestion -->
          <div
            class="timeline-step"
            :class="{
              active: store.statusStep === 4,
              completed: store.statusStep > 4,
            }"
          >
            <div class="step-indicator">
              <span v-if="store.statusStep > 4">✓</span>
              <span v-else>3</span>
            </div>
            <div class="step-details">
              <div class="step-title">
                Expanding & Ingesting
                <span v-if="store.statusStep === 4" class="spinner"></span>
              </div>
              <div class="step-desc">
                Generating x5 variations and embedding in Qdrant
              </div>
            </div>
          </div>

          <!-- Step 5: Success -->
          <div
            class="timeline-step"
            :class="{ completed: store.statusStep === 5 }"
          >
            <div class="step-indicator">
              <span v-if="store.statusStep === 5">✓</span>
              <span v-else>4</span>
            </div>
            <div class="step-details">
              <div class="step-title">Success</div>
              <div class="step-desc">Knowledge indexed and queryable!</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Error Alerts -->
      <div
        v-if="store.error"
        class="panel-card"
        style="
          border-color: rgba(239, 68, 68, 0.4);
          background: rgba(239, 68, 68, 0.05);
          margin-top: 1rem;
          padding: 1.25rem;
        "
      >
        <span
          style="
            color: var(--none-color);
            font-weight: 600;
            font-size: 0.9rem;
            display: block;
            margin-bottom: 0.25rem;
          "
          >⚠️ Error Encountered</span
        >
        <p style="font-size: 0.85rem; color: var(--text-secondary)">
          {{ store.error }}
        </p>
        <button
          class="btn-secondary"
          style="margin-top: 0.75rem; width: 100%; padding: 0.4rem"
          @click="store.error = null"
        >
          Dismiss
        </button>
      </div>
    </div>

    <!-- Right Panel: FAQ Review Grid & Management -->
    <div class="right-column panel-card" style="min-height: 500px">
      <!-- Inactive / Idle state -->
      <div v-if="store.statusStep < 3" class="empty-review-state">
        <div class="empty-review-icon">📑</div>
        <h2>FAQ Generation Grid</h2>
        <p style="max-width: 400px; font-size: 0.9rem">
          Select a database target, configure settings, and stage documents into
          the upload zone to automatically generate FAQ pairs for review.
        </p>
      </div>

      <!-- Ingesting state -->
      <div v-else-if="store.statusStep === 4" class="empty-review-state">
        <div
          class="spinner"
          style="
            width: 40px;
            height: 40px;
            border-width: 3px;
            border-top-color: var(--accent-purple);
            margin-bottom: 1rem;
          "
        ></div>
        <h2>Expanding & Embedding FAQ Pairs...</h2>
        <p>
          Generating x5 question variations and dense vector embeddings in
          Qdrant.
        </p>
      </div>

      <!-- Success State -->
      <div
        v-else-if="store.statusStep === 5"
        class="empty-review-state"
        style="color: var(--exact-color)"
      >
        <div style="font-size: 4rem; margin-bottom: 0.5rem">🎉</div>
        <h2>Ingestion Completed!</h2>
        <p
          style="
            color: var(--text-secondary);
            max-width: 400px;
            font-size: 0.9rem;
            margin-bottom: 1.5rem;
          "
        >
          All FAQ pairs and variations have been embedded and stored. External
          integrations can now query the collection.
        </p>
        <button class="btn-secondary" @click="resetFull">
          Start New Upload
        </button>
      </div>

      <!-- Active Review State -->
      <div v-else-if="store.statusStep === 3" class="faq-review-container">
        <div class="faq-review-header">
          <div>
            <h2>Review Extracted FAQs</h2>
            <p
              style="
                font-size: 0.8rem;
                color: var(--text-muted);
                margin-top: 0.25rem;
              "
            >
              Generated {{ store.extractedFaqs.length }} FAQ pairs from
              {{ store.totalFiles }} document(s). Review and edit before saving.
            </p>
          </div>
          <div
            style="
              display: flex;
              gap: 0.75rem;
              align-items: center;
              justify-content: flex-end;
            "
          >
            <button
              class="btn-secondary"
              style="
                border-color: var(--accent-purple);
                color: var(--accent-purple);
                min-width: 170px;
                justify-content: center;
              "
              @click="addManualFaq"
            >
              ➕ Add manually
            </button>
            <button
              class="btn-secondary"
              style="min-width: 110px; justify-content: center"
              @click="cancelUpload"
            >
              Cancel
            </button>
            <button
              class="btn-primary"
              @click="submitIngestion"
              style="min-width: 180px; justify-content: center"
            >
              Save & Ingest ({{ store.extractedFaqs.length }})
            </button>
          </div>
        </div>

        <!-- FAQ Grid list -->
        <div class="faq-grid-scroll">
          <div
            v-for="(faq, index) in store.extractedFaqs"
            :key="index"
            class="faq-edit-card"
          >
            <div class="faq-card-header">
              <div
                style="
                  display: flex;
                  align-items: center;
                  gap: 0.5rem;
                  width: 100%;
                "
              >
                <span class="faq-textarea-label" style="margin-bottom: 0"
                  >Category</span
                >
                <input
                  type="text"
                  class="input-control category-input"
                  v-model="faq.category"
                  placeholder="Category"
                />
                <span
                  style="
                    font-size: 0.7rem;
                    color: var(--text-muted);
                    margin-left: 0.5rem;
                  "
                  :title="faq.filename"
                >
                  📄 {{ faq.filename }} | ⚙️ Source:
                  {{ faq.source_type || "LLM" }}
                </span>
              </div>
              <button
                class="btn-danger-text"
                @click="deleteFaq(index)"
                title="Delete FAQ"
              >
                🗑️ Delete
              </button>
            </div>

            <div class="faq-card-body">
              <div>
                <div class="faq-textarea-label">Question</div>
                <textarea
                  class="faq-textarea"
                  rows="2"
                  v-model="faq.question"
                  placeholder="FAQ Question"
                ></textarea>
              </div>
              <div>
                <div class="faq-textarea-label">Answer</div>
                <textarea
                  class="faq-textarea"
                  rows="4"
                  v-model="faq.answer"
                  placeholder="FAQ Answer"
                ></textarea>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from "vue";
import { useSarStore } from "../stores/sarStore";

const store = useSarStore();

const targetMode = ref("create"); // 'create' or 'append'
const newDbName = ref("");
const isDragActive = ref(false);
const fileInput = ref(null);

const pendingFiles = ref([]);

onMounted(() => {
  store.fetchCollections();
});

const isTargetValid = computed(() => {
  if (targetMode.value === "create") {
    return newDbName.value.trim().length > 0;
  }
  return store.selectedCollection !== "";
});

const setTargetMode = (mode) => {
  targetMode.value = mode;
  store.error = null;
};

// Drag & Drop event handlers
const onDragOver = () => {
  if (isTargetValid.value) isDragActive.value = true;
};

const onDragLeave = () => {
  isDragActive.value = false;
};

const onDrop = (e) => {
  isDragActive.value = false;
  if (!isTargetValid.value) return;

  const files = Array.from(e.dataTransfer.files);
  stageFiles(files);
};

const triggerFileInput = () => {
  fileInput.value.click();
};

const onFileSelected = (e) => {
  const files = Array.from(e.target.files);
  stageFiles(files);
};

const stageFiles = (files) => {
  store.error = null;
  for (let file of files) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "docx", "txt"].includes(ext)) {
      store.error = `Unsupported file format: .${ext}. Please upload a .pdf, .docx, or .txt file.`;
      continue;
    }
    pendingFiles.value.push(file);
  }
};

const removePendingFile = (index) => {
  pendingFiles.value.splice(index, 1);
};

// Validate targets and start text extraction
const processStagedFiles = async () => {
  store.error = null;

  if (pendingFiles.value.length === 0) {
    store.error = "No files to process.";
    return;
  }

  // 1. Determine target collection name
  let targetCollection = "";
  if (targetMode.value === "create") {
    const rawName = newDbName.value.trim();
    // Clean name
    targetCollection = rawName.toLowerCase().replace(/[^a-z0-9_-]/g, "_");
  } else {
    targetCollection = store.selectedCollection;
  }

  // 2. If in create mode, create the collection first
  if (targetMode.value === "create") {
    const success = await store.createNewCollection(targetCollection);
    if (!success) return;
  }

  // Set the selected database in store
  store.selectedCollection = targetCollection;

  // 3. Run FAQ extraction
  await store.extractFaqs(pendingFiles.value);
  pendingFiles.value = []; // clear staging
};

const deleteFaq = (index) => {
  store.extractedFaqs.splice(index, 1);
};

const addManualFaq = () => {
  store.extractedFaqs.unshift({
    category: "",
    question: "",
    answer: "",
    filename: "Manual Entry",
    source_type: "Manual",
  });
};

const downloadDbCsv = (collection) => {
  window.open(
    `http://localhost:8000/api/v1/collections/export/${collection}`,
    "_blank",
  );
};

const cancelUpload = () => {
  store.resetIngestion();
  pendingFiles.value = [];
  if (targetMode.value === "create") {
    newDbName.value = "";
  }
};

const submitIngestion = async () => {
  if (store.extractedFaqs.length === 0) {
    store.error = "The FAQ list is empty. Nothing to ingest.";
    return;
  }
  await store.ingestApprovedFaqs(store.selectedCollection);
};

const resetFull = () => {
  store.resetIngestion();
  pendingFiles.value = [];
  newDbName.value = "";
};
</script>

<style scoped>
.dropzone.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  border-color: var(--border-color);
  background: var(--bg-secondary);
}
</style>
