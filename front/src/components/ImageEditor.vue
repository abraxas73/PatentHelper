<template>
  <div v-if="isOpen" class="editor-overlay">
    <div class="editor-container">
      <!-- Header -->
      <div class="editor-header">
        <h3>이미지 편집</h3>
        <button class="close-btn" @click="close">✕</button>
      </div>

      <!-- Toolbar -->
      <div class="editor-toolbar">
        <!-- Drawing Tools -->
        <div class="tool-group">
          <button @click="setDrawingMode('select')" :class="{ active: drawingMode === 'select' }" title="선택">↖</button>
          <button @click="setDrawingMode('pen')" :class="{ active: drawingMode === 'pen' }" title="펜">✏️</button>
          <button @click="setDrawingMode('highlighter')" :class="{ active: drawingMode === 'highlighter' }" title="형광펜">🖍️</button>
          <button @click="setDrawingMode('eraser')" :class="{ active: drawingMode === 'eraser' }" title="지우개">🧹</button>
        </div>

        <div class="separator"></div>

        <!-- Shape Tools -->
        <div class="tool-group">
          <button @click="addText" title="텍스트 추가">T</button>
          <button @click="drawArrow" title="화살표">→</button>
          <button @click="drawRectangle" title="사각형">□</button>
          <button @click="drawCircle" title="원">○</button>
          <button @click="drawLine" title="선">─</button>
          <button @click="drawTriangle" title="삼각형">△</button>
        </div>

        <div class="separator"></div>

        <!-- Style Controls -->
        <div class="tool-group">
          <label class="tool-label">색상:</label>
          <input type="color" v-model="currentColor" title="색상 선택" />
          <label class="tool-label">두께:</label>
          <input
            type="range"
            v-model="strokeWidth"
            min="1"
            max="20"
            title="선 두께"
          />
          <span class="width-indicator">{{ strokeWidth }}px</span>
        </div>

        <div class="separator"></div>

        <!-- Text Controls (shown when text is selected) -->
        <div class="tool-group" v-if="selectedObject && selectedObject.type === 'i-text'">
          <label class="tool-label">글자크기:</label>
          <input
            type="range"
            v-model="fontSize"
            min="10"
            max="100"
            @input="updateTextSize"
            title="글자 크기"
          />
          <span class="width-indicator">{{ fontSize }}px</span>
          <button @click="toggleBold" :class="{ active: isBold }" title="굵게">B</button>
          <button @click="toggleItalic" :class="{ active: isItalic }" title="기울임">I</button>
          <button @click="toggleUnderline" :class="{ active: isUnderline }" title="밑줄">U</button>
        </div>

        <div class="separator"></div>

        <!-- Object Controls -->
        <div class="tool-group">
          <button @click="copyObject" :disabled="!selectedObject" title="복사">📋</button>
          <button @click="pasteObject" :disabled="!copiedObject" title="붙여넣기">📌</button>
          <button @click="rotateObject(-15)" :disabled="!selectedObject" title="왼쪽 회전">↺</button>
          <button @click="rotateObject(15)" :disabled="!selectedObject" title="오른쪽 회전">↻</button>
          <button @click="bringToFront" :disabled="!selectedObject" title="맨 앞으로">⬆</button>
          <button @click="sendToBack" :disabled="!selectedObject" title="맨 뒤로">⬇</button>
        </div>

        <div class="separator"></div>

        <!-- Edit Actions -->
        <div class="tool-group">
          <button @click="deleteSelected" :disabled="!selectedObject" title="선택 삭제">🗑️</button>
          <button @click="clearAll" title="모두 지우기">🧹</button>
          <button @click="undo" :disabled="!canUndo" title="실행취소">↶</button>
          <button @click="redo" :disabled="!canRedo" title="다시실행">↷</button>
        </div>

        <!-- Zoom Controls -->
        <div class="tool-group zoom-controls">
          <button @click="zoomIn" title="확대">🔍+</button>
          <button @click="zoomOut" title="축소">🔍-</button>
          <button @click="resetZoom" title="원래 크기">🔍</button>
          <span class="zoom-indicator">{{ Math.round(zoomLevel * 100) }}%</span>
        </div>
      </div>

      <!-- Canvas Area -->
      <div class="canvas-container">
        <canvas id="fabric-canvas"></canvas>
        <div class="canvas-help">
          <small>💡 마우스 휠: 확대/축소 | Alt+드래그 또는 마우스 가운데 버튼: 이동 | Ctrl+C/V: 복사/붙여넣기</small>
        </div>
      </div>

      <!-- Footer Actions -->
      <div class="editor-footer">
        <button class="btn btn-save" @click="save">💾 저장</button>
        <button class="btn btn-cancel" @click="close">닫기</button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

export default {
  name: 'ImageEditor',
  props: {
    isOpen: {
      type: Boolean,
      required: true
    },
    imageUrl: {
      type: String,
      required: true
    },
    imageIndex: {
      type: Number,
      default: 0
    }
  },
  emits: ['close', 'save'],
  setup(props, { emit }) {
    // Canvas instance
    let canvas = null
    let fabricLib = null

    // Editor state
    const currentColor = ref('#000000')
    const strokeWidth = ref(2)
    const canUndo = ref(false)
    const canRedo = ref(false)
    const history = ref([])
    const historyStep = ref(0)
    const drawingMode = ref('select')
    const selectedObject = ref(null)
    const copiedObject = ref(null)
    const fontSize = ref(20)
    const isBold = ref(false)
    const isItalic = ref(false)
    const isUnderline = ref(false)
    const zoomLevel = ref(1)

    // Initialize canvas
    const initCanvas = async () => {
      console.log('initCanvas called, isOpen:', props.isOpen, 'imageUrl:', props.imageUrl)

      if (!props.imageUrl || !props.isOpen) return

      // Wait for DOM to be ready
      await nextTick()

      // Dynamically import fabric
      if (!fabricLib) {
        console.log('Loading Fabric.js...')
        const fabric = await import('fabric')
        fabricLib = fabric.fabric || fabric.default || fabric
        console.log('Fabric.js loaded:', fabricLib)
      }

      // Check if canvas element exists
      const canvasElement = document.getElementById('fabric-canvas')
      if (!canvasElement) {
        console.error('Canvas element not found, retrying...')
        setTimeout(initCanvas, 100)
        return
      }
      console.log('Canvas element found:', canvasElement)

      try {
        // Create canvas instance with proper settings
        canvas = new fabricLib.Canvas('fabric-canvas', {
          backgroundColor: '#f0f0f0',
          preserveObjectStacking: true,
          renderOnAddRemove: true,
          uniformScaling: false,
          targetFindTolerance: 10,  // Increased for better handle detection
          perPixelTargetFind: false,  // Disable for better performance with controls
          selection: true,
          selectionBorderColor: '#667eea',
          selectionColor: 'rgba(102, 126, 234, 0.1)',
          selectionLineWidth: 2,
          controlsAboveOverlay: true,  // Ensure controls are above overlay
          allowTouchScrolling: false,
          stopContextMenu: true,
          skipTargetFind: false,  // Ensure target finding is not skipped
          renderOnAddRemove: false  // Optimize rendering
        })

        // Configure control settings for better interaction
        fabricLib.Object.prototype.set({
          transparentCorners: false,
          cornerColor: '#667eea',
          cornerStrokeColor: '#ffffff',
          cornerSize: 16,  // Larger corner size for easier clicking
          cornerStyle: 'circle',
          borderColor: '#667eea',
          borderScaleFactor: 2,
          padding: 0,  // Remove padding to align controls exactly
          rotatingPointOffset: 40,  // Increased offset for rotation handle
          hasRotatingPoint: true,
          centeredScaling: false,
          centeredRotation: true,
          touchCornerSize: 24,  // Larger touch area
          borderOpacityWhenMoving: 0.4
        })

        // Set control visibility
        fabricLib.Object.prototype.setControlsVisibility({
          mt: true,  // middle top
          mb: true,  // middle bottom
          ml: true,  // middle left
          mr: true,  // middle right
          tl: true,  // top left
          tr: true,  // top right
          bl: true,  // bottom left
          br: true,  // bottom right
          mtr: true  // rotation control
        })

        console.log('Canvas instance created:', canvas)

        // Convert relative URL to absolute if needed and handle CORS for different environments
        let imageUrl = props.imageUrl

        // Check if we're in AWS environment and dealing with CloudFront URL
        if (imageUrl.includes('cloudfront.net') || imageUrl.includes('amazonaws.com')) {
          // AWS environment - extract S3 key and use image proxy to avoid CORS issues
          let s3Key = ''

          // Extract S3 key from CloudFront URL
          // URL format: https://d38f9rplbkj0f2.cloudfront.net/results/jobId/annotated/filename.png
          const urlParts = imageUrl.split('.cloudfront.net/')
          if (urlParts.length > 1) {
            s3Key = urlParts[1]
          } else if (imageUrl.includes('amazonaws.com/')) {
            // Direct S3 URL format: https://bucket.s3.region.amazonaws.com/key
            const s3Parts = imageUrl.split('.amazonaws.com/')
            if (s3Parts.length > 1) {
              s3Key = s3Parts[1]
            }
          }

          if (s3Key) {
            imageUrl = `https://ginihhv5d6.execute-api.ap-northeast-2.amazonaws.com/prod/images/${s3Key}`
            console.log('Using image proxy for AWS:', imageUrl, 'S3 key:', s3Key)
          } else {
            console.warn('Could not extract S3 key from URL:', imageUrl)
          }
        } else if (imageUrl.startsWith('/api/')) {
          // Local environment
          imageUrl = `http://localhost:8000${imageUrl}`
        }

        console.log('Loading image from:', imageUrl)

        // Create an Image element first (for local environment)
        const imgElement = new Image()
        imgElement.crossOrigin = 'anonymous'

        imgElement.onload = () => {
          console.log('Image loaded successfully:', imgElement.width, 'x', imgElement.height)

          // Create Fabric image from the loaded image element
          const fabricImage = new fabricLib.Image(imgElement)

          // Calculate scale to fit canvas (use more screen space)
          const maxWidth = window.innerWidth * 0.95
          const maxHeight = window.innerHeight * 0.85

          let scale = 1
          if (fabricImage.width > maxWidth) {
            scale = maxWidth / fabricImage.width
          }
          if (fabricImage.height * scale > maxHeight) {
            scale = maxHeight / fabricImage.height
          }

          console.log('Calculated scale:', scale)

          // Set canvas size
          canvas.setWidth(fabricImage.width * scale)
          canvas.setHeight(fabricImage.height * scale)

          // Set image as background (Fabric.js v5+ syntax)
          fabricImage.scaleX = scale
          fabricImage.scaleY = scale
          canvas.backgroundImage = fabricImage

          // Important: Force canvas to recalculate all coordinates
          canvas.renderAll()

          // Multiple recalculations to ensure proper positioning
          setTimeout(() => {
            canvas.calcOffset()
            updateControlsScaling()
            canvas.requestRenderAll()
          }, 0)

          // Additional recalculation after DOM settles
          setTimeout(() => {
            canvas.calcOffset()
            canvas.requestRenderAll()
          }, 100)

          console.log('Image set as background with proper offset')

          // Save initial state
          saveHistory()
        }

        imgElement.onerror = (err) => {
          console.error('Failed to load image:', err)
          console.error('Image URL was:', imageUrl)
        }

        imgElement.src = imageUrl

        // Enable canvas interactions (zoom, pan)
        enableCanvasInteractions()

        // Object modified event
        canvas.on('object:modified', saveHistory)
        canvas.on('object:added', saveHistory)
        canvas.on('object:removed', saveHistory)

        // Selection events
        canvas.on('selection:created', (e) => {
          selectedObject.value = e.selected[0]
          updateTextControls()
        })
        canvas.on('selection:updated', (e) => {
          selectedObject.value = e.selected[0]
          updateTextControls()
        })
        canvas.on('selection:cleared', () => {
          selectedObject.value = null
        })

      } catch (error) {
        console.error('Failed to initialize canvas:', error)
      }
    }

    // Save history for undo/redo
    const saveHistory = () => {
      if (!canvas) return

      const currentState = JSON.stringify(canvas.toJSON())

      // Remove any states after current step
      history.value = history.value.slice(0, historyStep.value + 1)

      // Add new state
      history.value.push(currentState)
      historyStep.value = history.value.length - 1

      updateHistoryButtons()
    }

    // Update undo/redo button states
    const updateHistoryButtons = () => {
      canUndo.value = historyStep.value > 0
      canRedo.value = historyStep.value < history.value.length - 1
    }

    // Undo action
    const undo = () => {
      if (historyStep.value > 0 && canvas) {
        historyStep.value--
        const state = history.value[historyStep.value]
        canvas.loadFromJSON(JSON.parse(state)).then(() => {
          canvas.renderAll()
          updateHistoryButtons()
        })
      }
    }

    // Redo action
    const redo = () => {
      if (historyStep.value < history.value.length - 1 && canvas) {
        historyStep.value++
        const state = history.value[historyStep.value]
        canvas.loadFromJSON(JSON.parse(state)).then(() => {
          canvas.renderAll()
          updateHistoryButtons()
        })
      }
    }

    // Set drawing mode
    const setDrawingMode = (mode) => {
      if (!canvas || !fabricLib) return

      drawingMode.value = mode

      if (mode === 'pen' || mode === 'highlighter' || mode === 'eraser') {
        canvas.isDrawingMode = true

        if (mode === 'pen') {
          canvas.freeDrawingBrush = new fabricLib.PencilBrush(canvas)
          canvas.freeDrawingBrush.color = currentColor.value
          canvas.freeDrawingBrush.width = strokeWidth.value
        } else if (mode === 'highlighter') {
          canvas.freeDrawingBrush = new fabricLib.PencilBrush(canvas)
          // Convert hex to rgba with transparency
          const hexToRgba = (hex, alpha) => {
            const r = parseInt(hex.slice(1, 3), 16)
            const g = parseInt(hex.slice(3, 5), 16)
            const b = parseInt(hex.slice(5, 7), 16)
            return `rgba(${r}, ${g}, ${b}, ${alpha})`
          }
          canvas.freeDrawingBrush.color = hexToRgba(currentColor.value, 0.3)
          canvas.freeDrawingBrush.width = strokeWidth.value * 3
        } else if (mode === 'eraser') {
          // Create eraser brush
          canvas.freeDrawingBrush = new fabricLib.PencilBrush(canvas)
          canvas.freeDrawingBrush.width = strokeWidth.value * 2
          canvas.freeDrawingBrush.color = '#FFFFFF'
          // Set global composite operation for erasing
          canvas.freeDrawingBrush.globalCompositeOperation = 'destination-out'
        }
      } else {
        canvas.isDrawingMode = false
        canvas.selection = true
      }
    }

    // Update text controls based on selected text
    const updateTextControls = () => {
      if (selectedObject.value && selectedObject.value.type === 'i-text') {
        fontSize.value = selectedObject.value.fontSize || 20
        isBold.value = selectedObject.value.fontWeight === 'bold'
        isItalic.value = selectedObject.value.fontStyle === 'italic'
        isUnderline.value = selectedObject.value.underline || false
      }
    }

    // Add text
    const addText = () => {
      if (!canvas || !fabricLib) return

      setDrawingMode('select')
      const center = getCenterPosition()
      const text = new fabricLib.IText('텍스트', {
        left: center.left,
        top: center.top,
        fontSize: fontSize.value,
        fill: currentColor.value,
        fontFamily: 'Noto Sans KR, sans-serif',
        editable: true,
        selectable: true,
        hasControls: true,
        lockScalingFlip: true,
        editingBorderColor: '#667eea',
        cursorColor: currentColor.value,
        cursorDuration: 600,
        cursorDelay: 250
      })

      // Configure text-specific settings
      text.setControlsVisibility({
        mt: false, // Hide middle top
        mb: false, // Hide middle bottom
        ml: false, // Hide middle left
        mr: false  // Hide middle right
      })

      applyObjectSettings(text)
      canvas.add(text)
      canvas.setActiveObject(text)

      // Enter editing mode immediately
      setTimeout(() => {
        text.enterEditing()
        text.selectAll()
      }, 100)

      canvas.renderAll()
    }

    // Get center position of visible canvas area
    const getCenterPosition = () => {
      if (!canvas) return { left: 100, top: 100 }

      const zoom = canvas.getZoom()
      const vpw = canvas.width / zoom
      const vph = canvas.height / zoom
      const viewportTransform = canvas.viewportTransform || [1, 0, 0, 1, 0, 0]

      // Calculate the center of the current viewport
      const centerX = (vpw / 2) - (viewportTransform[4] / zoom)
      const centerY = (vph / 2) - (viewportTransform[5] / zoom)

      return {
        left: Math.max(50, Math.min(centerX - 50, canvas.width - 150)),
        top: Math.max(50, Math.min(centerY - 50, canvas.height - 150))
      }
    }

    // Fix control hit detection on zoom
    const updateControlsScaling = () => {
      if (!canvas || !fabricLib) return

      const zoom = canvas.getZoom()
      const objects = canvas.getObjects()

      // Set global control settings for Fabric.js
      fabricLib.Object.prototype.transparentCorners = false
      fabricLib.Object.prototype.cornerColor = '#667eea'
      fabricLib.Object.prototype.cornerStrokeColor = '#fff'
      fabricLib.Object.prototype.borderColor = '#667eea'
      fabricLib.Object.prototype.cornerSize = 12
      fabricLib.Object.prototype.cornerStyle = 'circle'
      fabricLib.Object.prototype.borderDashArray = [5, 5]

      // Adjust control size based on zoom level
      const baseCornerSize = 12
      const adjustedCornerSize = Math.max(10, Math.min(20, baseCornerSize / Math.sqrt(zoom)))

      objects.forEach(obj => {
        obj.cornerSize = adjustedCornerSize
        obj.borderScaleFactor = 2
        obj.padding = 10
        obj.transparentCorners = false
        obj.cornerColor = '#667eea'
        obj.cornerStrokeColor = '#fff'
        obj.borderColor = '#667eea'

        // Force coordinate recalculation
        obj.setCoords()
      })

      // Force canvas to recalculate all positions
      canvas.calcOffset()
      canvas.renderAll()
    }

    // Apply current zoom control settings to object
    const applyObjectSettings = (obj) => {
      const zoom = canvas.getZoom()
      const baseCornerSize = 12
      const adjustedCornerSize = Math.max(10, Math.min(20, baseCornerSize / Math.sqrt(zoom)))

      obj.set({
        cornerSize: adjustedCornerSize,
        borderScaleFactor: 2,
        padding: 10,
        transparentCorners: false,
        cornerColor: '#667eea',
        cornerStrokeColor: '#ffffff',
        cornerStyle: 'circle',
        borderColor: '#667eea',
        hasRotatingPoint: true,
        rotatingPointOffset: 30
      })

      // Force coordinate recalculation
      obj.setCoords()
      canvas.calcOffset()

      return obj
    }

    // Draw arrow
    const drawArrow = () => {
      if (!canvas || !fabricLib) return

      setDrawingMode('select')
      const center = getCenterPosition()
      const arrow = new fabricLib.Path('M 0 0 L 100 0 L 90 -10 M 100 0 L 90 10', {
        left: center.left,
        top: center.top,
        stroke: currentColor.value,
        strokeWidth: strokeWidth.value,
        fill: 'transparent',
        selectable: true,
        scaleX: 1,
        scaleY: 1
      })
      applyObjectSettings(arrow)
      canvas.add(arrow)
      canvas.setActiveObject(arrow)
      canvas.renderAll()
    }

    // Draw rectangle
    const drawRectangle = () => {
      if (!canvas || !fabricLib) return

      setDrawingMode('select')
      const center = getCenterPosition()
      const rect = new fabricLib.Rect({
        left: center.left,
        top: center.top,
        width: 100,
        height: 100,
        fill: 'transparent',
        stroke: currentColor.value,
        strokeWidth: strokeWidth.value,
        scaleX: 1,
        scaleY: 1
      })
      applyObjectSettings(rect)
      canvas.add(rect)
      canvas.setActiveObject(rect)
      canvas.renderAll()
    }

    // Draw circle
    const drawCircle = () => {
      if (!canvas || !fabricLib) return

      setDrawingMode('select')
      const center = getCenterPosition()
      const circle = new fabricLib.Circle({
        left: center.left,
        top: center.top,
        radius: 50,
        fill: 'transparent',
        stroke: currentColor.value,
        strokeWidth: strokeWidth.value,
        scaleX: 1,
        scaleY: 1
      })
      applyObjectSettings(circle)
      canvas.add(circle)
      canvas.setActiveObject(circle)
      canvas.renderAll()
    }

    // Draw line
    const drawLine = () => {
      if (!canvas || !fabricLib) return

      setDrawingMode('select')
      const center = getCenterPosition()
      const line = new fabricLib.Line([center.left, center.top, center.left + 100, center.top], {
        stroke: currentColor.value,
        strokeWidth: strokeWidth.value,
        scaleX: 1,
        scaleY: 1
      })
      applyObjectSettings(line)
      canvas.add(line)
      canvas.setActiveObject(line)
      canvas.renderAll()
    }

    // Draw triangle
    const drawTriangle = () => {
      if (!canvas || !fabricLib) return

      setDrawingMode('select')
      const center = getCenterPosition()
      const triangle = new fabricLib.Triangle({
        left: center.left,
        top: center.top,
        width: 100,
        height: 100,
        fill: 'transparent',
        stroke: currentColor.value,
        strokeWidth: strokeWidth.value,
        scaleX: 1,
        scaleY: 1
      })
      applyObjectSettings(triangle)
      canvas.add(triangle)
      canvas.setActiveObject(triangle)
      canvas.renderAll()
    }

    // Text editing functions
    const updateTextSize = () => {
      if (selectedObject.value && selectedObject.value.type === 'i-text') {
        selectedObject.value.set('fontSize', parseInt(fontSize.value))
        canvas.renderAll()
        saveHistory()
      }
    }

    const toggleBold = () => {
      if (selectedObject.value && selectedObject.value.type === 'i-text') {
        isBold.value = !isBold.value
        selectedObject.value.set('fontWeight', isBold.value ? 'bold' : 'normal')
        canvas.renderAll()
        saveHistory()
      }
    }

    const toggleItalic = () => {
      if (selectedObject.value && selectedObject.value.type === 'i-text') {
        isItalic.value = !isItalic.value
        selectedObject.value.set('fontStyle', isItalic.value ? 'italic' : 'normal')
        canvas.renderAll()
        saveHistory()
      }
    }

    const toggleUnderline = () => {
      if (selectedObject.value && selectedObject.value.type === 'i-text') {
        isUnderline.value = !isUnderline.value
        selectedObject.value.set('underline', isUnderline.value)
        canvas.renderAll()
        saveHistory()
      }
    }

    // Copy and paste functions
    const copyObject = () => {
      if (!canvas || !selectedObject.value) return

      selectedObject.value.clone((cloned) => {
        copiedObject.value = cloned
      })
    }

    const pasteObject = () => {
      if (!canvas || !copiedObject.value) return

      copiedObject.value.clone((clonedObj) => {
        canvas.discardActiveObject()
        clonedObj.set({
          left: clonedObj.left + 10,
          top: clonedObj.top + 10,
          evented: true,
        })
        canvas.add(clonedObj)
        canvas.setActiveObject(clonedObj)
        canvas.requestRenderAll()
      })
    }

    // Rotate object
    const rotateObject = (angle) => {
      if (!selectedObject.value) return

      const currentAngle = selectedObject.value.angle || 0
      selectedObject.value.rotate(currentAngle + angle)
      canvas.renderAll()
      saveHistory()
    }

    // Layer management
    const bringToFront = () => {
      if (!selectedObject.value) return
      canvas.bringToFront(selectedObject.value)
      canvas.renderAll()
      saveHistory()
    }

    const sendToBack = () => {
      if (!selectedObject.value) return
      canvas.sendToBack(selectedObject.value)
      canvas.renderAll()
      saveHistory()
    }

    // Zoom functions with proper centering
    const zoomIn = () => {
      if (!canvas) return
      const center = canvas.getCenter()
      const newZoom = Math.min(zoomLevel.value * 1.1, 3)
      canvas.zoomToPoint({ x: center.left, y: center.top }, newZoom)
      zoomLevel.value = newZoom
      updateControlsScaling()
      canvas.renderAll()
    }

    const zoomOut = () => {
      if (!canvas) return
      const center = canvas.getCenter()
      const newZoom = Math.max(zoomLevel.value * 0.9, 0.3)
      canvas.zoomToPoint({ x: center.left, y: center.top }, newZoom)
      zoomLevel.value = newZoom
      updateControlsScaling()
      canvas.renderAll()
    }

    const resetZoom = () => {
      if (!canvas) return
      canvas.setViewportTransform([1, 0, 0, 1, 0, 0])
      zoomLevel.value = 1
      updateControlsScaling()
      canvas.renderAll()
    }

    // Enable mouse wheel zoom and pan
    const enableCanvasInteractions = () => {
      if (!canvas) return

      // Mouse wheel zoom
      canvas.on('mouse:wheel', (opt) => {
        const delta = opt.e.deltaY
        let zoom = canvas.getZoom()
        zoom *= 0.999 ** delta
        zoom = Math.min(Math.max(0.3, zoom), 3)
        canvas.zoomToPoint({ x: opt.e.offsetX, y: opt.e.offsetY }, zoom)
        zoomLevel.value = zoom
        updateControlsScaling()
        opt.e.preventDefault()
        opt.e.stopPropagation()
      })

      // Pan with middle mouse button or alt + left click
      let isPanning = false
      let lastPosX = 0
      let lastPosY = 0

      canvas.on('mouse:down', (opt) => {
        const evt = opt.e
        if (evt.altKey || evt.button === 1) { // Alt key or middle mouse button
          isPanning = true
          canvas.selection = false
          lastPosX = evt.clientX
          lastPosY = evt.clientY
        }
      })

      canvas.on('mouse:move', (opt) => {
        if (isPanning) {
          const e = opt.e
          const vpt = canvas.viewportTransform
          vpt[4] += e.clientX - lastPosX
          vpt[5] += e.clientY - lastPosY
          canvas.requestRenderAll()
          lastPosX = e.clientX
          lastPosY = e.clientY
        }
      })

      canvas.on('mouse:up', () => {
        if (isPanning) {
          canvas.setViewportTransform(canvas.viewportTransform)
          isPanning = false
          canvas.selection = true
        }
      })
    }

    // Clear all objects
    const clearAll = () => {
      if (!canvas) return

      if (confirm('모든 편집 내용을 지우시겠습니까?')) {
        const objects = canvas.getObjects()
        objects.forEach(obj => {
          if (obj !== canvas.backgroundImage) {
            canvas.remove(obj)
          }
        })
        canvas.renderAll()
        saveHistory()
      }
    }

    // Delete selected object
    const deleteSelected = () => {
      if (!canvas) return

      const activeObject = canvas.getActiveObject()
      if (activeObject) {
        canvas.remove(activeObject)
        canvas.renderAll()
      }
    }

    // Save edited image
    const save = () => {
      console.log('ImageEditor: save() called')
      if (!canvas) {
        console.error('ImageEditor: canvas is null')
        return
      }

      try {
        const editedData = canvas.toDataURL('image/png')
        console.log('ImageEditor: Generated data URL, length:', editedData.length)
        const saveData = {
          imageIndex: props.imageIndex,
          editedData
        }
        console.log('ImageEditor: Emitting save event with index:', props.imageIndex)
        emit('save', saveData)
        console.log('ImageEditor: save event emitted successfully')

        // Show success feedback
        const saveBtn = document.querySelector('.btn-save')
        if (saveBtn) {
          const originalText = saveBtn.textContent
          saveBtn.textContent = '✅ 저장됨!'
          saveBtn.style.backgroundColor = '#22c55e'
          setTimeout(() => {
            saveBtn.textContent = originalText
            saveBtn.style.backgroundColor = ''
          }, 2000)
        }
      } catch (error) {
        console.error('ImageEditor: Error saving image:', error)
        alert('이미지 저장 중 오류가 발생했습니다.')
      }
    }

    // Close editor
    const close = () => {
      if (canvas) {
        canvas.dispose()
        canvas = null
      }
      emit('close')
    }

    // Watch for isOpen changes
    watch(() => props.isOpen, (newVal) => {
      if (newVal) {
        nextTick(() => {
          initCanvas()
        })
      }
    })

    // Watch for color and width changes
    watch(currentColor, (newColor) => {
      if (canvas && canvas.isDrawingMode && drawingMode.value === 'pen') {
        canvas.freeDrawingBrush.color = newColor
      }
    })

    watch(strokeWidth, (newWidth) => {
      if (canvas && canvas.isDrawingMode) {
        if (drawingMode.value === 'highlighter') {
          canvas.freeDrawingBrush.width = newWidth * 3
        } else if (drawingMode.value === 'eraser') {
          canvas.freeDrawingBrush.width = newWidth * 2
        } else {
          canvas.freeDrawingBrush.width = newWidth
        }
      }
    })

    // Keyboard shortcuts
    const handleKeydown = (e) => {
      if (!props.isOpen) return

      // Check if a text object is being edited
      const activeObject = canvas?.getActiveObject()
      const isEditingText = activeObject &&
                           (activeObject.type === 'i-text' || activeObject.type === 'textbox') &&
                           activeObject.isEditing

      if (e.key === 'Delete' || e.key === 'Backspace') {
        // Don't delete object if editing text
        if (!isEditingText) {
          e.preventDefault()
          deleteSelected()
        }
      } else if (e.ctrlKey || e.metaKey) {
        if (e.key === 'z' && !e.shiftKey) {
          e.preventDefault()
          undo()
        } else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') {
          e.preventDefault()
          redo()
        } else if (e.key === 'c') {
          e.preventDefault()
          copyObject()
        } else if (e.key === 'v') {
          e.preventDefault()
          pasteObject()
        } else if (e.key === 'a') {
          e.preventDefault()
          canvas.discardActiveObject()
          const sel = new fabricLib.ActiveSelection(canvas.getObjects(), {
            canvas: canvas,
          })
          canvas.setActiveObject(sel)
          canvas.requestRenderAll()
        }
      } else if (e.key === 'Escape') {
        setDrawingMode('select')
      }
    }

    onMounted(() => {
      window.addEventListener('keydown', handleKeydown)
      if (props.isOpen) {
        initCanvas()
      }
    })

    onUnmounted(() => {
      window.removeEventListener('keydown', handleKeydown)
      if (canvas) {
        canvas.dispose()
      }
    })

    return {
      currentColor,
      strokeWidth,
      canUndo,
      canRedo,
      drawingMode,
      selectedObject,
      copiedObject,
      fontSize,
      isBold,
      isItalic,
      isUnderline,
      zoomLevel,
      setDrawingMode,
      addText,
      drawArrow,
      drawRectangle,
      drawCircle,
      drawLine,
      drawTriangle,
      updateTextSize,
      toggleBold,
      toggleItalic,
      toggleUnderline,
      copyObject,
      pasteObject,
      rotateObject,
      bringToFront,
      sendToBack,
      zoomIn,
      zoomOut,
      resetZoom,
      clearAll,
      deleteSelected,
      undo,
      redo,
      save,
      close
    }
  }
}
</script>

<style scoped>
.editor-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.editor-container {
  background: white;
  border-radius: 0;
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  box-shadow: none;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8f9fa;
}

.editor-header h3 {
  margin: 0;
  font-size: 1rem;
  color: #2d3748;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #718096;
  padding: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 4px;
  transition: background 0.2s;
}

.close-btn:hover {
  background: #f7fafc;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #fafafa;
  background: #f8fafc;
  flex-wrap: wrap;
}

.tool-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tool-label {
  font-size: 12px;
  color: #4a5568;
  margin: 0 4px;
  font-weight: 500;
}

.editor-toolbar button {
  width: 28px;
  height: 28px;
  border: 1px solid #cbd5e0;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  position: relative;
}

.editor-toolbar button:hover:not(:disabled) {
  background: #edf2f7;
  border-color: #a0aec0;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.editor-toolbar button.active {
  background: #667eea;
  color: white;
  border-color: #667eea;
}

.editor-toolbar button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.separator {
  width: 1px;
  height: 28px;
  background: #cbd5e0;
  margin: 0 4px;
}

.editor-toolbar input[type="color"] {
  width: 32px;
  height: 32px;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  cursor: pointer;
}

.editor-toolbar input[type="range"] {
  width: 80px;
  height: 4px;
  outline: none;
  -webkit-appearance: none;
  background: #e2e8f0;
  border-radius: 2px;
}

.editor-toolbar input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: #667eea;
  border-radius: 50%;
  cursor: pointer;
}

.editor-toolbar input[type="range"]::-moz-range-thumb {
  width: 16px;
  height: 16px;
  background: #667eea;
  border-radius: 50%;
  cursor: pointer;
  border: none;
}

.width-indicator, .zoom-indicator {
  font-size: 11px;
  color: #718096;
  min-width: 40px;
  text-align: center;
}

.zoom-controls {
  margin-left: auto;
}

.canvas-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
  overflow: auto;
  padding: 10px;
  position: relative;
}

#fabric-canvas {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  max-width: 100%;
  max-height: calc(100% - 30px);
}

.canvas-help {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.9);
  padding: 6px 12px;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  color: #4a5568;
  font-size: 12px;
  z-index: 10;
}

.editor-footer {
  padding: 10px 15px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  background: #f8f9fa;
}

.btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
}

.btn-save {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-save:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-cancel {
  background: #e5e7eb;
  color: #4a5568;
}

.btn-cancel:hover {
  background: #cbd5e0;
}
</style>