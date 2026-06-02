<template>
  <div class="dashboard-grid">
    <!-- Left Panel: Configuration & Processing Timeline -->
    <div class="left-column">
      <div class="panel-card">
        <h3 style="margin-bottom: 1.25rem;">Ingestion Target</h3>
        
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
          <p v-if="store.collections.length === 0" style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">
            No databases found. Create one first!
          </p>
        </div>
      </div>

      <!-- File Upload Zone -->
      <div class="panel-card" style="margin-top: 1rem;">
        <h3 style="margin-bottom: 1.25rem;">Upload Document</h3>
        
        <div 
          class="dropzone" 
          :class="{ active: isDragActive }"
          @dragover.prevent="onDragOver"
          @dragleave.prevent="onDragLeave"
          @drop.prevent="onDrop"
          @click="triggerFileInput"
          v-if="store.statusStep === 0"
        >
          <div class="upload-icon">📥</div>
          <p>Drag & Drop your document here</p>
          <span>Supports .pdf, .docx, .txt</span>
          <input 
            type="file" 
            ref="fileInput" 
            style="display: none;" 
            accept=".pdf,.docx,.txt"
            @change="onFileSelected"
          />
        </div>

        <!-- Selected File Status Badge -->
        <div v-else class="file-info-badge">
          <span>Active File:</span>
          <span class="file-name" :title="store.filename">{{ store.filename }}</span>
          <button 
            class="btn-danger-text" 
            style="padding: 0 0.25rem;"
            @click="cancelUpload" 
            :disabled="store.statusStep === 4"
          >
            Reset
          </button>
        </div>

        <!-- Step timeline status tracker -->
        <div v-if="store.statusStep > 0" class="timeline-tracker">
          
          <!-- Step 1: Text extraction -->
          <div class="timeline-step" :class="{ 
            active: store.statusStep === 1 || store.statusStep === 2, 
            completed: store.statusStep > 2 
          }">
            <div class="step-indicator">
              <span v-if="store.statusStep > 2">✓</span>
              <span v-else>1</span>
            </div>
            <div class="step-details">
              <div class="step-title">
                Extracting Clean Text
                <span v-if="store.statusStep === 1" class="spinner"></span>
              </div>
              <div class="step-desc">Reading clean paragraph/page layout text</div>
            </div>
          </div>

          <!-- Step 2: FAQ Extraction -->
          <div class="timeline-step" :class="{ 
            active: store.statusStep === 2, 
            completed: store.statusStep > 2 
          }">
            <div class="step-indicator">
              <span v-if="store.statusStep > 2">✓</span>
              <span v-else>2</span>
            </div>
            <div class="step-details">
              <div class="step-title">
                Generating FAQ Pairs
                <span v-if="store.statusStep === 2" class="spinner"></span>
              </div>
              <div class="step-desc">gpt-4o-mini structured analysis</div>
            </div>
          </div>

          <!-- Step 3: Review Grid -->
          <div class="timeline-step" :class="{ 
            active: store.statusStep === 3, 
            completed: store.statusStep > 3 
          }">
            <div class="step-indicator">
              <span v-if="store.statusStep > 3">✓</span>
              <span v-else>3</span>
            </div>
            <div class="step-details">
              <div class="step-title">Administrative Review</div>
              <div class="step-desc">Modify question content & categories</div>
            </div>
          </div>

          <!-- Step 4: Vector Store Ingestion -->
          <div class="timeline-step" :class="{ 
            active: store.statusStep === 4, 
            completed: store.statusStep > 4 
          }">
            <div class="step-indicator">
              <span v-if="store.statusStep > 4">✓</span>
              <span v-else>4</span>
            </div>
            <div class="step-details">
              <div class="step-title">
                Qdrant Embedding & Ingestion
                <span v-if="store.statusStep === 4" class="spinner"></span>
              </div>
              <div class="step-desc">Dense (large-3) & Sparse (BM25) configurations</div>
            </div>
          </div>

          <!-- Step 5: Success -->
          <div class="timeline-step" :class="{ completed: store.statusStep === 5 }">
            <div class="step-indicator">
              <span v-if="store.statusStep === 5">✓</span>
              <span v-else>5</span>
            </div>
            <div class="step-details">
              <div class="step-title">Success</div>
              <div class="step-desc">Knowledge indexed and queryable!</div>
            </div>
          </div>
          
        </div>
      </div>
      
      <!-- Error Alerts -->
      <div v-if="store.error" class="panel-card" style="border-color: rgba(239, 68, 68, 0.4); background: rgba(239, 68, 68, 0.05); margin-top: 1rem; padding: 1.25rem;">
        <span style="color: var(--none-color); font-weight: 600; font-size: 0.9rem; display: block; margin-bottom: 0.25rem;">⚠️ Error Encountered</span>
        <p style="font-size: 0.85rem; color: var(--text-secondary);">{{ store.error }}</p>
        <button class="btn-secondary" style="margin-top: 0.75rem; width: 100%; padding: 0.4rem;" @click="store.error = null">Dismiss</button>
      </div>
    </div>

    <!-- Right Panel: FAQ Review Grid & Management -->
    <div class="right-column panel-card" style="min-height: 500px;">
      
      <!-- Inactive / Idle state -->
      <div v-if="store.statusStep < 3" class="empty-review-state">
        <div class="empty-review-icon">📑</div>
        <h2>FAQ Generation Grid</h2>
        <p style="max-width: 400px; font-size: 0.9rem;">
          Select a database target and drag a document into the upload zone to automatically generate FAQ pairs for review.
        </p>
      </div>

      <!-- Ingesting state -->
      <div v-else-if="store.statusStep === 4" class="empty-review-state">
        <div class="spinner" style="width: 40px; height: 40px; border-width: 3px; border-top-color: var(--accent-purple); margin-bottom: 1rem;"></div>
        <h2>Embedding FAQ Pairs...</h2>
        <p>Generating dense vector embeddings and sparse indexes in Qdrant.</p>
      </div>

      <!-- Success State -->
      <div v-else-if="store.statusStep === 5" class="empty-review-state" style="color: var(--exact-color);">
        <div style="font-size: 4rem; margin-bottom: 0.5rem;">🎉</div>
        <h2>Ingestion Completed!</h2>
        <p style="color: var(--text-secondary); max-width: 400px; font-size: 0.9rem; margin-bottom: 1.5rem;">
          All FAQ pairs have been embedded and stored. External integrations can now query the collection.
        </p>
        <button class="btn-secondary" @click="resetFull">Start New Upload</button>
      </div>

      <!-- Active Review State -->
      <div v-else-if="store.statusStep === 3" class="faq-review-container">
        <div class="faq-review-header">
          <div>
            <h2>Review Extracted FAQs</h2>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">
              Generated {{ store.extractedFaqs.length }} FAQ pairs. Review and edit before saving.
            </p>
          </div>
          <div style="display: flex; gap: 0.75rem; align-items: center;">
            <button class="btn-secondary" @click="cancelUpload">Cancel</button>
            <button class="btn-primary" @click="submitIngestion" style="width: auto;">
              Save & Ingest ({{ store.extractedFaqs.length }} pairs)
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
              <div style="display: flex; align-items: center; gap: 0.5rem; width: 100%;">
                <span class="faq-textarea-label" style="margin-bottom: 0;">Category</span>
                <input 
                  type="text" 
                  class="input-control category-input" 
                  v-model="faq.category" 
                  placeholder="Category"
                />
              </div>
              <button class="btn-danger-text" @click="deleteFaq(index)" title="Delete FAQ">
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
import { ref, onMounted } from 'vue'
import { useSarStore } from '../stores/sarStore'

const store = useSarStore()

const targetMode = ref('create') // 'create' or 'append'
const newDbName = ref('')
const isDragActive = ref(false)
const fileInput = ref(null)

onMounted(() => {
  store.fetchCollections()
})

const setTargetMode = (mode) => {
  targetMode.value = mode
  store.error = null
}

// Drag & Drop event handlers
const onDragOver = () => {
  isDragActive.value = true
}

const onDragLeave = () => {
  isDragActive.value = false
}

const onDrop = (e) => {
  isDragActive.value = false
  const files = e.dataTransfer.files
  if (files.length > 0) {
    processFile(files[0])
  }
}

const triggerFileInput = () => {
  fileInput.value.click()
}

const onFileSelected = (e) => {
  const files = e.target.files
  if (files.length > 0) {
    processFile(files[0])
  }
}

// Validate targets and start text extraction
const processFile = async (file) => {
  store.error = null
  
  // 1. Determine target collection name
  let targetCollection = ''
  if (targetMode.value === 'create') {
    const rawName = newDbName.value.trim()
    if (!rawName) {
      store.error = 'Please enter a name for the new database.'
      return
    }
    // Clean name
    targetCollection = rawName.toLowerCase().replace(/[^a-z0-9_-]/g, '_')
  } else {
    targetCollection = store.selectedCollection
    if (!targetCollection) {
      store.error = 'Please select an existing database from the dropdown.'
      return
    }
  }

  // 2. Perform validation checks
  const ext = file.name.split('.').pop().toLowerCase()
  if (!['pdf', 'docx', 'txt'].includes(ext)) {
    store.error = `Unsupported file format: .${ext}. Please upload a .pdf, .docx, or .txt file.`
    return
  }

  // 3. If in create mode, create the collection first
  if (targetMode.value === 'create') {
    const success = await store.createNewCollection(targetCollection)
    if (!success) return
  }

  // Set the selected database in store
  store.selectedCollection = targetCollection

  // 4. Run FAQ extraction
  await store.extractFaqs(file)
}

const deleteFaq = (index) => {
  store.extractedFaqs.splice(index, 1)
}

const cancelUpload = () => {
  store.resetIngestion()
  if (targetMode.value === 'create') {
    newDbName.value = ''
  }
}

const submitIngestion = async () => {
  if (store.extractedFaqs.length === 0) {
    store.error = 'The FAQ list is empty. Nothing to ingest.'
    return
  }
  await store.ingestApprovedFaqs(store.selectedCollection)
}

const resetFull = () => {
  store.resetIngestion()
  newDbName.value = ''
}
</script>
