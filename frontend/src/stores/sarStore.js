import { defineStore } from 'pinia'

const API_BASE_URL = 'http://localhost:8000'

export const useSarStore = defineStore('sar', {
  state: () => ({
    collections: [],
    selectedCollection: '',
    
    // Extraction config
    language: 'Thai',
    numQuestions: 10,
    
    // Ingestion States
    // 0 = Idle, 1 = Extracting Text/Generating FAQs, 3 = FAQ Review Grid, 4 = Embedding & Ingesting, 5 = Success
    statusStep: 0,
    
    // Progress for multiple files
    totalFiles: 0,
    processedFiles: 0,
    currentFileName: '',
    
    filename: '', // Just for keeping some legacy stuff if needed, though we track multi-files now
    extractedFaqs: [],
    
    // Cost
    totalExtractionCost: 0.0,
    totalExpansionCost: 0.0,
    
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
    
    async extractFaqs(files) {
      this.error = null
      this.statusStep = 1 // Step 1: Extracting / Generation
      this.totalFiles = files.length
      this.processedFiles = 0
      this.extractedFaqs = []
      this.totalExtractionCost = 0.0
      
      try {
        for (let i = 0; i < files.length; i++) {
          const file = files[i]
          this.currentFileName = file.name
          
          const formData = new FormData()
          formData.append('file', file)
          formData.append('language', this.language)
          formData.append('num_questions', this.numQuestions)
          
          const response = await fetch(`${API_BASE_URL}/api/v1/extract-faq`, {
            method: 'POST',
            body: formData
          })
          
          if (!response.ok) {
            const detail = await response.json()
            throw new Error(detail.detail || `Extraction failed for ${file.name}`)
          }
          
          const data = await response.json()
          this.extractedFaqs = this.extractedFaqs.concat(data.faqs || [])
          this.totalExtractionCost += (data.extraction_cost || 0.0)
          
          this.processedFiles += 1
        }
        
        this.filename = 'Multiple Files'
        if (files.length === 1) {
          this.filename = files[0].name
        }
        
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
            faqs: this.extractedFaqs,
            language: this.language
          })
        })
        
        if (!response.ok) {
          const detail = await response.json()
          throw new Error(detail.detail || 'Ingestion failed')
        }
        
        const data = await response.json()
        this.totalExpansionCost = data.expansion_cost || 0.0
        
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
      this.totalFiles = 0
      this.processedFiles = 0
      this.currentFileName = ''
      this.totalExtractionCost = 0.0
      this.totalExpansionCost = 0.0
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
