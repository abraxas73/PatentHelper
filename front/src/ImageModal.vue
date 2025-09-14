<template>
  <div v-if="isOpen" class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-container" @click.stop>
      <!-- Close button -->
      <button class="modal-close" @click="close">✕</button>

      <!-- Image display -->
      <div class="modal-image-wrapper">
        <img :src="imageUrl" :alt="image.filename" />
      </div>

      <!-- Image info -->
      <div class="modal-info">
        <h3>{{ image.figure_number || (image.original_page !== undefined ? `페이지 ${image.original_page + 1}` : image.key || '이미지') }}</h3>
        <p>
          {{ image.filename || image.key || '이미지 파일' }}
          <span v-if="image.width && image.height && image.width !== 'Unknown'">
            • {{ image.width }} × {{ image.height }}px
          </span>
        </p>
      </div>

      <!-- Download section -->
      <div class="modal-actions">
        <div class="format-selector">
          <label>다운로드 형식:</label>
          <select v-model="selectedFormat" class="format-select">
            <option value="png">PNG (원본)</option>
          </select>
        </div>

        <div class="action-buttons">
          <button class="btn btn-edit" @click="openEditor" v-if="canEdit">
            ✏️ 편집
          </button>
          <button class="btn btn-download" @click="download" :disabled="isDownloading">
            <span v-if="isDownloading" class="loading"></span>
            <span v-else>📥 다운로드</span>
          </button>
          <button class="btn btn-secondary" @click="close">닫기</button>
        </div>
      </div>
    </div>

    <!-- Image Editor -->
    <ImageEditor
      v-if="isEditorOpen"
      :isOpen="isEditorOpen"
      :imageUrl="imageUrl"
      :imageIndex="imageIndex"
      @close="closeEditor"
      @save="handleEditedImage"
    />
  </div>
</template>

<script>
import { ref, computed } from 'vue'
import axios from 'axios'
import ImageEditor from './components/ImageEditor.vue'

export default {
  name: 'ImageModal',
  components: {
    ImageEditor
  },
  props: {
    isOpen: {
      type: Boolean,
      required: true
    },
    image: {
      type: Object,
      required: true
    },
    imageIndex: {
      type: Number,
      default: 0
    },
    isAnnotated: {
      type: Boolean,
      default: false
    }
  },
  emits: ['close', 'save-edited'],
  setup(props, { emit }) {
    const selectedFormat = ref('png')
    const isDownloading = ref(false)
    const isEditorOpen = ref(false)
    const editedImageUrl = ref(null)

    // Only allow editing for annotated images
    const canEdit = computed(() => {
      // Check if image is annotated by prop or by filename/URL containing 'annotated'
      const isAnnotatedByProp = props.isAnnotated
      const isAnnotatedByUrl = props.image?.url?.includes('annotated') ||
                              props.image?.filename?.includes('annotated') ||
                              props.image?.key?.includes('annotated')

      const result = isAnnotatedByProp || isAnnotatedByUrl

      console.log('ImageModal canEdit check:', {
        isAnnotated: props.isAnnotated,
        isAnnotatedByUrl,
        imageType: props.image?.type,
        imageSrc: props.image?.url,
        finalResult: result
      })
      return result
    })
    
    const imageUrl = computed(() => {
      // If we have an edited image, show that
      if (editedImageUrl.value) {
        return editedImageUrl.value
      }

      if (!props.image) return ''
      // If image has url property (from job results), use it directly
      if (props.image.url) {
        return props.image.url
      }
      // Otherwise fallback to filename based URL (from main page)
      if (props.image.filename) {
        return `/api/v1/images/${props.image.filename}`
      }
      return ''
    })
    
    const close = () => {
      isEditorOpen.value = false
      emit('close')
    }

    const openEditor = () => {
      isEditorOpen.value = true
    }

    const closeEditor = () => {
      isEditorOpen.value = false
    }

    const handleEditedImage = (data) => {
      console.log('ImageModal: handleEditedImage called with data:', data)

      // Update local imageUrl to show the edited version
      if (data.editedData) {
        editedImageUrl.value = data.editedData
        console.log('ImageModal: Updated local image preview')
      }

      // Emit the edited image data to parent component
      emit('save-edited', data)
      console.log('ImageModal: save-edited event emitted')

      // Don't close the editor - let user continue editing or close manually
      // Success feedback is shown in the editor itself
    }
    
    const handleOverlayClick = (e) => {
      if (e.target === e.currentTarget) {
        close()
      }
    }
    
    const download = async () => {
      if (!props.image) return
      
      isDownloading.value = true
      
      try {
        let downloadUrl = ''
        let filename = ''
        
        // Determine filename
        if (props.image.filename) {
          filename = props.image.filename.split('.')[0]
        } else if (props.image.figure_number) {
          filename = props.image.figure_number
        } else {
          filename = 'image'
        }
        
        if (selectedFormat.value === 'png') {
          // Direct download for PNG
          filename += '.png'

          // For cross-origin URLs (S3, CloudFront), fetch as blob
          if (imageUrl.value.includes('amazonaws.com') || imageUrl.value.includes('cloudfront.net')) {
            try {
              const response = await fetch(imageUrl.value)
              const blob = await response.blob()
              downloadUrl = URL.createObjectURL(blob)

              const link = document.createElement('a')
              link.href = downloadUrl
              link.download = filename
              document.body.appendChild(link)
              link.click()
              document.body.removeChild(link)

              // Clean up blob URL
              setTimeout(() => URL.revokeObjectURL(downloadUrl), 100)
            } catch (error) {
              console.error('Download failed:', error)
              // Fallback: open in new tab
              window.open(imageUrl.value, '_blank')
            }
          } else {
            // For local URLs, direct download
            const link = document.createElement('a')
            link.href = imageUrl.value
            link.download = filename
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
          }
        } else {
          // For format conversion, try to use backend if available
          try {
            const response = await axios.post('/api/v1/convert', {
              filename: props.image.filename || filename,
              format: selectedFormat.value
            }, {
              responseType: 'blob'
            })
            
            // Create blob URL for download
            const blob = new Blob([response.data], {
              type: response.headers['content-type']
            })
            downloadUrl = URL.createObjectURL(blob)
            filename += `.${selectedFormat.value}`
            
            // Trigger download
            const link = document.createElement('a')
            link.href = downloadUrl
            link.download = filename
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            
            // Clean up blob URL
            URL.revokeObjectURL(downloadUrl)
          } catch (conversionError) {
            // If conversion fails, fallback to direct download with warning
            console.warn('Format conversion not available, downloading as PNG:', conversionError)
            alert('형식 변환이 지원되지 않습니다. PNG 형식으로 다운로드됩니다.')

            // Use the same blob download approach for fallback
            if (imageUrl.value.includes('amazonaws.com') || imageUrl.value.includes('cloudfront.net')) {
              try {
                const response = await fetch(imageUrl.value)
                const blob = await response.blob()
                const blobUrl = URL.createObjectURL(blob)

                const link = document.createElement('a')
                link.href = blobUrl
                link.download = filename + '.png'
                document.body.appendChild(link)
                link.click()
                document.body.removeChild(link)

                setTimeout(() => URL.revokeObjectURL(blobUrl), 100)
              } catch (err) {
                console.error('Fallback download failed:', err)
                window.open(imageUrl.value, '_blank')
              }
            } else {
              const link = document.createElement('a')
              link.href = imageUrl.value
              link.download = filename + '.png'
              document.body.appendChild(link)
              link.click()
              document.body.removeChild(link)
            }
          }
        }
        
      } catch (error) {
        console.error('Download failed:', error)
        alert('다운로드 중 오류가 발생했습니다.')
      } finally {
        isDownloading.value = false
      }
    }
    
    return {
      selectedFormat,
      isDownloading,
      isEditorOpen,
      canEdit,
      imageUrl,
      close,
      openEditor,
      closeEditor,
      handleEditedImage,
      handleOverlayClick,
      download
    }
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal-container {
  background: white;
  border-radius: 16px;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
  animation: slideUp 0.3s ease;
  position: relative;
}

@keyframes slideUp {
  from {
    transform: translateY(30px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.modal-close {
  position: absolute;
  top: 15px;
  right: 15px;
  background: rgba(0, 0, 0, 0.5);
  color: white;
  border: none;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  z-index: 10;
}

.modal-close:hover {
  background: rgba(0, 0, 0, 0.7);
  transform: scale(1.1);
}

.modal-image-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  overflow: auto;
  background: #f8fafc;
  border-radius: 16px 16px 0 0;
}

.modal-image-wrapper img {
  max-width: 100%;
  max-height: 60vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
}

.modal-info {
  padding: 20px 30px;
  border-bottom: 1px solid #e5e7eb;
  background: white;
}

.modal-info h3 {
  font-size: 1.5rem;
  color: #2d3748;
  margin-bottom: 8px;
}

.modal-info p {
  color: #718096;
  font-size: 0.95rem;
}

.modal-actions {
  padding: 20px 30px;
  background: white;
  border-radius: 0 0 16px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}

.format-selector {
  display: flex;
  align-items: center;
  gap: 12px;
}

.format-selector label {
  font-weight: 600;
  color: #4a5568;
}

.format-select {
  padding: 8px 12px;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  font-size: 1rem;
  color: #2d3748;
  background: white;
  cursor: pointer;
  transition: border-color 0.3s ease;
  min-width: 150px;
}

.format-select:focus {
  outline: none;
  border-color: #667eea;
}

.action-buttons {
  display: flex;
  gap: 12px;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-download {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-download:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
}

.btn-download:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: #e5e7eb;
  color: #4a5568;
}

.btn-secondary:hover {
  background: #cbd5e1;
}

.btn-edit {
  background: linear-gradient(135deg, #f59e0b 0%, #f97316 100%);
  color: white;
}

.btn-edit:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(245, 158, 11, 0.4);
}

.loading {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: white;
  animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Responsive design */
@media (max-width: 768px) {
  .modal-container {
    max-width: 95vw;
    max-height: 95vh;
  }
  
  .modal-actions {
    flex-direction: column;
    gap: 15px;
  }
  
  .format-selector {
    width: 100%;
    justify-content: space-between;
  }
  
  .action-buttons {
    width: 100%;
  }
  
  .action-buttons .btn {
    flex: 1;
  }
}
</style>