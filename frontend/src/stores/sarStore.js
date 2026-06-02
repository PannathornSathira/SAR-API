import { defineStore } from 'pinia'

const API_BASE_URL = 'http://localhost:8000'

export const useSarStore = defineStore('sar', {
  state: () => ({
    collections: [],
    selectedCollection: '',
    
    // Ingestion States
    // 0 = Idle, 1 = Extracting Text, 2 = LLM Generating FAQs, 3 = FAQ Review Grid, 4 = Embedding & Ingesting, 5 = Success
    statusStep: 0,
    filename: '',
    extractedFaqs: [],
    
    // UI Helpers
    loading: false,
    error: null,
    successMessage: null
  }),
  
  actions: {
    async fetchCollections() {
      this.loading = true
      this.error = null
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/collections`)
        if (!response.ok) throw new Error('Failed to load collections')
        const data = await response.json()
        this.collections = data.collections || []
        
        // Auto-select first collection if none selected
        if (this.collections.length > 0 && !this.selectedCollection) {
          this.selectedCollection = this.collections[0]
        }
      } catch (err) {
        console.error(err)
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    
    async createNewCollection(name) {
      this.loading = true
      this.error = null
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/collections/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name })
        })
        if (!response.ok) {
          const detail = await response.json()
          throw new Error(detail.detail || 'Failed to create collection')
        }
        await this.fetchCollections()
        this.selectedCollection = name.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '_')
        this.successMessage = `Collection "${name}" created successfully!`
        setTimeout(() => { this.successMessage = null }, 3000)
        return true
      } catch (err) {
        console.error(err)
        this.error = err.message
        return false
      } finally {
        this.loading = false
      }
    },
    
    async extractFaqs(file) {
      this.error = null
      this.filename = file.name
      this.statusStep = 1 // Step 1: Extracting Text
      
      const formData = new FormData()
      formData.append('file', file)
      
      try {
        // We simulate intermediate transition state visually in UI
        setTimeout(() => {
          if (this.statusStep === 1) {
            this.statusStep = 2 // Step 2: LLM FAQ Generation
          }
        }, 1500)
        
        const response = await fetch(`${API_BASE_URL}/api/v1/extract-faq`, {
          method: 'POST',
          body: formData
        })
        
        if (!response.ok) {
          const detail = await response.json()
          throw new Error(detail.detail || 'Extraction failed')
        }
        
        const data = await response.json()
        this.extractedFaqs = data.faqs || []
        this.statusStep = 3 // Step 3: FAQ Review Grid
      } catch (err) {
        console.error(err)
        this.error = err.message
        this.statusStep = 0 // Reset
      }
    },
    
    async ingestApprovedFaqs(collectionName) {
      this.error = null
      this.statusStep = 4 // Step 4: Embedding & Ingestion
      
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/collections/ingest`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            collection_name: collectionName,
            filename: this.filename,
            faqs: this.extractedFaqs
          })
        })
        
        if (!response.ok) {
          const detail = await response.json()
          throw new Error(detail.detail || 'Ingestion failed')
        }
        
        this.statusStep = 5 // Step 5: Success
        await this.fetchCollections() // Refresh collections list
      } catch (err) {
        console.error(err)
        this.error = err.message
        this.statusStep = 3 // Rollback to review grid on failure
      }
    },
    
    resetIngestion() {
      this.statusStep = 0
      this.filename = ''
      this.extractedFaqs = []
      this.error = null
    },
    
    async queryCollection(collectionName, query, chatHistory = []) {
      this.error = null
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/query/${collectionName}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query,
            chat_history: chatHistory
          })
        })
        
        if (!response.ok) {
          const detail = await response.json()
          throw new Error(detail.detail || 'Query request failed')
        }
        
        return await response.json()
      } catch (err) {
        console.error(err)
        this.error = err.message
        throw err
      }
    }
  }
})
