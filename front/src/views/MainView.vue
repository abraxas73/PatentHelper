<template>
  <div class="container">
    <!-- Image Modal -->
    <ImageModal 
      :isOpen="modalOpen"
      :image="selectedImage"
      @close="closeModal"
    />
    <!-- Header -->
    <div class="header">
      <h1>🔬 Patent Drawing Helper</h1>
      <p>특허 도면 자동 처리 시스템</p>
      <button @click="showHistory = true" class="history-button">📋 작업 이력</button>
    </div>

    <!-- Upload Section -->
    <div class="upload-section">
      <div 
        v-if="!isCompleted"
        class="upload-area"
        :class="{ dragover: isDragging }"
        @drop="handleDrop"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
      >
        <label class="upload-label">
          <input 
            type="file" 
            accept=".pdf"
            @change="handleFileSelect"
            ref="fileInput"
            :disabled="isProcessing || isCompleted"
          />
          <div class="upload-icon">📄</div>
          <div class="upload-text">PDF 파일을 선택하거나 드래그하세요</div>
          <div class="upload-hint">특허 문서 PDF 파일만 지원됩니다</div>
        </label>
      </div>

      <!-- Completed Message -->
      <div v-else class="completed-area">
        <div class="completion-icon">✅</div>
        <div class="completion-text">도면 추출이 완료되었습니다!</div>
        <div class="completion-file">{{ selectedFile?.name || uploadedFile?.name }}</div>
      </div>

      <!-- File Info -->
      <div v-if="selectedFile && !isCompleted" class="file-info">
        <div>
          <div class="file-name">{{ selectedFile.name }}</div>
          <div class="file-size">{{ formatFileSize(selectedFile.size) }}</div>
        </div>
        <button class="btn btn-danger" @click="removeFile" :disabled="isProcessing">삭제</button>
      </div>

      <!-- Action Buttons -->
      <div class="action-buttons">
        <button 
          v-if="!isCompleted"
          class="btn btn-primary"
          :disabled="!selectedFile || isProcessing"
          @click="uploadFile"
        >
          <span v-if="isProcessing" class="loading"></span>
          <span v-else>도면 추출 시작</span>
        </button>
        <button 
          v-else
          class="btn btn-success"
          @click="startNewTask"
        >
          새 작업
        </button>
        <span v-if="isProcessing" class="processing-time">
          처리 중... {{ processingTime }}초
        </span>
      </div>

      <!-- Job Status -->
      <div v-if="currentJobId" class="job-status">
        <div class="status-card">
          <div class="status-header">
            <span>작업 ID: {{ currentJobId }}</span>
            <span class="status-badge" :class="jobStatus">{{ jobStatusText }}</span>
          </div>
          <div v-if="jobMessage" class="status-message">{{ jobMessage }}</div>
          <div v-if="jobProgress > 0" class="progress-bar">
            <div class="progress-fill" :style="{ width: jobProgress + '%' }"></div>
          </div>
          <div v-if="jobStatus === 'COMPLETED'" class="result-link">
            <router-link :to="`/job/${currentJobId}`" class="btn-link">
              🔗 결과 페이지로 이동
            </router-link>
          </div>
        </div>
      </div>

      <!-- Messages -->
      <div v-if="errorMessage" class="error-message">
        ⚠️ {{ errorMessage }}
      </div>
      <div v-if="successMessage" class="success-message">
        ✅ {{ successMessage }}
      </div>
    </div>

    <!-- Results Section -->
    <div v-if="images.length > 0" class="results-section">
      <div class="results-header">
        <h2 class="results-title">추출된 도면</h2>
        <div class="results-count">총 {{ images.length }}개</div>
      </div>

      <!-- Image Grid -->
      <div class="image-grid">
        <div 
          v-for="(image, index) in images" 
          :key="index"
          class="image-card"
        >
          <div class="image-wrapper">
            <img 
              :src="image.url" 
              :alt="`Drawing ${index + 1}`"
              @click="openModal(image)"
              style="cursor: pointer;"
            />
          </div>
          <div class="image-info">
            <div class="image-title">도면 {{ index + 1 }}</div>
            <div class="image-meta">
              <span class="badge badge-original">원본</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Annotated Images -->
      <div v-if="annotatedImages.length > 0" class="annotated-section">
        <h3>어노테이션 도면</h3>
        <div class="image-grid">
          <div 
            v-for="(image, index) in annotatedImages" 
            :key="'annotated-' + index"
            class="image-card"
          >
            <div class="image-wrapper">
              <img 
                :src="image.url" 
                :alt="`Annotated ${index + 1}`"
                @click="openModal(image)"
                style="cursor: pointer;"
              />
            </div>
            <div class="image-info">
              <div class="image-title">어노테이션 {{ index + 1 }}</div>
              <div class="image-meta">
                <span class="badge badge-annotated">명칭 추가됨</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 번호 매핑 정보 -->
      <div v-if="numberMappings && Object.keys(numberMappings).length > 0" class="mappings-section">
        <h3>부품 번호 매핑</h3>
        <div class="mappings-grid">
          <div v-for="(value, key) in numberMappings" :key="key" class="mapping-item">
            <span class="mapping-key">{{ key }}</span>
            <span class="mapping-arrow">→</span>
            <span class="mapping-value">{{ value }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Job History Modal -->
    <div v-if="showHistory" class="modal-overlay" @click="showHistory = false">
      <div class="modal-dialog" @click.stop>
        <div class="modal-header">
          <h2>작업 이력</h2>
          <button @click="showHistory = false" class="close-button">×</button>
        </div>
        <div class="modal-body">
          <div v-if="jobHistory.length === 0" class="empty-history">
            아직 작업 이력이 없습니다.
          </div>
          <div v-else class="history-list">
            <div v-for="job in jobHistory" :key="job.jobId" class="history-item">
              <div class="history-info">
                <div class="history-filename">{{ getJobFilename(job) }}</div>
                <div class="history-date">{{ formatDate(job.createdAt) }}</div>
                <div class="history-status">
                  <span 
                    v-if="job.status === 'PROCESSING'"
                    class="status-badge clickable" 
                    :class="job.status"
                    @click.stop="trackProcessingJob(job)"
                    title="클릭하여 진행 상황 보기"
                  >
                    {{ getStatusText(job.status) }}
                  </span>
                  <span v-else class="status-badge" :class="job.status">
                    {{ getStatusText(job.status) }}
                  </span>
                </div>
              </div>
              <button 
                v-if="job.status === 'PROCESSING'"
                @click="trackProcessingJob(job)"
                class="view-button processing-button"
              >
                진행 상황
              </button>
              <router-link v-else :to="`/job/${job.jobId}`" class="view-button">
                보기
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onUnmounted, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import ImageModal from '../ImageModal.vue'
import config from '../config'

export default {
  name: 'MainView',
  components: {
    ImageModal
  },
  setup() {
    const router = useRouter()
    const selectedFile = ref(null)
    const uploadedFile = ref(null)
    const isDragging = ref(false)
    const isProcessing = ref(false)
    const images = ref([])
    const annotatedImages = ref([])
    const errorMessage = ref('')
    const successMessage = ref('')
    const numberMappings = ref({})
    const modalOpen = ref(false)
    const selectedImage = ref(null)
    const processingTime = ref(0)
    const processingTimer = ref(null)
    const progressMessage = ref('')
    const progress = ref(0)
    const isCompleted = ref(false)  // Track if extraction is completed
    
    // Serverless specific
    const currentJobId = ref(null)
    const jobStatus = ref('')
    const jobMessage = ref('')
    const jobProgress = ref(0)
    const statusCheckInterval = ref(null)
    const showHistory = ref(false)
    const jobHistory = ref([])

    const jobStatusText = computed(() => {
      const statusMap = {
        'QUEUED': '대기 중',
        'PROCESSING': '처리 중',
        'COMPLETED': '완료',
        'FAILED': '실패'
      }
      return statusMap[jobStatus.value] || jobStatus.value
    })

    const handleFileSelect = (event) => {
      const file = event.target.files[0]
      if (file && file.type === 'application/pdf') {
        selectedFile.value = file
        errorMessage.value = ''
      } else {
        errorMessage.value = 'PDF 파일만 업로드 가능합니다.'
      }
    }

    const handleDrop = (event) => {
      event.preventDefault()
      isDragging.value = false
      
      const file = event.dataTransfer.files[0]
      if (file && file.type === 'application/pdf') {
        selectedFile.value = file
        errorMessage.value = ''
      } else {
        errorMessage.value = 'PDF 파일만 업로드 가능합니다.'
      }
    }

    const removeFile = () => {
      selectedFile.value = null
      images.value = []
      annotatedImages.value = []
      errorMessage.value = ''
      successMessage.value = ''
      currentJobId.value = null
      jobStatus.value = ''
      jobMessage.value = ''
      jobProgress.value = 0
    }

    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 Bytes'
      const k = 1024
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
    }

    const uploadFile = async () => {
      if (!selectedFile.value) return

      isProcessing.value = true
      errorMessage.value = ''
      successMessage.value = ''
      processingTime.value = 0
      images.value = []
      annotatedImages.value = []

      // Start timer
      processingTimer.value = setInterval(() => {
        processingTime.value += 1
      }, 1000)

      try {
        // Convert file to base64
        const fileBase64 = await fileToBase64(selectedFile.value)
        
        // Upload file
        const response = await axios.post(`${config.API_URL}/upload`, {
          file: fileBase64,
          filename: selectedFile.value.name,
          userId: 'web-user'
        })

        currentJobId.value = response.data.jobId
        jobStatus.value = response.data.status
        
        // Save to history
        saveToHistory({
          jobId: response.data.jobId,
          fileName: selectedFile.value.name,
          status: response.data.status,
          createdAt: Date.now()
        })
        
        // Start checking job status
        checkJobStatus()
        
      } catch (error) {
        console.error('Error:', error)
        errorMessage.value = error.response?.data?.error || '업로드 중 오류가 발생했습니다.'
        isProcessing.value = false
        stopTimer()
      }
    }

    const fileToBase64 = (file) => {
      return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.readAsDataURL(file)
        reader.onload = () => {
          const base64 = reader.result.split(',')[1]
          resolve(base64)
        }
        reader.onerror = reject
      })
    }

    const checkJobStatus = async () => {
      if (!currentJobId.value) return

      statusCheckInterval.value = setInterval(async () => {
        try {
          const response = await axios.get(`${config.API_URL}/status/${currentJobId.value}`)
          
          jobStatus.value = response.data.status
          jobMessage.value = response.data.message
          jobProgress.value = response.data.progress || 0
          
          if (response.data.status === 'COMPLETED') {
            // Get results
            await getJobResults()
            stopStatusCheck()
            stopTimer()
            isProcessing.value = false
            isCompleted.value = true  // Mark as completed
            updateHistoryStatus(currentJobId.value, 'COMPLETED')
            // Show result URL
            successMessage.value = `처리 완료! 결과 페이지: ${window.location.origin}/#/job/${currentJobId.value}`
          } else if (response.data.status === 'FAILED') {
            errorMessage.value = response.data.message || '처리 중 오류가 발생했습니다.'
            stopStatusCheck()
            stopTimer()
            isProcessing.value = false
            updateHistoryStatus(currentJobId.value, 'FAILED')
          }
        } catch (error) {
          console.error('Status check error:', error)
        }
      }, 2000) // Check every 2 seconds
    }

    const getJobResults = async () => {
      try {
        const response = await axios.get(`${config.API_URL}/result/${currentJobId.value}`)
        
        console.log('Result response:', response.data)
        
        // Lambda returns objects with presigned URLs
        images.value = response.data.extractedImages || []
        annotatedImages.value = response.data.annotatedImages || []
        numberMappings.value = response.data.numberMappings || {}
        
        successMessage.value = `성공적으로 ${images.value.length}개의 도면을 추출했습니다. 처리 시간: ${response.data.processingTime || processingTime.value}초`
      } catch (error) {
        console.error('Error getting results:', error)
        errorMessage.value = '결과를 가져오는 중 오류가 발생했습니다.'
      }
    }

    const stopStatusCheck = () => {
      if (statusCheckInterval.value) {
        clearInterval(statusCheckInterval.value)
        statusCheckInterval.value = null
      }
    }

    const stopTimer = () => {
      if (processingTimer.value) {
        clearInterval(processingTimer.value)
        processingTimer.value = null
      }
    }

    const openModal = (image) => {
      selectedImage.value = image
      modalOpen.value = true
    }

    const closeModal = () => {
      modalOpen.value = false
      selectedImage.value = null
    }

    const saveToHistory = (job) => {
      const history = JSON.parse(localStorage.getItem('jobHistory') || '[]')
      history.unshift(job)
      // Keep only last 50 jobs
      if (history.length > 50) {
        history.pop()
      }
      localStorage.setItem('jobHistory', JSON.stringify(history))
      loadHistory()
    }

    const updateHistoryStatus = (jobId, status) => {
      const history = JSON.parse(localStorage.getItem('jobHistory') || '[]')
      const jobIndex = history.findIndex(j => j.jobId === jobId)
      if (jobIndex !== -1) {
        history[jobIndex].status = status
        localStorage.setItem('jobHistory', JSON.stringify(history))
        loadHistory()
      }
    }

    const loadHistory = async () => {
      try {
        // Load from localStorage first (for backward compatibility)
        let localHistory = JSON.parse(localStorage.getItem('jobHistory') || '[]')
        
        // Clean up invalid timestamp data in localStorage
        localHistory = localHistory.map(job => {
          if (job.createdAt && job.createdAt < 10000000000) {
            // If timestamp is in seconds but stored as milliseconds incorrectly
            // Update it to current timestamp for old invalid entries
            return {
              ...job,
              createdAt: Date.now()
            }
          }
          return job
        }).filter(job => {
          // Remove entries with invalid dates (1970 era)
          const date = new Date(job.createdAt)
          return date.getFullYear() > 2020 // Only keep entries from after 2020
        })
        
        // Update localStorage with cleaned data
        if (localHistory.length !== JSON.parse(localStorage.getItem('jobHistory') || '[]').length) {
          localStorage.setItem('jobHistory', JSON.stringify(localHistory))
        }
        
        // Try to load from server
        const response = await axios.get(`${config.API_URL}/history?limit=50`)
        if (response.data && response.data.history) {
          // Normalize server data to match local data structure
          const serverHistory = response.data.history.map(job => ({
            ...job,
            fileName: job.fileName || job.filename // Ensure fileName field exists
          }))
          
          // Merge server history with local history (remove duplicates)
          const mergedHistory = [...serverHistory]
          
          // Add local items that don't exist on server
          localHistory.forEach(localJob => {
            if (!mergedHistory.find(j => j.jobId === localJob.jobId)) {
              mergedHistory.push(localJob)
            }
          })
          
          jobHistory.value = mergedHistory.slice(0, 50) // Keep only latest 50
        } else {
          jobHistory.value = localHistory
        }
      } catch (error) {
        console.error('Failed to load history from server:', error)
        // Fallback to localStorage with cleanup
        let localHistory = JSON.parse(localStorage.getItem('jobHistory') || '[]')
        localHistory = localHistory.filter(job => {
          const date = new Date(job.createdAt)
          return date.getFullYear() > 2020
        })
        jobHistory.value = localHistory
      }
    }

    const formatDate = (timestamp) => {
      if (!timestamp) return '-'
      
      // Check if timestamp is in seconds (Unix timestamp) or milliseconds (JavaScript timestamp)
      let dateValue = timestamp
      if (timestamp < 10000000000) {
        // If timestamp is less than 10 billion, it's probably in seconds, convert to milliseconds
        dateValue = timestamp * 1000
      }
      
      const date = new Date(dateValue)
      // Check if date is valid
      if (isNaN(date.getTime())) {
        return '잘못된 날짜'
      }
      
      return date.toLocaleString('ko-KR')
    }

    const getStatusText = (status) => {
      const statusMap = {
        'QUEUED': '대기 중',
        'PROCESSING': '처리 중',
        'COMPLETED': '완료',
        'FAILED': '실패'
      }
      return statusMap[status] || status
    }

    const getJobFilename = (job) => {
      // Try multiple possible filename fields
      if (job.fileName) return job.fileName
      if (job.filename) return job.filename
      
      // If no filename, try to extract from s3Key
      if (job.s3Key) {
        const keyParts = job.s3Key.split('/')
        const filename = keyParts[keyParts.length - 1]
        if (filename && filename !== 'undefined') {
          return filename
        }
      }
      
      // Last resort: use jobId with PDF extension
      if (job.jobId) {
        return `${job.jobId.substring(0, 8)}.pdf`
      }
      
      return '파일명 없음'
    }

    const startNewTask = () => {
      // Reload the page to start fresh
      window.location.href = '/'
    }

    const trackProcessingJob = (job) => {
      // Hide history modal
      showHistory.value = false
      
      // Set current job ID
      currentJobId.value = job.jobId
      
      // Update job status info
      jobStatus.value = job.status
      jobMessage.value = job.message || ''
      jobProgress.value = job.progress || 0
      
      // Update progress message
      if (job.message) {
        progressMessage.value = job.message
      }
      if (job.progress) {
        progress.value = job.progress
      }
      
      // Show processing status
      isProcessing.value = true
      
      // Calculate elapsed time
      const startTime = job.createdAt * (job.createdAt < 10000000000 ? 1000 : 1)
      processingTime.value = Math.floor((Date.now() - startTime) / 1000)
      
      // Start timer for elapsed time
      stopTimer() // Stop any existing timer first
      processingTimer.value = setInterval(() => {
        processingTime.value += 1
      }, 1000)
      
      // Start status check for this job
      startStatusCheck()
      
      // Set file info if available
      if (job.fileName || job.filename) {
        uploadedFile.value = { name: getJobFilename(job) }
      }
    }

    // Load history on mount
    onMounted(() => {
      loadHistory()
    })

    // Cleanup on unmount
    onUnmounted(() => {
      stopStatusCheck()
      stopTimer()
    })

    return {
      selectedFile,
      uploadedFile,
      isDragging,
      isProcessing,
      isCompleted,
      images,
      annotatedImages,
      errorMessage,
      successMessage,
      numberMappings,
      modalOpen,
      selectedImage,
      processingTime,
      progressMessage,
      progress,
      currentJobId,
      jobStatus,
      jobStatusText,
      jobMessage,
      jobProgress,
      handleFileSelect,
      handleDrop,
      removeFile,
      formatFileSize,
      uploadFile,
      openModal,
      closeModal,
      showHistory,
      jobHistory,
      formatDate,
      getStatusText,
      getJobFilename,
      trackProcessingJob,
      startNewTask
    }
  }
}
</script>

<style>
.job-status {
  margin-top: 20px;
}

.status-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 14px;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.status-badge.QUEUED {
  background: #fef3c7;
  color: #92400e;
}

.status-badge.PROCESSING {
  background: #dbeafe;
  color: #1e40af;
}

.status-badge.COMPLETED {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.FAILED {
  background: #fee2e2;
  color: #991b1b;
}

.status-badge.clickable {
  cursor: pointer;
  transition: all 0.2s ease;
}

.status-badge.clickable:hover {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.status-message {
  color: #64748b;
  font-size: 14px;
  margin-bottom: 12px;
}

.progress-bar {
  height: 8px;
  background: #f1f5f9;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.3s ease;
}

.annotated-section {
  margin-top: 40px;
}

.annotated-section h3 {
  font-size: 20px;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 20px;
}

/* History Button */
.header {
  position: relative;
}

.history-button {
  position: absolute;
  right: 20px;
  top: 20px;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 2px solid white;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.2s;
  backdrop-filter: blur(10px);
}

.history-button:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
}

/* Result Link */
.result-link {
  margin-top: 15px;
  text-align: center;
}

.btn-link {
  display: inline-block;
  padding: 8px 16px;
  background: #667eea;
  color: white;
  text-decoration: none;
  border-radius: 6px;
  font-size: 14px;
  transition: background 0.2s;
}

.btn-link:hover {
  background: #5a67d8;
}

/* Modal Overlay */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-dialog {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 20px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.close-button {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: #94a3b8;
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.empty-history {
  text-align: center;
  padding: 40px;
  color: #94a3b8;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
  transition: background 0.2s;
}

.history-item:hover {
  background: #f1f5f9;
}

.history-info {
  flex: 1;
}

.history-filename {
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 4px;
}

.history-date {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}

.history-status .status-badge {
  font-size: 11px;
}

.view-button {
  padding: 6px 14px;
  background: #667eea;
  color: white;
  text-decoration: none;
  border-radius: 6px;
  font-size: 13px;
  transition: background 0.2s;
  border: none;
  cursor: pointer;
}

.view-button:hover {
  background: #5a67d8;
}

.view-button.processing-button {
  background: #17a2b8;
}

.view-button.processing-button:hover {
  background: #138496;
}

/* Completed Area Styles */
.completed-area {
  text-align: center;
  padding: 60px 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  border-radius: 12px;
  border: 2px dashed #28a745;
}

.completion-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.completion-text {
  font-size: 24px;
  font-weight: 600;
  color: #28a745;
  margin-bottom: 10px;
}

.completion-file {
  font-size: 16px;
  color: #6c757d;
}

.btn-success {
  background: #28a745;
  color: white;
  border: none;
  padding: 12px 32px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-success:hover {
  background: #218838;
  transform: translateY(-2px);
}

.header {
  position: relative;
}

/* Mappings Section */
.mappings-section {
  margin-top: 30px;
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.mappings-section h3 {
  font-size: 20px;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 15px;
}

.mappings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 15px;
}

.mapping-item {
  display: flex;
  align-items: center;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 4px;
}

.mapping-key {
  font-weight: bold;
  color: #007bff;
}

.mapping-arrow {
  margin: 0 10px;
  color: #999;
}

.mapping-value {
  flex: 1;
}
</style>