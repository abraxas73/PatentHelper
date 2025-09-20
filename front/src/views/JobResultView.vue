<template>
  <div class="job-result-container">
    <!-- Image Modal -->
    <ImageModal
      :isOpen="modalOpen"
      :image="selectedImage"
      :imageIndex="selectedImageIndex"
      :isAnnotated="selectedImageIsAnnotated"
      @close="closeModal"
      @save-edited="handleEditedImage"
    />
    
    <div class="header">
      <button @click="goBack" class="back-button">← 메인</button>
      <h1>작업 결과 - {{ jobId }}</h1>
    </div>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <p>작업 정보를 불러오는 중...</p>
    </div>

    <div v-else-if="error" class="error">
      <p>{{ error }}</p>
      <button @click="loadJobResult">다시 시도</button>
    </div>

    <div v-else-if="jobData" class="job-content">
      <!-- 작업 상태 정보 -->
      <div class="status-card">
        <h2>작업 상태</h2>
        <div class="status-info">
          <div class="status-item">
            <span class="label">상태:</span>
            <span :class="['status-badge', getStatusClass(jobData.status)]">
              {{ getStatusText(jobData.status) }}
            </span>
          </div>
          <div class="status-item">
            <span class="label">파일명:</span>
            <span>{{ getJobFilename(jobData) }}</span>
          </div>
          <div class="status-item">
            <span class="label">요청 시간:</span>
            <span>{{ formatDate(jobData.createdAt || jobData.created_at) }}</span>
          </div>
          <div v-if="jobData.completedAt || jobData.completed_at" class="status-item">
            <span class="label">완료 시간:</span>
            <span>{{ formatDate(jobData.completedAt || jobData.completed_at) }}</span>
          </div>
          <div v-if="jobData.processingTime" class="status-item">
            <span class="label">처리 시간:</span>
            <span>{{ jobData.processingTime }}초</span>
          </div>
        </div>
      </div>

      <!-- 진행 상황 -->
      <div v-if="jobData.status === 'PROCESSING'" class="progress-card">
        <h3>진행 상황</h3>
        <div class="progress-bar">
          <div class="progress-fill" :style="{width: `${jobData.progress || 0}%`}"></div>
        </div>
        <p>{{ jobData.message }}</p>
      </div>

      <!-- 재생성된 PDF 섹션 (moved to top) -->
      <div v-if="jobData.regeneratedPdfs && jobData.regeneratedPdfs.length > 0" class="regenerated-pdfs-section">
        <h3>재생성된 PDF</h3>
        <div class="pdf-list">
          <div v-for="pdf in jobData.regeneratedPdfs" :key="pdf.jobId" class="pdf-item">
            <div class="pdf-info">
              <span class="pdf-filename">{{ pdf.filename }}</span>
              <span class="pdf-date">{{ formatDate(pdf.timestamp) }}</span>
              <span class="edit-count">편집 {{ pdf.editCount }}개</span>
            </div>
            <button @click="downloadRegeneratedPdf(pdf)" class="btn-download">
              📥 다운로드
            </button>
          </div>
        </div>
      </div>

      <!-- Annotated Images -->
      <div v-if="jobData.annotatedImages && jobData.annotatedImages.length > 0" class="results-section">
        <div class="annotated-section">
          <div class="section-header">
            <h3>어노테이션 도면</h3>
            <div class="pdf-buttons">
              <button
                v-if="hasEditedImages()"
                @click="regeneratePdf()"
                class="btn-regenerate"
                :disabled="isRegeneratingPdf"
              >
                <span v-if="isRegeneratingPdf" class="loading"></span>
                <span v-else>🔄 PDF 재생성</span>
              </button>
              <button v-if="jobData.originalPdfUrl" @click="downloadOriginalPdf" class="btn-pdf-original">
                📋 원본 PDF
              </button>
              <button v-if="jobData.annotatedPdf" @click="downloadPdf" class="btn-pdf-download">
                📄 완성 PDF 다운로드
              </button>
            </div>
          </div>
          <div class="image-grid">
            <div v-for="(image, index) in jobData.annotatedImages" :key="'annotated-' + index" class="image-card">
              <div class="image-wrapper">
                <img
                  :src="getImageUrl(image)"
                  :alt="`어노테이션 ${index + 1}`"
                  @click="openModal(image, index, true)"
                  @error="handleImageError($event, image)"
                  style="cursor: pointer;"
                />
              </div>
              <div class="image-info">
                <div class="image-title">어노테이션 {{ index + 1 }}</div>
                <div class="image-meta">
                  <span v-if="image.isEdited" class="badge badge-edited">✏️ 편집됨</span>
                  <span v-else class="badge badge-annotated">명칭 추가됨</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 번호 매핑 정보 -->
      <div v-if="jobData.numberMappings && Object.keys(jobData.numberMappings).length > 0" class="mappings-section">
        <h3>부품 번호 매핑</h3>
        <div class="mappings-grid">
          <div v-for="(value, key) in jobData.numberMappings" :key="key" class="mapping-item">
            <span class="mapping-key">{{ key }}</span>
            <span class="mapping-arrow">→</span>
            <span class="mapping-value">{{ value }}</span>
          </div>
        </div>
      </div>

      <!-- 추출된 도면 (moved to bottom) -->
      <div v-if="jobData.extractedImages && jobData.extractedImages.length > 0" class="results-section">
        <div class="results-header">
          <h2 class="results-title">추출된 도면 (원본)</h2>
          <div class="results-count">총 {{ jobData.extractedImages.length }}개</div>
        </div>

        <!-- Original Images -->
        <div class="image-grid">
          <div v-for="(image, index) in jobData.extractedImages" :key="index" class="image-card">
            <div class="image-wrapper">
              <img
                :src="getImageUrl(image)"
                :alt="`도면 ${index + 1}`"
                @click="openModal(image)"
                @error="handleImageError($event, image)"
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
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import ImageModal from '../ImageModal.vue'
import config from '../config'
const API_BASE_URL = config.API_URL

const route = useRoute()
const router = useRouter()
const jobId = computed(() => route.params.jobId)

const jobData = ref(null)
const loading = ref(true)
const error = ref(null)
const modalOpen = ref(false)
const selectedImage = ref(null)
const selectedImageIndex = ref(0)
const selectedImageIsAnnotated = ref(false)
const editedImages = ref({})
const isRegeneratingPdf = ref(false)
const pollingInterval = ref(null)

const getStatusClass = (status) => {
  const statusClasses = {
    'PENDING': 'status-pending',
    'PROCESSING': 'status-processing',
    'COMPLETED': 'status-completed',
    'FAILED': 'status-failed'
  }
  return statusClasses[status] || 'status-unknown'
}

const getStatusText = (status) => {
  const statusTexts = {
    'PENDING': '대기 중',
    'PROCESSING': '처리 중',
    'COMPLETED': '완료',
    'FAILED': '실패'
  }
  return statusTexts[status] || status
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

const getImageUrl = (image) => {
  // If image is an object with url property, use it
  if (typeof image === 'object' && image.url) {
    console.log('getImageUrl: Using image.url:', image.url)
    return image.url
  }
  // For local development, use the local API endpoint
  if (config.isLocal) {
    const filename = typeof image === 'string' ? image : image.filename
    const url = `${API_BASE_URL}/images/${encodeURIComponent(filename)}`
    console.log('getImageUrl: Local URL:', url)
    return url
  }
  // Otherwise fallback to old behavior (for backward compatibility)
  const url = `${API_BASE_URL}/images/${encodeURIComponent(image)}`
  console.log('getImageUrl: Fallback URL:', url)
  return url
}

const getImageName = (image) => {
  // If image is an object with filename property, use it
  if (typeof image === 'object' && image.filename) {
    return image.filename
  }
  // If image is an object with key property, extract filename from it
  if (typeof image === 'object' && image.key) {
    return image.key.split('/').pop()
  }
  // Otherwise assume it's a string key
  return image.split('/').pop()
}

const openModal = (image, index = 0, isAnnotated = false) => {
  console.log('Opening modal with image:', image)
  // Convert job result image format to ImageModal compatible format
  const imageObj = {
    filename: getImageName(image),
    url: getImageUrl(image),
    width: 'Unknown',
    height: 'Unknown',
    figure_number: getImageName(image).replace('_annotated', '').replace('.png', '')
  }
  selectedImage.value = imageObj
  selectedImageIndex.value = index
  selectedImageIsAnnotated.value = isAnnotated
  modalOpen.value = true
}

const closeModal = () => {
  modalOpen.value = false
  selectedImage.value = null
}

const getJobFilename = (job) => {
  if (!job) return '파일명 없음'
  
  // Try different possible field names for filename
  if (job.fileName) return job.fileName
  if (job.filename) return job.filename
  if (job.originalFileName) return job.originalFileName
  if (job.original_filename) return job.original_filename
  if (job.file_name) return job.file_name
  
  // Extract from s3Key if available
  if (job.s3Key) {
    const filename = job.s3Key.split('/').pop()
    if (filename && filename !== 'undefined' && filename.length > 0) return filename
  }
  
  // Generate fallback name from jobId
  if (job.jobId) return `${job.jobId.substring(0, 8)}.pdf`
  
  return '파일명 없음'
}

const goBack = () => {
  router.push('/')
}

const downloadRegeneratedPdf = async (pdf) => {
  try {
    if (!pdf.url) {
      console.error('PDF URL not found')
      return
    }

    // Use the presigned URL directly from the backend
    console.log('Downloading regenerated PDF with presigned URL')

    // Simply open the URL in a new window/tab - browser will handle the download
    window.open(pdf.url, '_blank')

  } catch (error) {
    console.error('Failed to download regenerated PDF:', error)
    alert('PDF 다운로드에 실패했습니다.')
  }
}

const handleImageError = (event, image) => {
  console.error('Image failed to load:', image)
  console.log('Image URL that failed:', event.target.src)

  // If this is an edited image, try to use the original URL as fallback
  if (image.isEdited && image.originalUrl) {
    console.log('Trying original URL as fallback:', image.originalUrl)
    event.target.src = image.originalUrl
  } else {
    // Show a placeholder image
    event.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHRleHQtYW5jaG9yPSJtaWRkbGUiIHg9IjIwMCIgeT0iMTUwIiBzdHlsZT0iZmlsbDojYWFhO2ZvbnQtd2VpZ2h0OmJvbGQ7Zm9udC1zaXplOjE5cHg7Zm9udC1mYW1pbHk6QXJpYWwsSGVsdmV0aWNhLHNhbnMtc2VyaWY7ZG9taW5hbnQtYmFzZWxpbmU6Y2VudHJhbCI+SU1BR0UgTk9UIEZPVU5EPC90ZXh0Pjwvc3ZnPg=='
  }
}

const handleEditedImage = async (data) => {
  console.log('JobResultView: handleEditedImage called with data:', data)

  const { imageIndex, editedData } = data

  // Convert index to string for consistent storage
  const indexStr = String(imageIndex)

  // Store edited image data with string key
  editedImages.value[indexStr] = editedData
  console.log('JobResultView: Stored edited image at index:', indexStr)

  // Update the displayed annotated image immediately with the base64 data
  if (jobData.value && jobData.value.annotatedImages && jobData.value.annotatedImages[imageIndex]) {
    // Create a completely new object for Vue reactivity
    const updatedImages = jobData.value.annotatedImages.map((img, idx) => {
      if (idx === imageIndex) {
        // Explicitly create new object without spread to ensure url is overridden
        return {
          key: img.key || img,
          filename: img.filename || '',
          url: editedData,  // Use the base64 data directly for immediate display
          isEdited: true,
          originalUrl: img.originalUrl || img.url || (typeof img === 'string' ? `https://d38f9rplbkj0f2.cloudfront.net/${img}` : '')
        }
      }
      return img
    })

    // Replace the entire array to trigger Vue reactivity
    jobData.value.annotatedImages = updatedImages
    console.log('Updated annotatedImages after edit:', updatedImages)

    // Force update
    jobData.value = { ...jobData.value }
  }

  // Save edited image to server
  try {
    let response

    if (config.isLocal) {
      // Local environment: Different endpoint/format if needed
      console.log('Local environment: Saving edited image')
      // For local, you might want to save differently or skip server save
      // For now, we'll skip the save in local environment
      console.log('Local environment: Skip server save, only update UI')
    } else {
      // AWS environment: Save to S3 via Lambda
      response = await axios.post(`${API_BASE_URL}/save-edited-image`, {
        jobId: jobId.value,
        imageIndex,
        editedData,
        sessionId: getSessionId()
      })

      if (response.data.message) {
        console.log('Image saved successfully to S3')

        // After successful save, reload job data to get server state
        // This ensures persistence across refreshes
        setTimeout(() => {
          loadJobResult()
        }, 500)
      }
    }
  } catch (error) {
    console.error('Failed to save edited image:', error)
    if (error.response) {
      console.error('Error response:', error.response.data)
    }
  }
}

const hasEditedImages = () => {
  return Object.keys(editedImages.value).length > 0
}

const getSessionId = () => {
  let sessionId = sessionStorage.getItem('editSessionId')
  if (!sessionId) {
    sessionId = 'session-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9)
    sessionStorage.setItem('editSessionId', sessionId)
  }
  return sessionId
}

const regeneratePdf = async () => {
  isRegeneratingPdf.value = true

  try {
    // AWS environment only - regenerate PDF is not available in local
    if (config.isLocal) {
      alert('PDF 재생성은 AWS 환경에서만 사용 가능합니다.')
      isRegeneratingPdf.value = false
      return
    }

    const sessionId = getSessionId()

    const response = await axios.post(`${API_BASE_URL}/regenerate-pdf`, {
      jobId: jobId.value,
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
      } else {
        // Force regenerate new PDF
        await regeneratePdfForce()
      }
    } else if (response.data.action === 'regeneration_started') {
      // New regeneration started
      alert('PDF 재생성이 시작되었습니다. 완료되면 작업 이력에서 다운로드할 수 있습니다.')
    }

  } catch (error) {
    console.error('Failed to regenerate PDF:', error)
    alert('PDF 재생성에 실패했습니다.')
  } finally {
    isRegeneratingPdf.value = false
  }
}

const regeneratePdfForce = async () => {
  try {
    const sessionId = getSessionId()

    const response = await axios.post(`${API_BASE_URL}/regenerate-pdf`, {
      jobId: jobId.value,
      editedImages: editedImages.value,
      sessionId,
      forceRegenerate: true
    })

    if (response.data.action === 'regeneration_started') {
      alert('PDF 재생성이 시작되었습니다. 완료되면 작업 이력에서 다운로드할 수 있습니다.')
    }
  } catch (error) {
    console.error('Failed to force regenerate PDF:', error)
    alert('PDF 재생성에 실패했습니다.')
  }
}

const downloadOriginalPdf = async () => {
  try {
    // Check if originalPdfUrl is available
    if (jobData.value.originalPdfUrl) {
      // Use the provided URL directly
      const link = document.createElement('a')
      link.href = jobData.value.originalPdfUrl
      link.download = getJobFilename(jobData.value)
      link.target = '_blank'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } else {
      alert('원본 PDF를 찾을 수 없습니다.')
    }
  } catch (error) {
    console.error('Original PDF download failed:', error)
    alert('원본 PDF 다운로드에 실패했습니다.')
  }
}

const downloadPdf = async () => {
  if (!jobData.value || !jobData.value.annotatedPdf) {
    console.error('PDF URL not found')
    return
  }

  try {
    // Create CloudFront URL for direct S3 access
    const cloudFrontUrl = 'https://d38f9rplbkj0f2.cloudfront.net'
    const pdfUrl = `${cloudFrontUrl}/${jobData.value.annotatedPdf}`

    // Direct download from CloudFront/S3
    const link = document.createElement('a')
    link.href = pdfUrl

    // Extract filename from URL or use default
    const filename = jobData.value.annotatedPdf.split('/').pop() || 'annotated.pdf'
    link.download = filename
    link.target = '_blank'

    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (error) {
    console.error('PDF download failed:', error)
    alert('PDF 다운로드에 실패했습니다. 다시 시도해주세요.')
  }
}

const loadJobResult = async () => {
  loading.value = true
  error.value = null

  try {
    // For local development, we don't have job results endpoint
    if (config.isLocal) {
      error.value = '로컬 환경에서는 작업 결과 페이지를 지원하지 않습니다. 메인 페이지에서 직접 처리해주세요.'
      loading.value = false
      return
    }

    const response = await axios.get(`${API_BASE_URL}/result/${jobId.value}`)
    jobData.value = response.data

    // Debug log for checking field names
    console.log('Job data fields:', Object.keys(jobData.value))
    console.log('Job data:', jobData.value)

    // Load edited images if available
    if (jobData.value.editedImages && Object.keys(jobData.value.editedImages).length > 0) {
      editedImages.value = jobData.value.editedImages
      console.log('Loaded edited images from server:', editedImages.value)

      // Update annotated images with edited versions
      if (jobData.value.annotatedImages && Array.isArray(jobData.value.annotatedImages)) {
        console.log('Original annotatedImages:', jobData.value.annotatedImages)

        const updatedImages = []
        for (let index = 0; index < jobData.value.annotatedImages.length; index++) {
          const image = jobData.value.annotatedImages[index]
          const indexStr = String(index)

          if (editedImages.value[indexStr]) {
            // The editedImages should already contain full URLs from Lambda
            const editedUrl = editedImages.value[indexStr]
            console.log(`Applying edited image for index ${indexStr}:`, editedUrl)

            // Get original URL before replacing
            let originalUrl = ''
            if (typeof image === 'object' && image.url) {
              originalUrl = image.url
            } else if (typeof image === 'string') {
              originalUrl = `https://d38f9rplbkj0f2.cloudfront.net/${image}`
            } else if (image.key) {
              originalUrl = `https://d38f9rplbkj0f2.cloudfront.net/${image.key}`
            }

            // Create new image object with edited URL - explicitly override url
            const newImage = {
              key: image.key || image,
              filename: image.filename || (typeof image === 'string' ? image.split('/').pop() : ''),
              url: editedUrl,  // Explicitly set the edited URL
              isEdited: true,
              originalUrl: originalUrl
            }
            console.log(`Created new image object:`, newImage)
            updatedImages.push(newImage)
          } else {
            // Keep original image, but ensure it has proper format
            if (typeof image === 'string' || !image.url) {
              const imageUrl = typeof image === 'string' ? image : (image.key || image.filename || '')
              updatedImages.push({
                key: imageUrl,
                url: `https://d38f9rplbkj0f2.cloudfront.net/${imageUrl}`,
                filename: imageUrl.split('/').pop(),
                isEdited: false
              })
            } else {
              updatedImages.push(image)
            }
          }
        }

        // Replace entire array to trigger Vue reactivity
        jobData.value.annotatedImages = updatedImages
        console.log('Updated annotatedImages:', jobData.value.annotatedImages)
      }
    } else {
      // Even if no edited images, ensure annotatedImages have proper structure
      if (jobData.value.annotatedImages && Array.isArray(jobData.value.annotatedImages)) {
        jobData.value.annotatedImages = jobData.value.annotatedImages.map(image => {
          if (typeof image === 'string' || !image.url) {
            const imageUrl = typeof image === 'string' ? image : (image.key || image.filename || '')
            return {
              key: imageUrl,
              url: `https://d38f9rplbkj0f2.cloudfront.net/${imageUrl}`,
              filename: imageUrl.split('/').pop(),
              isEdited: false
            }
          }
          return image
        })
      }
    }

    // 처리 중인 경우 폴링 시작
    if (jobData.value.status === 'PROCESSING' || jobData.value.status === 'PENDING') {
      startPolling()
    } else {
      stopPolling()
    }
  } catch (err) {
    console.error('Failed to load job result:', err)
    error.value = '작업 정보를 불러오는데 실패했습니다.'
  } finally {
    loading.value = false
  }
}

const startPolling = () => {
  if (pollingInterval.value) return
  
  pollingInterval.value = setInterval(async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/result/${jobId.value}`)
      jobData.value = response.data
      
      if (jobData.value.status === 'COMPLETED' || jobData.value.status === 'FAILED') {
        stopPolling()
      }
    } catch (err) {
      console.error('Polling error:', err)
    }
  }, 3000) // 3초마다 폴링
}

const stopPolling = () => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
}

onMounted(() => {
  loadJobResult()
})

// 컴포넌트 언마운트 시 폴링 중지
onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.job-result-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 30px;
}

.back-button {
  padding: 8px 16px;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  white-space: nowrap;
}

.back-button:hover {
  background: #5a6268;
}

.loading, .error {
  text-align: center;
  padding: 40px;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 5px solid #f3f3f3;
  border-top: 5px solid #007bff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.status-card, .progress-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.status-info {
  display: grid;
  gap: 10px;
  margin-top: 15px;
}

.status-item {
  display: flex;
  gap: 10px;
}

.label {
  font-weight: bold;
  min-width: 100px;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: bold;
}

.status-pending {
  background: #ffc107;
  color: #000;
}

.status-processing {
  background: #17a2b8;
  color: white;
}

.status-completed {
  background: #28a745;
  color: white;
}

.status-failed {
  background: #dc3545;
  color: white;
}

.progress-bar {
  width: 100%;
  height: 30px;
  background: #f0f0f0;
  border-radius: 15px;
  overflow: hidden;
  margin: 15px 0;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #007bff, #0056b3);
  transition: width 0.3s ease;
}

.results-section {
  margin-top: 30px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.results-title {
  font-size: 24px;
  font-weight: 600;
  color: #2d3748;
  margin: 0;
}

.results-count {
  background: #667eea;
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 24px;
  margin-bottom: 30px;
}

.image-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
  transition: all 0.3s ease;
}

.image-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.image-wrapper {
  position: relative;
  width: 100%;
  height: 200px;
  overflow: hidden;
}

.image-wrapper img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #f8fafc;
  transition: transform 0.3s ease;
}

.image-card:hover .image-wrapper img {
  transform: scale(1.05);
}

.image-info {
  padding: 16px;
}

.image-title {
  font-size: 16px;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 8px;
}

.image-meta {
  display: flex;
  gap: 8px;
}

.badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.badge-original {
  background: #e0f2fe;
  color: #0277bd;
}

.badge-annotated {
  background: #f3e5f5;
  color: #7b1fa2;
}

.badge-edited {
  background: #fff3cd;
  color: #856404;
  border: 1px solid #ffc107;
}

.annotated-section {
  margin-top: 40px;
}

.annotated-section h3 {
  font-size: 20px;
  font-weight: 600;
  color: #2d3748;
  margin: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.pdf-buttons {
  display: flex;
  gap: 10px;
}

.btn-pdf-original {
  padding: 10px 20px;
  background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(107, 114, 128, 0.3);
}

.btn-pdf-original:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(107, 114, 128, 0.4);
}

.btn-pdf-download {
  padding: 10px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.btn-pdf-download:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.btn-pdf-download:active,
.btn-pdf-original:active {
  transform: translateY(0);
}

.btn-regenerate {
  padding: 10px 20px;
  background: linear-gradient(135deg, #f59e0b 0%, #f97316 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(245, 158, 11, 0.3);
}

.btn-regenerate:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(245, 158, 11, 0.4);
}

.btn-regenerate:disabled {
  background: #cccccc;
  cursor: not-allowed;
  opacity: 0.6;
}

.loading {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: white;
  animation: spin 1s ease-in-out infinite;
}

.regenerated-pdfs-section {
  margin-top: 30px;
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.regenerated-pdfs-section h3 {
  font-size: 20px;
  font-weight: 600;
  color: #2d3748;
  margin: 0 0 20px 0;
}

.pdf-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pdf-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  transition: background 0.2s;
}

.pdf-item:hover {
  background: #f1f5f9;
}

.pdf-info {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.pdf-filename {
  font-weight: 600;
  color: #1f2937;
  flex: 1;
}

.pdf-date {
  color: #6b7280;
  font-size: 14px;
}

.edit-count {
  background: #fef3c7;
  color: #92400e;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.btn-download {
  padding: 8px 16px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-download:hover {
  background: #2563eb;
  transform: translateY(-1px);
}

.mappings-section {
  margin-top: 30px;
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.mappings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 15px;
  margin-top: 15px;
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