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
    </div>

    <!-- Upload Section -->
    <div class="upload-section">
      <div 
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
          />
          <div class="upload-icon">📄</div>
          <div class="upload-text">PDF 파일을 선택하거나 드래그하세요</div>
          <div class="upload-hint">특허 문서 PDF 파일만 지원됩니다</div>
        </label>
      </div>

      <!-- File Info -->
      <div v-if="selectedFile" class="file-info">
        <div>
          <div class="file-name">{{ selectedFile.name }}</div>
          <div class="file-size">{{ formatFileSize(selectedFile.size) }}</div>
        </div>
        <button class="btn btn-danger" @click="removeFile">삭제</button>
      </div>

      <!-- Action Buttons -->
      <div class="action-buttons">
        <button 
          class="btn btn-primary"
          :disabled="!selectedFile || isProcessing"
          @click="uploadFile"
        >
          <span v-if="isProcessing" class="loading"></span>
          <span v-else>도면 추출 시작</span>
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
    </div>
  </div>
</template>

<script>
import { ref, computed, onUnmounted } from 'vue'
import axios from 'axios'
import ImageModal from './ImageModal.vue'
import config from './config'

export default {
  name: 'App',
  components: {
    ImageModal
  },
  setup() {
    const selectedFile = ref(null)
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
    
    // Serverless specific
    const currentJobId = ref(null)
    const jobStatus = ref('')
    const jobMessage = ref('')
    const jobProgress = ref(0)
    const statusCheckInterval = ref(null)

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
          } else if (response.data.status === 'FAILED') {
            errorMessage.value = response.data.message || '처리 중 오류가 발생했습니다.'
            stopStatusCheck()
            stopTimer()
            isProcessing.value = false
          }
        } catch (error) {
          console.error('Status check error:', error)
        }
      }, 2000) // Check every 2 seconds
    }

    const getJobResults = async () => {
      try {
        const response = await axios.get(`${config.API_URL}/result/${currentJobId.value}`)
        
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

    // Cleanup on unmount
    onUnmounted(() => {
      stopStatusCheck()
      stopTimer()
    })

    return {
      selectedFile,
      isDragging,
      isProcessing,
      images,
      annotatedImages,
      errorMessage,
      successMessage,
      numberMappings,
      modalOpen,
      selectedImage,
      processingTime,
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
      closeModal
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
</style>