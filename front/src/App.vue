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
      <h1>🔬 Patent Helper</h1>
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
          @click="processFile"
        >
          <span v-if="isProcessing" class="loading"></span>
          <span v-else>도면 추출 시작</span>
        </button>
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

      <!-- Tabs -->
      <div class="tabs">
        <button 
          class="tab"
          :class="{ active: currentTab === 'all' }"
          @click="currentTab = 'all'"
        >
          전체
        </button>
        <button 
          class="tab"
          :class="{ active: currentTab === 'original' }"
          @click="currentTab = 'original'"
        >
          원본 도면
        </button>
        <button 
          class="tab"
          :class="{ active: currentTab === 'annotated' }"
          @click="currentTab = 'annotated'"
        >
          어노테이션
        </button>
      </div>

      <!-- Image Grid -->
      <div class="image-grid">
        <div 
          v-for="image in filteredImages" 
          :key="image.file_path"
          class="image-card"
        >
          <div class="image-wrapper">
            <img 
              :src="getImageUrl(image.filename)" 
              :alt="image.filename"
              @click="openModal(image)"
              style="cursor: pointer;"
            />
          </div>
          <div class="image-info">
            <div class="image-title">
              {{ image.figure_number || `페이지 ${image.original_page + 1}` }}
            </div>
            <div class="image-meta">
              <span class="badge badge-original">
                {{ image.width }} × {{ image.height }}
              </span>
              <span>{{ image.filename }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Annotated Images -->
    <div v-if="annotatedImages.length > 0" class="results-section">
      <div class="results-header">
        <h2 class="results-title">어노테이션된 도면</h2>
        <div class="results-count">총 {{ annotatedImages.length }}개</div>
      </div>

      <div class="image-grid">
        <div 
          v-for="(imagePath, index) in annotatedImages" 
          :key="imagePath"
          class="image-card"
        >
          <div class="image-wrapper">
            <img 
              :src="getAnnotatedImageUrl(imagePath)" 
              :alt="`Annotated ${index + 1}`"
              @click="openAnnotatedModal(imagePath, index)"
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
</template>

<script>
import { ref, computed } from 'vue'
import axios from 'axios'
import ImageModal from './ImageModal.vue'

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
    const currentTab = ref('all')
    const numberMappings = ref({})
    const modalOpen = ref(false)
    const selectedImage = ref(null)

    const handleFileSelect = (event) => {
      const file = event.target.files[0]
      if (file && file.type === 'application/pdf') {
        selectedFile.value = file
        errorMessage.value = ''
        successMessage.value = ''
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
        successMessage.value = ''
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
    }

    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 Bytes'
      const k = 1024
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
    }

    const processFile = async () => {
      if (!selectedFile.value) return

      isProcessing.value = true
      errorMessage.value = ''
      successMessage.value = ''

      const formData = new FormData()
      formData.append('file', selectedFile.value)

      try {
        const response = await axios.post('/api/v1/process', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        })

        images.value = response.data.extracted_images
        annotatedImages.value = response.data.annotated_images
        numberMappings.value = response.data.number_mappings
        
        successMessage.value = `성공적으로 ${images.value.length}개의 도면을 추출했습니다. 처리 시간: ${response.data.processing_time.toFixed(2)}초`
      } catch (error) {
        console.error('Error:', error)
        errorMessage.value = error.response?.data?.detail || '처리 중 오류가 발생했습니다.'
      } finally {
        isProcessing.value = false
      }
    }

    const getImageUrl = (filename) => {
      return `/api/v1/images/${filename}`
    }

    const getAnnotatedImageUrl = (imagePath) => {
      const filename = imagePath.split('/').pop()
      return `/api/v1/images/${filename}`
    }

    const openModal = (image) => {
      selectedImage.value = image
      modalOpen.value = true
    }
    
    const openAnnotatedModal = (imagePath, index) => {
      const filename = imagePath.split('/').pop()
      selectedImage.value = {
        filename: filename,
        figure_number: `어노테이션 ${index + 1}`,
        original_page: index,
        width: 0,
        height: 0
      }
      modalOpen.value = true
    }
    
    const closeModal = () => {
      modalOpen.value = false
      selectedImage.value = null
    }

    const filteredImages = computed(() => {
      if (currentTab.value === 'all') {
        return images.value
      } else if (currentTab.value === 'original') {
        return images.value.filter(img => !img.filename.includes('annotated'))
      } else {
        return images.value.filter(img => img.filename.includes('annotated'))
      }
    })

    return {
      selectedFile,
      isDragging,
      isProcessing,
      images,
      annotatedImages,
      errorMessage,
      successMessage,
      currentTab,
      numberMappings,
      filteredImages,
      handleFileSelect,
      handleDrop,
      removeFile,
      formatFileSize,
      processFile,
      getImageUrl,
      getAnnotatedImageUrl,
      openModal,
      openAnnotatedModal,
      closeModal,
      modalOpen,
      selectedImage
    }
  }
}
</script>