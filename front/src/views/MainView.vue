<template>
  <div class="container">
    <!-- Image Modal -->
    <ImageModal
      v-if="selectedImage"
      :isOpen="modalOpen"
      :image="selectedImage"
      :imageIndex="selectedImageIndex"
      :isAnnotated="selectedImageIsAnnotated"
      @close="closeModal"
      @save-edited="handleEditedImage"
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
          v-if="!isCompleted && !showMappings && !currentJobId"
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
          :disabled="isProcessing || isProcessingOCR"
          @click="processWithMappings"
        >
          <span v-if="isProcessing || isProcessingOCR" class="loading"></span>
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
        <span v-if="isProcessing || isProcessingOCR || currentJobId" class="processing-time">
          <template v-if="jobStatus === 'COMPLETED'">
            작업 시간: {{ processingTime }}초
          </template>
          <template v-else>
            처리 중... {{ processingTime }}초
          </template>
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
        <button v-if="annotatedPdfUrl && !isReworkMode && !isProcessingOCR" @click="downloadPdf" class="download-pdf-btn">
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
                @click="openModal(image, index, true)"
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
              @click="openModal({ url: getImageUrl(img), filename: img.filename || `도면 ${index + 1}`, key: img.file_path })"
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
        <div class="pdf-download-buttons" v-if="annotatedPdfUrl">
          <button
            v-if="hasEditedImages()"
            @click="regeneratePdf()"
            class="btn btn-regenerate"
            :disabled="isRegeneratingPdf"
          >
            <span v-if="isRegeneratingPdf" class="loading"></span>
            <span v-else>🔄 PDF 재생성 (편집 이미지 포함)</span>
          </button>
          <button
            @click="downloadPdf()"
            class="btn btn-pdf"
          >
            📄 어노테이션된 PDF 다운로드
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
                @click="openModal(image, index, true)"
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
                    {{ getStatusText(job.status, job.processType) }}
                  </span>
                  <span v-else class="status-badge" :class="job.status === 'COMPLETED' && job.processType === 'EXTRACTION' ? 'analysis-complete' : job.status">
                    {{ getStatusText(job.status, job.processType) }}
                  </span>
                  <!-- 재생성 상태에 따라 태그 표시 -->
                  <span v-if="getRegenerationStatus(job) === 'processing'"
                        class="status-badge regenerating">
                    재생성중
                  </span>
                  <span v-else-if="getRegenerationStatus(job) === 'completed'"
                        class="status-badge regenerated">
                    재생성완료
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
              <button
                v-else-if="job.status === 'COMPLETED' && job.processType === 'EXTRACTION'"
                @click="trackProcessingJob(job)"
                class="view-button analysis-complete-button"
              >
                매핑 편집
              </button>
              <router-link 
                v-else-if="job.status === 'COMPLETED' && job.processType === 'OCR'"
                :to="`/job/${job.jobId}`" 
                class="view-button completed-button"
              >
                결과 보기
              </router-link>
              <button
                v-else
                @click="trackProcessingJob(job)"
                class="view-button"
              >
                상세 보기
              </button>
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
    const regeneratedPdfUrl = ref(null)
    const isRegeneratingPdf = ref(false)
    const errorMessage = ref('')
    const successMessage = ref('')
    const numberMappings = ref({})
    const modalOpen = ref(false)
    const selectedImage = ref(null)  // null is ok, v-if handles it
    const selectedImageIndex = ref(0)
    const selectedImageIsAnnotated = ref(false)
    const editedImages = ref({})  // Store edited images by index
    const processingTime = ref(0)
    const processingTimer = ref(null)
    const progressMessage = ref('')
    const progress = ref(0)
    const isCompleted = ref(false)  // Track if extraction is completed
    const isGeneratingPDF = ref(false)  // Track PDF generation status
    
    // Serverless specific
    const currentJobId = ref(null)
    const extractionJobId = ref(null) // Store extraction job ID separately
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
            isProcessingOCR.value = false
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
            isProcessingOCR.value = false
            isCompleted.value = true
            
            // Show result URL
            const baseUrl = config.isLocal ? 'http://localhost:3000' : window.location.origin
            successMessage.value = `처리 완료! 결과 페이지: ${baseUrl}/#/job/${currentJobId.value}`
            
          } else if (response.data.status === 'FAILED') {
            errorMessage.value = response.data.message || 'OCR 처리 중 오류가 발생했습니다.'
            stopStatusCheck()
            stopTimer()
            isProcessing.value = false
            isProcessingOCR.value = false
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
        
        
        // Store final results
        images.value = response.data.extractedImages || []
        annotatedImages.value = response.data.annotatedImages || []
        numberMappings.value = response.data.numberMappings || {}
        
        // Store PDF URL if available - use CloudFront URL directly
        // But not in rework mode
        if (response.data.annotatedPdf && !isReworkMode.value) {
          // CloudFront URL for direct S3 access
          const cloudFrontUrl = 'https://d38f9rplbkj0f2.cloudfront.net'
          annotatedPdfUrl.value = `${cloudFrontUrl}/${response.data.annotatedPdf}`
        }
        
        // 재작업 모드에 따라 다른 메시지 표시
        if (isReworkMode.value) {
          successMessage.value = `재작업이 완료되었습니다! ${annotatedImages.value.length}개의 도면을 처리했습니다. 처리 시간: ${response.data.processingTime || processingTime.value}초`
          isReworkMode.value = false  // 재작업 완료 후 모드 해제
        } else {
          successMessage.value = `성공적으로 ${images.value.length}개의 도면을 처리했습니다. 처리 시간: ${response.data.processingTime || processingTime.value}초`
        }
        
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

    const openModal = (image, index = 0, isAnnotated = false) => {
      console.log('Opening modal with image:', image)
      console.log('Modal parameters:', { index, isAnnotated })
      selectedImage.value = image
      selectedImageIndex.value = index
      selectedImageIsAnnotated.value = isAnnotated
      modalOpen.value = true
    }

    const closeModal = () => {
      modalOpen.value = false
      selectedImage.value = null
      selectedImageIndex.value = 0
      selectedImageIsAnnotated.value = false
    }

    const handleEditedImage = async (data) => {
      console.log('MainView: handleEditedImage called with data:', data)

      // Store edited image data
      const { imageIndex, editedData } = data
      if (!editedData) {
        console.error('MainView: No editedData received')
        return
      }

      console.log('MainView: Storing edited image at index:', imageIndex)
      editedImages.value[imageIndex] = editedData

      // Update the annotated image if exists
      if (annotatedImages.value[imageIndex]) {
        // Use Vue's reactivity system to ensure updates are detected
        const updatedImage = { ...annotatedImages.value[imageIndex] }
        updatedImage.editedUrl = editedData
        updatedImage.url = editedData
        annotatedImages.value[imageIndex] = updatedImage

        // Force reactivity update
        annotatedImages.value = [...annotatedImages.value]
      }

      // Also update the selected image in modal if it's the same image
      if (selectedImage.value && selectedImageIndex.value === imageIndex) {
        selectedImage.value = { ...selectedImage.value, url: editedData }
      }

      // Save edited image to server
      try {
        // Get the filename from various sources
        let pdfFilename = selectedFile.value?.name || uploadedFile.value?.name

        // If not found, try to get from annotated images data
        if (!pdfFilename && annotatedImages.value.length > 0) {
          // Extract filename from image URL or key
          const firstImage = annotatedImages.value[0]

          // Try different sources for the filename
          let imageIdentifier = firstImage.filename || firstImage.key || ''

          // If we have a URL, extract the filename from it
          if (!imageIdentifier && firstImage.url) {
            const urlParts = firstImage.url.split('/')
            imageIdentifier = urlParts[urlParts.length - 1]
          }

          console.log('Image identifier:', imageIdentifier)

          // Extract base filename without page number and extension
          const match = imageIdentifier.match(/^(.+?)_page\d+/)
          if (match) {
            pdfFilename = match[1] + '.pdf'
          }
        }

        let response
        if (config.isLocal) {
          // Local environment: use existing endpoint
          const requestData = {
            imageIndex,
            editedData,
            pdfFilename: pdfFilename || 'unknown.pdf'
          }
          console.log('Sending data to local server:', {
            imageIndex,
            editedDataLength: editedData?.length,
            pdfFilename: requestData.pdfFilename
          })
          response = await axios.post('/api/v1/save-edited-image', requestData)
        } else {
          // AWS environment: use Lambda endpoint
          const sessionId = getSessionId()
          const requestData = {
            jobId: currentJobId.value,
            imageIndex,
            editedData,
            sessionId
          }
          console.log('Sending data to AWS:', {
            jobId: currentJobId.value,
            imageIndex,
            editedDataLength: editedData?.length,
            sessionId
          })
          response = await axios.post(`${config.API_URL}/save-edited-image`, requestData)
        }

        if (response.data.message) {
          successMessage.value = '이미지가 성공적으로 편집되었습니다.'
          setTimeout(() => successMessage.value = '', 3000)
        }
      } catch (error) {
        console.error('Failed to save edited image:', error)
        if (error.response) {
          console.error('Error response:', error.response.data)
          console.error('Error status:', error.response.status)
          if (error.response.data.detail) {
            console.error('Error detail:', JSON.stringify(error.response.data.detail, null, 2))
          }
        }
        errorMessage.value = '편집된 이미지 저장에 실패했습니다.'
        setTimeout(() => errorMessage.value = '', 3000)
      }
    }

    const extractMappings = async () => {
      if (!selectedFile.value) return

      isProcessing.value = true
      errorMessage.value = ''
      successMessage.value = ''
      processingTime.value = 0
      
      // Generate jobId for local environment at the start
      if (config.isLocal) {
        currentJobId.value = 'local-' + Date.now()
        console.log('Generated jobId for local environment:', currentJobId.value)
      }

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
          // AWS environment - use presigned URL
          // Step 1: Get presigned URL
          const urlResponse = await axios.post(`${config.API_URL}/get-upload-url`, {
            filename: selectedFile.value.name,
            contentType: selectedFile.value.type || 'application/pdf'
          })
          
          const { uploadUrl, jobId, s3_key } = urlResponse.data
          
          // Step 2: Upload file directly to S3
          await axios.put(uploadUrl, selectedFile.value, {
            headers: {
              'Content-Type': selectedFile.value.type || 'application/pdf'
            }
          })
          
          // Step 3: Trigger extraction
          response = await axios.post(`${config.API_URL}/extract-mappings`, {
            jobId: jobId,
            s3_key: s3_key
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
              extractionJobId.value = response.data.jobId  // Store extraction job ID
              jobStatus.value = response.data.status || 'PROCESSING'
              jobMessage.value = response.data.message || '매핑 추출 중...'
              
              // Don't set isProcessing to false here, keep it true while polling
              // Start polling for AWS job status
              await checkJobStatus()
              return // Exit here to avoid finally block
            }
          }
        }
        
        // Only set isProcessing to false if we're done (local environment)
        isProcessing.value = false
        stopTimer()

      } catch (error) {
        console.error('Mapping extraction error:', error)
        errorMessage.value = error.response?.data?.error || error.response?.data?.detail || '매핑 추출 중 오류가 발생했습니다.'
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
      
      isProcessingOCR.value = true
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
        if (extractionJobId.value && !config.isLocal) {
          requestData.extraction_job_id = extractionJobId.value
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
          
          // 로컬 환경에서는 PDF 생성을 자동으로 시도
          if (config.isLocal && annotatedImages.value.length > 0) {
            try {
              progressMessage.value = 'PDF 생성 중...'
              const pdfResponse = await axios.post(`${config.API_URL}/generate-pdf`, {
                pdf_filename: uploadedFile.value.name,
                pdf_type: 'annotated'
              })
              
              if (pdfResponse.data.filename) {
                // 로컬 환경에서는 API를 통해 다운로드 URL 생성
                annotatedPdfUrl.value = `${config.API_URL}/download-pdf/${pdfResponse.data.filename}`
                successMessage.value = `도면 처리 및 PDF 생성이 완료되었습니다! (처리 시간: ${processingTime.value}초)`
                
                // PDF URL이 생성된 후 작업 이력 업데이트
                const history = JSON.parse(localStorage.getItem('jobHistory') || '[]')
                // Use currentJobId.value which was set consistently earlier
                const jobId = currentJobId.value
                const existingIndex = history.findIndex(h => h.jobId === jobId)
                if (existingIndex >= 0) {
                  history[existingIndex].annotatedPdfUrl = annotatedPdfUrl.value
                  localStorage.setItem('jobHistory', JSON.stringify(history))
                  console.log('Updated job history with PDF URL:', annotatedPdfUrl.value, 'for jobId:', jobId)
                } else {
                  console.log('Could not find job in history with jobId:', jobId)
                }
              }
            } catch (error) {
              console.error('PDF generation error:', error)
              // PDF 생성 실패해도 처리는 완료된 것으로 표시
              successMessage.value = `도면 처리가 완료되었습니다! (처리 시간: ${processingTime.value}초) - PDF 생성 실패`
            }
          } else {
            // 재작업 모드가 아닐 때만 PDF 관련 메시지 표시
            if (!isReworkMode.value) {
              successMessage.value = `도면 처리가 완료되었습니다! (처리 시간: ${processingTime.value}초)`
            } else {
              successMessage.value = `재작업이 완료되었습니다! (처리 시간: ${processingTime.value}초)`
              isReworkMode.value = false  // 재작업 완료 후 모드 해제
            }
          }
          
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

        // Store in job history - use existing jobId
        // currentJobId.value was already set in extractMappings for local environment
        const localJobId = currentJobId.value
        
        saveToHistory({
          jobId: localJobId,
          fileName: uploadedFile.value.name,
          status: config.isLocal ? 'COMPLETED' : 'PROCESSING',
          createdAt: Date.now(),
          extractedImages: extractedImages.value,
          annotatedImages: annotatedImages.value,
          numberMappings: selectedMappings,
          processingTime: processingTime.value,
          annotatedPdfUrl: annotatedPdfUrl.value // Add PDF URL for local environment
        })

      } catch (error) {
        console.error('Processing error:', error)
        errorMessage.value = error.response?.data?.error || error.response?.data?.detail || '처리 중 오류가 발생했습니다.'
        isProcessingOCR.value = false
        stopTimer()
      } finally {
        if (config.isLocal) {
          isProcessingOCR.value = false
          stopTimer()
        }
        // For AWS, isProcessingOCR will be set to false in checkJobStatusForOCR
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
      // For local environment
      if (config.isLocal) {
        // Handle object with file_path property
        if (typeof imagePath === 'object' && imagePath.file_path) {
          // Extract just the filename from the full path
          const filename = imagePath.file_path.split('/').pop()
          return `${config.API_URL}/images/${filename}`
        }
        
        // Handle string path
        if (typeof imagePath === 'string') {
          // Extract just the filename from the full path
          const filename = imagePath.split('/').pop()
          return `${config.API_URL}/images/${filename}`
        }
      } 
      // For AWS environment
      else {
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
      // 로컬 환경: localStorage에만 저장
      if (config.isLocal) {
        const history = JSON.parse(localStorage.getItem('jobHistory') || '[]')
        
        // 중복 체크 (같은 jobId가 있으면 업데이트)
        const existingIndex = history.findIndex(h => h.jobId === job.jobId)
        if (existingIndex >= 0) {
          history[existingIndex] = job
        } else {
          history.unshift(job)
        }
        
        // Keep more history (up to 500 jobs)
        if (history.length > 500) {
          // Remove oldest entries if exceeding limit
          history.splice(500)
        }
        localStorage.setItem('jobHistory', JSON.stringify(history))
        loadHistory()
      } 
      // AWS 환경: DynamoDB에 저장됨 (Lambda가 처리)
      else {
        // AWS에서는 Lambda/ECS가 자동으로 DynamoDB에 저장
        // 여기서는 임시로 localStorage에 백업만
        const history = JSON.parse(localStorage.getItem('jobHistory') || '[]')
        const existingIndex = history.findIndex(h => h.jobId === job.jobId)
        if (existingIndex >= 0) {
          history[existingIndex] = job
        } else {
          history.unshift(job)
        }
        if (history.length > 500) {
          // Remove oldest entries if exceeding limit
          history.splice(500)
        }
        localStorage.setItem('jobHistory', JSON.stringify(history))
        // AWS 환경에서는 주기적으로 DynamoDB에서 동기화
        loadHistory()
      }
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
        // 로컬 환경: localStorage에서만 가져오기
        if (config.isLocal) {
          let localHistory = JSON.parse(localStorage.getItem('jobHistory') || '[]')
          
          // Clean up invalid timestamp data in localStorage
          localHistory = localHistory.map(job => {
            // 타임스탬프 보정
            if (job.createdAt && job.createdAt < 10000000000) {
              return {
                ...job,
                createdAt: Date.now()
              }
            }
            // 로컬 환경 필수 필드 보장
            return {
              ...job,
              status: job.status || 'COMPLETED',
              extractedImages: job.extractedImages || [],
              annotatedImages: job.annotatedImages || [],
              numberMappings: job.numberMappings || {},
              annotatedPdfUrl: job.annotatedPdfUrl || null
            }
          }).filter(job => {
            const date = new Date(job.createdAt)
            return date.getFullYear() > 2020
          })
          
          jobHistory.value = localHistory // Show all history
        } 
        // AWS 환경: DynamoDB에서 가져오기
        else {
          const response = await axios.get(`${config.API_URL}/history?limit=500`)
          jobHistory.value = response.data.history || []
          
          // DynamoDB 데이터를 localStorage에 백업 (오프라인 대비)
          localStorage.setItem('jobHistory', JSON.stringify(jobHistory.value))
        }
      } catch (error) {
        console.error('Failed to load history:', error)
        
        if (config.isLocal) {
          // 로컬 환경: localStorage에서 복구 시도
          let localHistory = JSON.parse(localStorage.getItem('jobHistory') || '[]')
          localHistory = localHistory.filter(job => {
            const date = new Date(job.createdAt)
            return date.getFullYear() > 2020
          })
          jobHistory.value = localHistory
        } else {
          // AWS 환경: localStorage 백업에서 읽기 시도
          try {
            const backupHistory = JSON.parse(localStorage.getItem('jobHistory') || '[]')
            jobHistory.value = backupHistory
            console.log('Using localStorage backup for AWS history')
          } catch {
            jobHistory.value = []  // 최후의 수단: 빈 배열
          }
        }
      }
    }

    const getRegenerationStatus = (job) => {
      // 재생성된 PDF가 없으면 null 반환
      if (!job.regeneratedPdfs || job.regeneratedPdfs.length === 0) {
        return null
      }

      // 재생성된 PDF들의 상태 확인
      const hasProcessing = job.regeneratedPdfs.some(pdf =>
        pdf.status === 'PROCESSING' || !pdf.status
      )
      const hasCompleted = job.regeneratedPdfs.some(pdf =>
        pdf.status === 'COMPLETED'
      )

      // 처리 중인 것이 있으면 'processing', 완료된 것만 있으면 'completed'
      if (hasProcessing) {
        return 'processing'
      } else if (hasCompleted) {
        return 'completed'
      }

      return null
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

    const getStatusText = (status, processType) => {
      // processType이 있으면 더 구체적인 상태 표시
      if (status === 'PROCESSING' && processType) {
        if (processType === 'EXTRACTION') {
          return '매핑 추출 중'
        } else if (processType === 'OCR') {
          return 'OCR 처리 중'
        }
      }
      
      // EXTRACTION이 완료되었지만 OCR은 안한 경우
      if (status === 'COMPLETED' && processType === 'EXTRACTION') {
        return '분석 완료'
      }
      
      const statusMap = {
        'QUEUED': '대기 중',
        'PROCESSING': '처리 중',
        'COMPLETED': '완료',
        'FAILED': '실패'
      }
      return statusMap[status] || status
    }

    const getJobFilename = (job) => {
      // Try multiple possible filename fields (통일된 순서)
      if (job.filename) return job.filename
      if (job.pdf_filename) return job.pdf_filename  // OCR 작업의 경우
      if (job.fileName) return job.fileName  // 레거시 호환
      
      // If no filename, try to extract from s3Key or s3_key
      const s3Key = job.s3Key || job.s3_key
      if (s3Key) {
        const keyParts = s3Key.split('/')
        const filename = keyParts[keyParts.length - 1]
        if (filename && filename !== 'undefined') {
          return filename
        }
      }
      
      // Last resort: use jobId with prefix based on processType
      if (job.jobId) {
        const prefix = job.processType === 'OCR' ? 'OCR_' : 'Extract_'
        return `${prefix}${job.jobId.substring(0, 8)}.pdf`
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
      selectedImageIndex.value = 0
      selectedImageIsAnnotated.value = false
      editedImages.value = {}
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

    const getSessionId = () => {
      // Get or create session ID for AWS environment
      let sessionId = localStorage.getItem('editSessionId')
      if (!sessionId) {
        sessionId = 'session-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9)
        localStorage.setItem('editSessionId', sessionId)
      }
      return sessionId
    }

    const hasEditedImages = () => {
      return Object.keys(editedImages.value).length > 0
    }

    const regeneratePdfForce = async () => {
      // Force regenerate PDF (AWS only)
      if (config.isLocal) return

      try {
        const sessionId = getSessionId()

        const response = await axios.post(`${config.API_URL}/regenerate-pdf`, {
          jobId: currentJobId.value,
          editedImages: editedImages.value,
          sessionId,
          forceRegenerate: true
        })

        if (response.data.action === 'regeneration_started') {
          successMessage.value = 'PDF 재생성이 시작되었습니다. 완료되면 작업 이력에서 다운로드할 수 있습니다.'
          currentJobId.value = response.data.regenerationJobId
          // monitorJobProgress 함수가 있다면 호출
          if (typeof monitorJobProgress === 'function') {
            monitorJobProgress(response.data.regenerationJobId)
          }
        }
      } catch (error) {
        console.error('Failed to force regenerate PDF:', error)
        errorMessage.value = 'PDF 재생성에 실패했습니다.'
      }
    }

    const regeneratePdf = async () => {
      isRegeneratingPdf.value = true
      errorMessage.value = ''

      try {
        // Get PDF filename
        let pdfFilename = selectedFile.value?.name || uploadedFile.value?.name

        if (!pdfFilename && annotatedImages.value.length > 0) {
          const firstImage = annotatedImages.value[0]
          let imageIdentifier = firstImage.filename || firstImage.key || ''
          if (!imageIdentifier && firstImage.url) {
            const urlParts = firstImage.url.split('/')
            imageIdentifier = urlParts[urlParts.length - 1]
          }
          const match = imageIdentifier.match(/^(.+?)_page\d+/)
          if (match) {
            pdfFilename = match[1] + '.pdf'
          }
        }

        console.log('Regenerating PDF with edited images...')

        if (config.isLocal) {
          // Local environment: use existing endpoint
          const response = await axios.post(`${config.API_URL}/regenerate-pdf`, {
            pdf_filename: pdfFilename || 'unknown.pdf',
            edited_images: editedImages.value,
            use_edited: true
          })

          if (response.data.filename) {
            regeneratedPdfUrl.value = `${config.API_URL}/download-pdf/${response.data.filename}`
            successMessage.value = 'PDF가 편집된 이미지로 재생성되었습니다!'

            // Automatically download the regenerated PDF
            const downloadResponse = await fetch(regeneratedPdfUrl.value)
            const blob = await downloadResponse.blob()
            const url = window.URL.createObjectURL(blob)

            const link = document.createElement('a')
            link.href = url
            link.download = response.data.filename
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)

            setTimeout(() => window.URL.revokeObjectURL(url), 100)
          }
        } else {
          // AWS environment: use Lambda endpoint with session management
          const sessionId = getSessionId()

          const response = await axios.post(`${config.API_URL}/regenerate-pdf`, {
            jobId: currentJobId.value,
            editedImages: editedImages.value,
            sessionId,
            forceRegenerate: false
          })

          if (response.data.action === 'existing_pdf_found') {
            // Found existing regenerated PDF for this session
            const shouldDownload = confirm(
              `이미 이 세션에서 편집된 PDF가 있습니다 (편집 수: ${response.data.editCount}개).\n기존 PDF를 다운로드하시겠습니까?\n\n취소하면 새로 재생성합니다.`
            )

            if (shouldDownload) {
              // Download existing PDF
              const link = document.createElement('a')
              link.href = response.data.pdfUrl
              link.download = response.data.filename
              link.target = '_blank'
              document.body.appendChild(link)
              link.click()
              document.body.removeChild(link)

              successMessage.value = '기존 편집된 PDF를 다운로드했습니다.'
            } else {
              // Force regenerate new PDF
              await regeneratePdfForce()
              return
            }
          } else if (response.data.action === 'regeneration_started') {
            // New regeneration started
            successMessage.value = 'PDF 재생성이 시작되었습니다. 완료되면 작업 이력에서 다운로드할 수 있습니다.'

            // Start monitoring the regeneration job
            currentJobId.value = response.data.regenerationJobId
            // monitorJobProgress 함수가 있다면 호출
            if (typeof monitorJobProgress === 'function') {
              monitorJobProgress(response.data.regenerationJobId)
            }
          }
        }

      } catch (error) {
        console.error('Failed to regenerate PDF:', error)
        errorMessage.value = 'PDF 재생성에 실패했습니다.'
      } finally {
        isRegeneratingPdf.value = false
      }
    }

    const downloadPdf = async () => {
      if (!annotatedPdfUrl.value) {
        errorMessage.value = 'PDF 파일을 찾을 수 없습니다.'
        return
      }
      
      try {
        // For local environment, use fetch to download the file
        if (config.isLocal) {
          const response = await fetch(annotatedPdfUrl.value)
          const blob = await response.blob()
          const url = window.URL.createObjectURL(blob)
          
          const link = document.createElement('a')
          link.href = url
          
          // Extract filename from URL or use default
          const urlParts = annotatedPdfUrl.value.split('/')
          const filename = urlParts[urlParts.length - 1] || 'annotated.pdf'
          link.download = filename
          
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          
          // Clean up the object URL
          window.URL.revokeObjectURL(url)
        } else {
          // Direct download from CloudFront/S3 for AWS environment
          const link = document.createElement('a')
          link.href = annotatedPdfUrl.value
          
          // Extract filename from URL or use default
          const urlParts = annotatedPdfUrl.value.split('/')
          const filename = urlParts[urlParts.length - 1] || 'annotated.pdf'
          link.download = filename
          link.target = '_blank'
          
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
        }
        
        successMessage.value = 'PDF 다운로드가 시작되었습니다.'
      } catch (error) {
        console.error('PDF download failed:', error)
        errorMessage.value = 'PDF 다운로드에 실패했습니다. 다시 시도해주세요.'
      }
    }

    const trackProcessingJob = (job) => {
      // Hide history modal
      showHistory.value = false
      
      // Set current job ID
      currentJobId.value = job.jobId
      
      // For local environment with completed jobs, show results directly
      if (config.isLocal && job.status === 'COMPLETED') {
        // Restore completed job data
        if (job.extractedImages) {
          extractedImages.value = job.extractedImages
          // Convert extracted images to URL format for display
          images.value = job.extractedImages.map(img => {
            if (typeof img === 'object' && img.file_path) {
              const filename = img.file_path.split('/').pop()
              return {
                url: `${config.API_URL}/images/${filename}`,
                key: filename,
                ...img
              }
            } else if (typeof img === 'string') {
              const filename = img.split('/').pop()
              return {
                url: `${config.API_URL}/images/${filename}`,
                key: filename
              }
            }
            return img
          })
        }
        if (job.annotatedImages) {
          // Convert annotated images to URL format for display
          annotatedImages.value = job.annotatedImages.map(img => {
            if (typeof img === 'object' && img.file_path) {
              const filename = img.file_path.split('/').pop()
              return {
                url: `${config.API_URL}/images/${filename}`,
                key: filename,
                ...img
              }
            } else if (typeof img === 'string') {
              const filename = img.split('/').pop()
              return {
                url: `${config.API_URL}/images/${filename}`,
                key: filename
              }
            }
            return img
          })
        }
        if (job.numberMappings) {
          numberMappings.value = job.numberMappings
        }
        if (job.annotatedPdfUrl) {
          annotatedPdfUrl.value = job.annotatedPdfUrl
          console.log('Restored annotatedPdfUrl:', annotatedPdfUrl.value)
        } else {
          console.log('No annotatedPdfUrl in job history')
        }
        
        // Set completion status
        isCompleted.value = true
        isProcessing.value = false
        isProcessingOCR.value = false
        showMappings.value = false
        isReworkMode.value = false  // Ensure rework mode is off
        
        // Show success message
        if (job.processingTime) {
          processingTime.value = job.processingTime
          successMessage.value = `작업이 완료되었습니다! (처리 시간: ${job.processingTime}초)`
        } else {
          successMessage.value = '작업이 완료되었습니다!'
        }
        
        return // Exit early for completed local jobs
      }
      
      // For AWS environment with completed jobs
      if (!config.isLocal && job.status === 'COMPLETED') {
        // AWS 환경: DynamoDB에서 가져온 완료된 작업 데이터 복원
        // JobResultView와 동일한 방식으로 처리
        if (job.extractedImages) {
          extractedImages.value = job.extractedImages
          images.value = job.extractedImages
        }
        if (job.annotatedImages) {
          annotatedImages.value = job.annotatedImages
        }
        if (job.numberMappings) {
          numberMappings.value = job.numberMappings
        }
        
        // AWS 환경에서는 별도 페이지로 이동
        router.push(`/job/${job.jobId}`)
        return
      }
      
      // For processing jobs (both local and AWS), continue with tracking
      // If this is an extraction job (has extractedImages), store as extraction job
      if (job.extractedImages) {
        extractionJobId.value = job.jobId
      }
      
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
      selectedImageIndex,
      selectedImageIsAnnotated,
      editedImages,
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
      handleEditedImage,
      generatePDF,
      isGeneratingPDF,
      getImageUrl,
      showHistory,
      jobHistory,
      formatDate,
      getStatusText,
      getJobFilename,
      getRegenerationStatus,
      trackProcessingJob,
      startNewTask,
      reworkTask,
      goHome,
      downloadPdf,
      annotatedPdfUrl,
      savedMappings,
      isReworkMode,
      selectedResultTab,
      hasEditedImages,
      regeneratePdf,
      isRegeneratingPdf,
      regeneratedPdfUrl
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

.btn-regenerate {
  padding: 8px 16px;
  background: linear-gradient(135deg, #f59e0b 0%, #f97316 100%);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  white-space: nowrap;
  transition: all 0.3s;
  margin-right: 10px;
}

.btn-regenerate:hover:not(:disabled) {
  background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
  transform: translateY(-1px);
}

.btn-regenerate:disabled {
  background: #cccccc;
  cursor: not-allowed;
  opacity: 0.6;
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

.status-badge.analysis-complete {
  background: #e0f2fe;
  color: #0369a1;
  font-weight: 600;
}

.status-badge.FAILED {
  background: #fee2e2;
  color: #991b1b;
}

.status-badge.regenerating {
  background: #dbeafe;
  color: #1e40af;
  margin-left: 8px;
  animation: pulse 1.5s infinite;
}

.status-badge.regenerated {
  background: #d1fae5;
  color: #065f46;
  margin-left: 8px;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
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

.view-button.analysis-complete-button {
  background: #0369a1;
}

.view-button.analysis-complete-button:hover {
  background: #075985;
}

.view-button.completed-button {
  background: #28a745;
}

.view-button.completed-button:hover {
  background: #218838;
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