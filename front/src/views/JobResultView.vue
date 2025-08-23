<template>
  <div class="job-result-container">
    <div class="header">
      <button @click="goBack" class="back-button">← 목록으로</button>
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
            <span>{{ jobData.fileName }}</span>
          </div>
          <div class="status-item">
            <span class="label">생성 시간:</span>
            <span>{{ formatDate(jobData.createdAt) }}</span>
          </div>
          <div v-if="jobData.completedAt" class="status-item">
            <span class="label">완료 시간:</span>
            <span>{{ formatDate(jobData.completedAt) }}</span>
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

      <!-- 추출된 도면 -->
      <div v-if="jobData.extractedImages && jobData.extractedImages.length > 0" class="results-section">
        <div class="results-header">
          <h2 class="results-title">추출된 도면</h2>
          <div class="results-count">총 {{ jobData.extractedImages.length }}개</div>
        </div>

        <!-- Original Images -->
        <div class="image-grid">
          <div v-for="(image, index) in jobData.extractedImages" :key="index" class="image-card">
            <div class="image-wrapper">
              <img 
                :src="getImageUrl(image)" 
                :alt="`도면 ${index + 1}`" 
                @click="openModal(getImageUrl(image))"
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
        <div v-if="jobData.annotatedImages && jobData.annotatedImages.length > 0" class="annotated-section">
          <h3>어노테이션 도면</h3>
          <div class="image-grid">
            <div v-for="(image, index) in jobData.annotatedImages" :key="'annotated-' + index" class="image-card">
              <div class="image-wrapper">
                <img 
                  :src="getImageUrl(image)" 
                  :alt="`어노테이션 ${index + 1}`" 
                  @click="openModal(getImageUrl(image))"
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
    </div>

    <!-- 이미지 모달 -->
    <div v-if="modalImage" class="modal" @click="closeModal">
      <div class="modal-content" @click.stop>
        <span class="close" @click="closeModal">&times;</span>
        <img 
          :src="modalImage" 
          alt="확대 이미지" 
          @error="handleImageError"
          @load="handleImageLoad"
        />
        <div v-if="imageError" class="error-message">
          이미지를 불러올 수 없습니다: {{ modalImage }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import config from '../config'
const API_BASE_URL = config.API_URL

const route = useRoute()
const router = useRouter()
const jobId = computed(() => route.params.jobId)

const jobData = ref(null)
const loading = ref(true)
const error = ref(null)
const modalImage = ref(null)
const pollingInterval = ref(null)
const imageError = ref(false)

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
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('ko-KR')
}

const getImageUrl = (image) => {
  // If image is an object with url property, use it
  if (typeof image === 'object' && image.url) {
    return image.url
  }
  // Otherwise fallback to old behavior (for backward compatibility)
  return `${API_BASE_URL}/images/${encodeURIComponent(image)}`
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

const openModal = (imageUrl) => {
  console.log('Opening modal with image URL:', imageUrl)
  modalImage.value = imageUrl
  imageError.value = false
}

const closeModal = () => {
  modalImage.value = null
  imageError.value = false
}

const handleImageError = (event) => {
  console.error('Image failed to load:', event.target.src)
  imageError.value = true
}

const handleImageLoad = (event) => {
  console.log('Image loaded successfully:', event.target.src)
  imageError.value = false
}

const goBack = () => {
  router.push('/')
}

const loadJobResult = async () => {
  loading.value = true
  error.value = null
  
  try {
    const response = await axios.get(`${API_BASE_URL}/result/${jobId.value}`)
    jobData.value = response.data
    
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

.annotated-section {
  margin-top: 40px;
}

.annotated-section h3 {
  font-size: 20px;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 20px;
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

.modal {
  display: flex;
  align-items: center;
  justify-content: center;
  position: fixed;
  z-index: 1000;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0,0,0,0.9);
}

.modal-content {
  position: relative;
  max-width: 90%;
  max-height: 90%;
}

.modal-content img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.close {
  position: absolute;
  top: -40px;
  right: 0;
  color: white;
  font-size: 35px;
  font-weight: bold;
  cursor: pointer;
}

.close:hover {
  color: #ccc;
}

.error-message {
  color: #dc3545;
  background: rgba(255, 255, 255, 0.9);
  padding: 10px;
  border-radius: 5px;
  margin-top: 10px;
  font-size: 14px;
  word-break: break-all;
}
</style>