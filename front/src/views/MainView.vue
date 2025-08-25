<template>
  <div class="container">
    <!-- Image Modal -->
    <ImageModal 
      v-if="selectedImage"
      :isOpen="modalOpen"
      :image="selectedImage"
      @close="closeModal"
    />
    <!-- Header -->
    <div class="header">
      <button @click="goHome" class="home-button" title="홈으로">🏠</button>
      <h1>🔬 Patent Drawing Helper</h1>
      <p>특허 도면 자동 처리 시스템</p>
      <button @click="showHistory = true" class="history-button">📋 작업 이력</button>
    </div>

    <!-- Upload Section -->
    <div class="upload-section">
      <div 
        v-if="!isCompleted && !showMappings && !isReworkMode"
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
      <div v-else-if="isCompleted" class="completed-area">
        <div class="completion-icon">✅</div>
        <div class="completion-text">도면 추출이 완료되었습니다!</div>
        <div class="completion-file">{{ selectedFile?.name || uploadedFile?.name }}</div>
      </div>

      <!-- File Info for analysis/rework mode -->
      <div v-else-if="(showMappings || isReworkMode) && selectedFile" class="file-info-compact">
        <div class="file-name">📄 {{ selectedFile.name }}</div>
      </div>

      <!-- File Info with delete button (only when not in mapping/rework mode) -->
      <div v-if="selectedFile && !isCompleted && !showMappings && !isReworkMode" class="file-info">
        <div>
          <div class="file-name">{{ selectedFile.name }}</div>
          <div class="file-size">{{ formatFileSize(selectedFile.size) }}</div>
        </div>
        <button class="btn btn-danger" @click="removeFile" :disabled="isProcessing">삭제</button>
      </div>

      <!-- Action Buttons -->
      <div class="action-buttons">
        <button 
          v-if="!isCompleted && !showMappings"
          class="btn btn-primary"
          :disabled="!selectedFile || isProcessing"
          @click="extractMappings"
        >
          <span v-if="isProcessing" class="loading"></span>
          <span v-else>분석</span>
        </button>
        <button 
          v-if="showMappings && !isCompleted"
          class="btn btn-primary"
          :disabled="isProcessing"
          @click="processWithMappings"
        >
          <span v-if="isProcessing" class="loading"></span>
          <span v-else-if="isReworkMode">작업 실행</span>
          <span v-else>작업 시작</span>
        </button>
        <button 
          v-else-if="annotatedImages.length > 0"
          class="btn btn-secondary"
          @click="reworkTask"
        >
          재작업
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
          <div v-if="jobStatus === 'COMPLETED' && isProcessingOCR" class="result-link">
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
        <button v-if="annotatedPdfUrl" @click="downloadPdf" class="download-pdf-btn">
          📄 어노테이션된 PDF 다운로드
        </button>
      </div>
    </div>

    <!-- Mapping Section -->
    <div v-if="showMappings" class="mapping-section">
      <h2>매핑 정보 편집</h2>
      
      <!-- Show previous results in rework mode -->
      <div v-if="isReworkMode && (images.length > 0 || annotatedImages.length > 0)" class="previous-results">
        <div class="results-tabs">
          <button 
            @click="selectedResultTab = 'original'" 
            :class="['tab', selectedResultTab === 'original' ? 'active' : '']"
          >
            추출된 도면 ({{ images.length }})
          </button>
          <button 
            @click="selectedResultTab = 'annotated'" 
            :class="['tab', selectedResultTab === 'annotated' ? 'active' : '']"
            v-if="annotatedImages.length > 0"
          >
            어노테이션 도면 ({{ annotatedImages.length }})
          </button>
        </div>
        
        <!-- Original images tab -->
        <div v-if="selectedResultTab === 'original'" class="image-grid">
          <div v-for="(image, index) in images" :key="index" class="image-card">
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
        
        <!-- Annotated images tab -->
        <div v-if="selectedResultTab === 'annotated' && annotatedImages.length > 0" class="image-grid">
          <div v-for="(image, index) in annotatedImages" :key="'annotated-' + index" class="image-card">
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
                <span class="badge badge-annotated">어노테이션</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Mapping Table - 2 Column Layout -->
      <div class="mapping-table-container">
        <div class="mapping-table two-column">
          <table>
            <thead>
              <tr>
                <th width="40">선택</th>
                <th width="60">번호</th>
                <th>명칭</th>
                <th width="30"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(mapping, index) in editableMappingsFirstHalf" :key="index">
                <td>
                  <input 
                    type="checkbox" 
                    v-model="mapping.selected"
                    :disabled="!mapping.label || mapping.label.trim() === ''"
                  />
                </td>
                <td>{{ mapping.number }}</td>
                <td>
                  <input 
                    type="text" 
                    v-model="mapping.label"
                    @input="() => { if(mapping.label && mapping.label.trim()) mapping.selected = true; }"
                    placeholder="명칭 입력"
                  />
                </td>
                <td>
                  <button @click="removeMapping(editableMappings.indexOf(mapping))" class="btn btn-sm btn-danger btn-icon" title="삭제">×</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="mapping-table two-column">
          <table>
            <thead>
              <tr>
                <th width="40">선택</th>
                <th width="60">번호</th>
                <th>명칭</th>
                <th width="30"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(mapping, index) in editableMappingsSecondHalf" :key="index">
                <td>
                  <input 
                    type="checkbox" 
                    v-model="mapping.selected"
                    :disabled="!mapping.label || mapping.label.trim() === ''"
                  />
                </td>
                <td>{{ mapping.number }}</td>
                <td>
                  <input 
                    type="text" 
                    v-model="mapping.label"
                    @input="() => { if(mapping.label && mapping.label.trim()) mapping.selected = true; }"
                    placeholder="명칭 입력"
                  />
                </td>
                <td>
                  <button @click="removeMapping(editableMappings.indexOf(mapping))" class="btn btn-sm btn-danger btn-icon" title="삭제">×</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- Add New Mapping -->
      <div class="add-mapping">
        <div class="add-mapping-inline">
          <h3>새 매핑 추가</h3>
          <div class="add-mapping-form">
            <input 
              type="text" 
              v-model="newMapping.number" 
              placeholder="번호 (예: 100, 156a)"
              class="input-number"
            />
            <input 
              type="text" 
              v-model="newMapping.label" 
              placeholder="명칭 (예: 전원 버튼)"
              class="input-label"
            />
            <button 
              @click="addMapping" 
              :disabled="!newMapping.number || !newMapping.label"
              class="btn btn-success"
            >
              추가
            </button>
          </div>
        </div>
      </div>
      
      <!-- Extracted Images Preview -->
      <div class="images-preview" v-if="extractedImages.length > 0">
        <h3>추출된 도면</h3>
        <div class="image-grid">
          <div v-for="(img, index) in extractedImages" :key="img.file_path || index" class="image-item">
            <img 
              :src="getImageUrl(img)" 
              :alt="img.filename || `도면 ${index + 1}`"
              @click="openModal(getImageUrl(img))"
            />
            <div class="image-caption">{{ img.filename || `도면 ${index + 1}` }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Results Section - Show only when not in mapping mode -->
    <div v-if="images.length > 0 && !showMappings" class="results-section">
      <div class="results-header">
        <h2 class="results-title">추출된 도면</h2>
        <div class="results-count">총 {{ images.length }}개</div>
        <div class="pdf-download-buttons">
          <button 
            @click="generatePDF()" 
            class="btn btn-pdf"
            :disabled="isGeneratingPDF"
          >
            📝 주석 PDF 다운로드
          </button>
        </div>
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

      <!-- Annotated Images - Show only when not in mapping mode -->
      <div v-if="annotatedImages.length > 0 && !showMappings" class="annotated-section">
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
import { ref, computed, onUnmounted, onMounted, nextTick } from 'vue'
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
    const annotatedPdfUrl = ref(null)
    const errorMessage = ref('')
    const successMessage = ref('')
    const numberMappings = ref({})
    const modalOpen = ref(false)
    const selectedImage = ref(null)  // null is ok, v-if handles it
    const processingTime = ref(0)
    const processingTimer = ref(null)
    const progressMessage = ref('')
    const progress = ref(0)
    const isCompleted = ref(false)  // Track if extraction is completed
    const isGeneratingPDF = ref(false)  // Track PDF generation status
    
    // Serverless specific
    const currentJobId = ref(null)
    const jobStatus = ref('')
    const jobMessage = ref('')
    const jobProgress = ref(0)
    const statusCheckInterval = ref(null)
    const showHistory = ref(false)
    const jobHistory = ref([])

    // Mapping related states
    const showMappings = ref(false)
    const extractedImages = ref([])
    const detectedNumbers = ref([])
    const editableMappings = ref([])
    const newMapping = ref({ number: '', label: '' })
    const savedMappings = ref([])  // 재작업을 위한 매핑 정보 저장
    const isReworkMode = ref(false)  // 재작업 모드 플래그
    const selectedResultTab = ref('original')  // 재작업 모드에서 결과 탭 선택
    const isProcessingOCR = ref(false)  // OCR 처리 중인지 구분

    const jobStatusText = computed(() => {
      const statusMap = {
        'QUEUED': '대기 중',
        'PROCESSING': '처리 중',
        'COMPLETED': '완료',
        'FAILED': '실패'
      }
      return statusMap[jobStatus.value] || jobStatus.value
    })

    // Split mappings into two columns
    const editableMappingsFirstHalf = computed(() => {
      const midpoint = Math.ceil(editableMappings.value.length / 2)
      return editableMappings.value.slice(0, midpoint)
    })

    const editableMappingsSecondHalf = computed(() => {
      const midpoint = Math.ceil(editableMappings.value.length / 2)
      return editableMappings.value.slice(midpoint)
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
      uploadedFile.value = selectedFile.value  // Store uploaded file info

      // Start timer
      processingTimer.value = setInterval(() => {
        processingTime.value += 1
      }, 1000)

      try {
        // Create FormData for local server
        const formData = new FormData()
        formData.append('file', selectedFile.value)
        
        // Upload file to local server
        const response = await axios.post(`${config.API_URL}/process`, formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          },
          timeout: 300000 // 5 minutes timeout for local processing
        })

        // Local server returns results directly
        currentJobId.value = 'local-' + Date.now()
        jobStatus.value = 'COMPLETED'
        
        // Process local server response
        if (response.data.extracted_images) {
          images.value = response.data.extracted_images.map(img => {
            // extracted_images is an array of objects with file_path property
            if (typeof img === 'object' && img.file_path) {
              const filename = img.file_path.split('/').pop()
              return {
                url: `${config.API_URL}/images/${filename}`,
                key: filename
              }
            }
            // Fallback for string format
            const imgPath = typeof img === 'string' ? img : img.toString()
            const filename = imgPath.includes('/') ? imgPath.split('/').pop() : imgPath
            return {
              url: `${config.API_URL}/images/${filename}`,
              key: filename
            }
          })
        }
        
        if (response.data.annotated_images) {
          annotatedImages.value = response.data.annotated_images.map(img => {
            // Handle both string paths and filenames
            const imgPath = typeof img === 'string' ? img : String(img)
            const filename = imgPath.includes('/') ? imgPath.split('/').pop() : imgPath
            return {
              url: `${config.API_URL}/images/${filename}`,
              key: filename
            }
          })
        }
        
        numberMappings.value = response.data.number_mappings || {}
        
        // Save to history with full job data for local access
        saveToHistory({
          jobId: currentJobId.value,
          fileName: selectedFile.value.name,
          status: 'COMPLETED',
          createdAt: Date.now(),
          extractedImages: images.value,
          annotatedImages: annotatedImages.value,
          numberMappings: numberMappings.value,
          processingTime: processingTime.value
        })
        
        stopTimer()
        isProcessing.value = false
        isCompleted.value = true
        successMessage.value = `성공적으로 ${images.value.length}개의 도면을 추출했습니다. 처리 시간: ${processingTime.value}초`
        
      } catch (error) {
        console.error('Error:', error)
        errorMessage.value = error.response?.data?.detail || error.message || '업로드 중 오류가 발생했습니다.'
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
      // For AWS environment - poll for extraction status
      if (!currentJobId.value || config.isLocal) return

      statusCheckInterval.value = setInterval(async () => {
        try {
          const response = await axios.get(`${config.API_URL}/status/${currentJobId.value}`)
          
          jobStatus.value = response.data.status
          jobMessage.value = response.data.message
          jobProgress.value = response.data.progress || 0
          
          if (response.data.status === 'COMPLETED') {
            // Get extraction results
            await getJobResults()
            stopStatusCheck()
            stopTimer()
            
            // Show mappings for editing
            showMappings.value = true
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

    const checkJobStatusForOCR = async () => {
      // For AWS environment - poll for OCR processing status
      if (!currentJobId.value || config.isLocal) return

      statusCheckInterval.value = setInterval(async () => {
        try {
          const response = await axios.get(`${config.API_URL}/status/${currentJobId.value}`)
          
          jobStatus.value = response.data.status
          jobMessage.value = response.data.message
          jobProgress.value = response.data.progress || 0
          
          if (response.data.status === 'COMPLETED') {
            // Get OCR results
            await getOCRJobResults()
            stopStatusCheck()
            stopTimer()
            isProcessing.value = false
            isCompleted.value = true
            
            // Show result URL
            const baseUrl = config.isLocal ? 'http://localhost:3000' : window.location.origin
            successMessage.value = `처리 완료! 결과 페이지: ${baseUrl}/#/job/${currentJobId.value}`
            
          } else if (response.data.status === 'FAILED') {
            errorMessage.value = response.data.message || 'OCR 처리 중 오류가 발생했습니다.'
            stopStatusCheck()
            stopTimer()
            isProcessing.value = false
          }
        } catch (error) {
          console.error('OCR status check error:', error)
        }
      }, 2000) // Check every 2 seconds
    }

    const getJobResults = async () => {
      // For AWS environment - get extraction results
      if (config.isLocal) return
      
      try {
        const response = await axios.get(`${config.API_URL}/result/${currentJobId.value}`)
        
        console.log('Extraction result response:', response.data)
        console.log('Extracted images from server:', response.data.extractedImages)
        
        // Store extracted images and mappings
        extractedImages.value = response.data.extractedImages || []
        
        console.log('Stored extractedImages:', extractedImages.value)
        
        editableMappings.value = response.data.numberMappings ? 
          Object.entries(response.data.numberMappings).map(([number, label]) => ({
            number,
            label,
            selected: true
          })) : []
        
      } catch (error) {
        console.error('Error getting extraction results:', error)
        errorMessage.value = '결과를 가져오는 중 오류가 발생했습니다.'
      }
    }

    const getOCRJobResults = async () => {
      // For AWS environment - get OCR processing results
      if (config.isLocal) return
      
      try {
        const response = await axios.get(`${config.API_URL}/result/${currentJobId.value}`)
        
        console.log('OCR result response:', response.data)
        
        // Store final results
        images.value = response.data.extractedImages || []
        annotatedImages.value = response.data.annotatedImages || []
        numberMappings.value = response.data.numberMappings || {}
        
        // Store PDF URL if available
        if (response.data.annotatedPdf) {
          annotatedPdfUrl.value = `${config.API_URL}/images/${response.data.annotatedPdf}`
        }
        
        successMessage.value = `성공적으로 ${images.value.length}개의 도면을 처리했습니다. 처리 시간: ${response.data.processingTime || processingTime.value}초`
        
        // Store in job history
        saveToHistory({
          jobId: currentJobId.value,
          fileName: uploadedFile.value?.name || 'Unknown',
          status: 'COMPLETED',
          createdAt: Date.now(),
          extractedImages: images.value,
          annotatedImages: annotatedImages.value,
          numberMappings: numberMappings.value,
          processingTime: processingTime.value
        })
        
      } catch (error) {
        console.error('Error getting OCR results:', error)
        errorMessage.value = 'OCR 결과를 가져오는 중 오류가 발생했습니다.'
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

    const extractMappings = async () => {
      if (!selectedFile.value) return

      isProcessing.value = true
      errorMessage.value = ''
      successMessage.value = ''
      processingTime.value = 0

      // Start timer
      processingTimer.value = setInterval(() => {
        processingTime.value += 1
      }, 1000)

      try {
        let response
        
        if (config.isLocal) {
          // Local environment - use FormData
          const formData = new FormData()
          formData.append('file', selectedFile.value)
          
          response = await axios.post(`${config.API_URL}/extract-mappings`, formData, {
            headers: {
              'Content-Type': 'multipart/form-data'
            },
            timeout: 300000 // 5 minutes timeout
          })
        } else {
          // AWS environment - use base64
          const fileBase64 = await fileToBase64(selectedFile.value)
          
          response = await axios.post(`${config.API_URL}/extract-mappings`, {
            file: fileBase64,
            filename: selectedFile.value.name
          })
        }

        // Store uploaded file info
        uploadedFile.value = selectedFile.value

        // Process mapping response
        if (response.data) {
          if (config.isLocal) {
            // Local environment returns data directly
            extractedImages.value = response.data.extracted_images || []
            detectedNumbers.value = response.data.detected_numbers || []
            
            // Initialize editable mappings with extracted mappings
            const mappings = response.data.number_mappings || {}
            editableMappings.value = []
            
            // Add all mappings to editable list
            Object.keys(mappings).forEach(num => {
              editableMappings.value.push({
                number: num,
                label: mappings[num],
                selected: true
              })
            })
            
            showMappings.value = true
            successMessage.value = '매핑 정보를 추출했습니다. 확인 후 처리를 진행하세요.'
            
          } else {
            // AWS environment returns jobId, need to poll for status
            if (response.data.jobId) {
              currentJobId.value = response.data.jobId
              jobStatus.value = response.data.status || 'PROCESSING'
              jobMessage.value = response.data.message || '매핑 추출 중...'
              
              // Start polling for AWS job status
              await checkJobStatus()
            }
          }
        }

      } catch (error) {
        console.error('Mapping extraction error:', error)
        errorMessage.value = error.response?.data?.error || error.response?.data?.detail || '매핑 추출 중 오류가 발생했습니다.'
      } finally {
        isProcessing.value = false
        stopTimer()
      }
    }

    const processWithMappings = async () => {
      // 매핑 정보 저장 (재작업을 위해)
      savedMappings.value = [...editableMappings.value]
      
      // 재작업 모드인 경우 이전 결과 초기화
      if (isReworkMode.value) {
        // 어노테이션 이미지만 초기화 (원본 이미지는 유지)
        annotatedImages.value = []
      }
      
      isProcessing.value = true
      errorMessage.value = ''
      successMessage.value = ''
      processingTime.value = 0
      
      // Start timer to show processing
      processingTimer.value = setInterval(() => {
        processingTime.value += 1
      }, 1000)
      
      progressMessage.value = 'OCR 작업 시작 중...'
      progress.value = 10

      try {
        // Collect selected mappings
        const selectedMappings = {}
        let selectedCount = 0
        editableMappings.value.forEach(mapping => {
          if (mapping.selected && mapping.label && mapping.label.trim()) {
            selectedMappings[mapping.number] = mapping.label.trim()
            selectedCount++
          }
        })
        
        progressMessage.value = `OCR로 도면에서 숫자 인식 중... (${selectedCount}개 매핑 적용 예정)`
        progress.value = 30

        // Process with selected mappings (including OCR)
        const requestData = {
          pdf_filename: uploadedFile.value.name,
          mappings: selectedMappings
        }
        
        // Include extraction job ID if available (for AWS environment)
        if (currentJobId.value && !config.isLocal) {
          requestData.extraction_job_id = currentJobId.value
        }
        
        // Include extracted images for AWS environment
        if (extractedImages.value.length > 0 && !config.isLocal) {
          requestData.extractedImages = extractedImages.value
        }
        
        const response = await axios.post(`${config.API_URL}/process-with-mappings`, requestData, {
          timeout: 300000 // 5 minutes timeout for OCR processing
        })

        if (config.isLocal) {
          // Local environment - direct results
          if (response.data.annotated_images) {
            annotatedImages.value = response.data.annotated_images.map(img => {
              const imgPath = typeof img === 'string' ? img : img.toString()
              const filename = imgPath.includes('/') ? imgPath.split('/').pop() : imgPath
              return {
                url: `${config.API_URL}/images/${filename}`,
                key: filename
              }
            })
          }
          
          // Keep extracted images for display
          images.value = extractedImages.value.map(img => {
            if (typeof img === 'object' && img.file_path) {
              const filename = img.file_path.split('/').pop()
              return {
                url: `${config.API_URL}/images/${filename}`,
                key: filename
              }
            }
            return img
          })
          
          numberMappings.value = selectedMappings
          isCompleted.value = true
          showMappings.value = false
          stopTimer()
          progressMessage.value = ''
          progress.value = 100
          successMessage.value = `도면 처리가 완료되었습니다! (처리 시간: ${processingTime.value}초)`
          
        } else {
          // AWS environment - returns jobId, need to poll for status
          if (response.data.jobId) {
            currentJobId.value = response.data.jobId
            jobStatus.value = response.data.status || 'PROCESSING'
            jobMessage.value = response.data.message || 'OCR 처리 중...'
            
            // Start polling for AWS job status
            showMappings.value = false
            isProcessingOCR.value = true  // Mark as OCR processing
            await checkJobStatusForOCR()
          }
        }

        // Store in job history
        saveToHistory({
          jobId: config.isLocal ? 'local-' + Date.now() : currentJobId.value,
          fileName: uploadedFile.value.name,
          status: config.isLocal ? 'COMPLETED' : 'PROCESSING',
          createdAt: Date.now(),
          extractedImages: extractedImages.value,
          annotatedImages: annotatedImages.value,
          numberMappings: selectedMappings,
          processingTime: processingTime.value
        })

      } catch (error) {
        console.error('Processing error:', error)
        errorMessage.value = error.response?.data?.error || error.response?.data?.detail || '처리 중 오류가 발생했습니다.'
        stopTimer()
      } finally {
        if (config.isLocal) {
          isProcessing.value = false
        }
      }
    }

    const addMapping = () => {
      if (newMapping.value.number && newMapping.value.label) {
        // Check if number already exists
        const existingIndex = editableMappings.value.findIndex(
          m => m.number === newMapping.value.number
        )
        
        if (existingIndex >= 0) {
          // Update existing mapping
          editableMappings.value[existingIndex].label = newMapping.value.label
          editableMappings.value[existingIndex].selected = true
        } else {
          // Add new mapping
          editableMappings.value.push({
            number: newMapping.value.number,
            label: newMapping.value.label,
            selected: true
          })
        }
        
        // Clear input
        newMapping.value = { number: '', label: '' }
      }
    }

    const removeMapping = (index) => {
      editableMappings.value.splice(index, 1)
    }

    const getImageUrl = (imagePath) => {
      // Handle object with file_path property
      if (typeof imagePath === 'object' && imagePath.file_path) {
        // For S3 paths like "results/{jobId}/extracted/filename.png"
        return `${config.API_URL}/images/${imagePath.file_path}`
      }
      
      // Handle string path
      if (typeof imagePath === 'string') {
        // If it's already a full S3 path
        if (imagePath.startsWith('results/')) {
          return `${config.API_URL}/images/${imagePath}`
        }
        // For legacy paths, just get filename
        const filename = imagePath.split('/').pop()
        return `${config.API_URL}/images/${filename}`
      }
      
      return imagePath
    }

    const generatePDF = async () => {
      if (!uploadedFile.value && !selectedFile.value) {
        errorMessage.value = 'PDF 파일이 없습니다.'
        return
      }

      isGeneratingPDF.value = true
      errorMessage.value = ''

      try {
        const filename = uploadedFile.value?.name || selectedFile.value?.name
        
        // Request PDF generation (annotated only)
        const response = await axios.post(`${config.API_URL}/generate-pdf`, {
          pdf_filename: filename,
          pdf_type: 'annotated'
        })

        if (response.data.filename) {
          // Download the generated PDF
          const downloadUrl = `${config.API_URL}/download-pdf/${response.data.filename}`
          
          // Create a temporary anchor element to trigger download
          const link = document.createElement('a')
          link.href = downloadUrl
          link.download = response.data.filename
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          
          successMessage.value = '주석 PDF가 생성되었습니다.'
        }
      } catch (error) {
        console.error('PDF generation error:', error)
        errorMessage.value = error.response?.data?.detail || 'PDF 생성 중 오류가 발생했습니다.'
      } finally {
        isGeneratingPDF.value = false
      }
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
        
        // For local server, just use localStorage
        jobHistory.value = localHistory.slice(0, 50) // Keep only latest 50
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

    const goHome = () => {
      // 홈으로 이동 (페이지 새로고침)
      window.location.href = '/'
    }
    
    const startNewTask = () => {
      // Reset all states for new task
      uploadedFile.value = null
      images.value = []
      annotatedImages.value = []
      editableMappings.value = []
      savedMappings.value = []
      detectedNumbers.value = []
      extractedImages.value = []
      showMappings.value = false
      isReworkMode.value = false
      isProcessingOCR.value = false
      errorMessage.value = ''
      successMessage.value = ''
      isProcessing.value = false
      isCompleted.value = false
      processingTime.value = 0
      progressMessage.value = ''
      progress.value = 0
      currentJobId.value = null
      jobStatus.value = ''
      jobMessage.value = ''
      jobProgress.value = 0
      modalOpen.value = false
      selectedImage.value = null
      showHistory.value = false
      isGeneratingPDF.value = false
      
      // Clear timer if exists
      if (processingTimer.value) {
        clearInterval(processingTimer.value)
        processingTimer.value = null
      }
    }
    
    const reworkTask = () => {
      // 재작업: 이전 매핑 정보와 이미지를 유지하면서 분석 화면으로 돌아가기
      if (savedMappings.value.length > 0) {
        // 저장된 매핑 정보 복원
        editableMappings.value = [...savedMappings.value]
      }
      
      // 재작업 모드 설정
      isReworkMode.value = true
      showMappings.value = true
      isCompleted.value = false  // 완료 상태 초기화
      successMessage.value = ''
      errorMessage.value = ''
      
      // 스크롤을 매핑 섹션으로 이동
      nextTick(() => {
        const mappingSection = document.querySelector('.mapping-section')
        if (mappingSection) {
          mappingSection.scrollIntoView({ behavior: 'smooth' })
        }
      })
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
      checkJobStatus()
      
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
      showMappings,
      extractedImages,
      detectedNumbers,
      editableMappings,
      isProcessingOCR,
      editableMappingsFirstHalf,
      editableMappingsSecondHalf,
      newMapping,
      handleFileSelect,
      handleDrop,
      removeFile,
      formatFileSize,
      uploadFile,
      extractMappings,
      processWithMappings,
      addMapping,
      removeMapping,
      openModal,
      closeModal,
      generatePDF,
      isGeneratingPDF,
      getImageUrl,
      showHistory,
      jobHistory,
      formatDate,
      getStatusText,
      getJobFilename,
      trackProcessingJob,
      startNewTask,
      reworkTask,
      goHome,
      savedMappings,
      isReworkMode,
      selectedResultTab
    }
  }
}
</script>

<style>
.pdf-download-buttons {
  display: flex;
  gap: 10px;
  margin-left: auto;
}

.btn-pdf {
  padding: 8px 16px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  white-space: nowrap;
  transition: background 0.3s;
}

.btn-pdf:hover:not(:disabled) {
  background: #45a049;
}

.btn-pdf:disabled {
  background: #cccccc;
  cursor: not-allowed;
}

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

/* Compact file info for analysis/rework mode */
.file-info-compact {
  text-align: center;
  padding: 10px;
  margin-bottom: 10px;
  background: #f8f9fa;
  border-radius: 8px;
}

.file-info-compact .file-name {
  font-size: 14px;
  color: #4a5568;
  font-weight: 500;
}

/* Mapping Section Styles */
.mapping-section {
  margin-top: 30px;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.mapping-section h2 {
  margin-bottom: 20px;
  color: #1e293b;
}

.mapping-info {
  margin-bottom: 20px;
  padding: 15px;
  background: #f8fafc;
  border-radius: 6px;
  font-size: 14px;
  color: #64748b;
}

.mapping-table-container {
  display: flex;
  gap: 20px;
  margin-bottom: 30px;
}

.mapping-table {
  overflow-x: auto;
}

.mapping-table.two-column {
  flex: 1;
}

/* Responsive design for smaller screens */
@media (max-width: 768px) {
  .mapping-table-container {
    flex-direction: column;
    gap: 10px;
  }
}

.mapping-table table {
  width: 100%;
  border-collapse: collapse;
  background: white;
}

.mapping-table th {
  background: #f1f5f9;
  padding: 6px 10px;  /* Reduced from 12px */
  text-align: left;
  font-weight: 600;
  font-size: 13px;  /* Reduced font size */
  color: #475569;
  border-bottom: 2px solid #e2e8f0;
}

.mapping-table td {
  padding: 2px 8px;  /* Further reduced from 4px 10px */
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;  /* Reduced font size */
  vertical-align: middle;  /* Center content vertically */
}

.mapping-table input[type="checkbox"] {
  cursor: pointer;
  width: 16px;  /* Reduced from 18px */
  height: 16px;  /* Reduced from 18px */
}

.mapping-table input[type="text"] {
  width: 100%;
  padding: 3px 8px;  /* Reduced from 6px 10px */
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  font-size: 13px;  /* Reduced from 14px */
  transition: border-color 0.2s;
}

.mapping-table input[type="text"]:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.btn-sm {
  padding: 2px 6px;  /* Reduced padding */
  font-size: 10px;  /* Smaller font to fit in one line */
  line-height: 1;  /* Compact line height */
  min-height: 20px;  /* Smaller minimum height */
  white-space: nowrap;  /* Prevent text wrapping */
  display: inline-flex;  /* Use flexbox for centering */
  align-items: center;  /* Center text vertically */
  justify-content: center;  /* Center text horizontally */
}

.btn-sm.btn-icon {
  padding: 1px;  /* Minimal padding for icon */
  width: 18px;  /* Fixed width */
  height: 18px;  /* Fixed height */
  min-height: 18px;  /* Override minimum height */
  font-size: 16px;  /* Larger font for × symbol */
  font-weight: bold;  /* Bold × symbol */
  border-radius: 3px;  /* Smaller border radius */
}

.btn-sm.btn-danger {
  background: #ef4444;
  color: white;
  border: none;
  cursor: pointer;
}

.btn-sm.btn-danger:hover {
  background: #dc2626;
}

.add-mapping {
  margin-bottom: 20px;  /* Reduced from 30px */
  padding: 12px 15px;  /* Reduced from 20px */
  background: #f8fafc;
  border-radius: 6px;
}

.add-mapping-inline {
  display: flex;
  align-items: center;
  gap: 15px;
}

.add-mapping-inline h3 {
  margin: 0;
  font-size: 14px;  /* Reduced from 16px */
  color: #334155;
  white-space: nowrap;
  min-width: fit-content;
}

.add-mapping-form {
  display: flex;
  gap: 10px;
  align-items: center;
  flex: 1;
}

.add-mapping-form .input-number {
  width: 120px;  /* Reduced from 150px */
  padding: 4px 8px;  /* Reduced from 8px 12px */
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  font-size: 13px;  /* Reduced from 14px */
}

.add-mapping-form .input-label {
  width: 250px;  /* Fixed width instead of flex: 1 */
  padding: 4px 8px;  /* Reduced from 8px 12px */
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  font-size: 13px;  /* Reduced from 14px */
}

.add-mapping-form input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.images-preview {
  margin-top: 30px;
}

.images-preview h3 {
  margin-bottom: 15px;
  font-size: 18px;
  color: #334155;
}

.images-preview .image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 15px;
}

.images-preview .image-item {
  cursor: pointer;
  transition: transform 0.2s;
}

.images-preview .image-item:hover {
  transform: scale(1.05);
}

.images-preview .image-item img {
  width: 100%;
  height: 150px;
  object-fit: contain;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 5px;
}

.images-preview .image-caption {
  margin-top: 5px;
  font-size: 12px;
  color: #64748b;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Annotated section header styles */
.annotated-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.annotated-header h3 {
  margin: 0;
  font-size: 20px;
  color: #1f2937;
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.action-buttons .btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.action-buttons .btn-primary {
  background: #3b82f6;
  color: white;
}

.action-buttons .btn-primary:hover {
  background: #2563eb;
}

.action-buttons .btn-secondary {
  background: #6b7280;
  color: white;
}

.action-buttons .btn-secondary:hover {
  background: #4b5563;
}

/* Inline action buttons for top section */
.action-buttons-inline {
  display: inline-flex;
  gap: 10px;
}

.action-buttons-inline .btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.action-buttons-inline .btn-primary {
  background: #3b82f6;
  color: white;
}

.action-buttons-inline .btn-primary:hover {
  background: #2563eb;
}

.action-buttons-inline .btn-secondary {
  background: #6b7280;
  color: white;
}

.action-buttons-inline .btn-secondary:hover {
  background: #4b5563;
}

/* Previous results in rework mode */
.previous-results {
  margin-bottom: 30px;
  padding: 20px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.previous-results h3 {
  margin-bottom: 15px;
  font-size: 16px;
  color: #1f2937;
}

.results-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  border-bottom: 2px solid #e5e7eb;
}

.results-tabs .tab {
  padding: 10px 20px;
  background: none;
  border: none;
  color: #718096;
  font-weight: 600;
  cursor: pointer;
  position: relative;
  transition: color 0.3s ease;
}

.results-tabs .tab.active {
  color: #667eea;
}

.results-tabs .tab.active::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 2px;
  background: #667eea;
}

/* Home button styles - matching history button */
.home-button {
  position: absolute;
  left: 20px;
  top: 20px;
  background: rgba(255, 255, 255, 0.2);
  border: 2px solid white;
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  backdrop-filter: blur(10px);
}

.home-button:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
}
</style>