<template>
  <router-view />
</template>

<script>
export default {
  name: 'App'
}
</script>

<style>
/* Global styles - moved from original App.vue */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.header {
  text-align: center;
  color: white;
  margin-bottom: 40px;
}

.header h1 {
  font-size: 36px;
  margin-bottom: 10px;
}

.header p {
  font-size: 18px;
  opacity: 0.9;
}

.upload-section {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
  margin-bottom: 30px;
}

.upload-area {
  border: 2px dashed #cbd5e0;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  transition: all 0.3s ease;
}

.upload-area.dragover {
  border-color: #667eea;
  background: #f0f4ff;
}

.upload-label {
  cursor: pointer;
  display: block;
}

.upload-label input[type="file"] {
  display: none;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 15px;
}

.upload-text {
  font-size: 18px;
  color: #4a5568;
  margin-bottom: 8px;
}

.upload-hint {
  font-size: 14px;
  color: #718096;
}

.file-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  padding: 15px;
  background: #f7fafc;
  border-radius: 8px;
}

.file-name {
  font-weight: 600;
  color: #2d3748;
}

.file-size {
  font-size: 14px;
  color: #718096;
  margin-top: 4px;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-top: 20px;
}

.btn {
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-danger {
  background: #f56565;
  color: white;
  padding: 8px 16px;
  font-size: 14px;
}

.btn-danger:hover {
  background: #e53e3e;
}

.loading {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: white;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.processing-time {
  color: #718096;
  font-size: 14px;
}

.error-message {
  margin-top: 20px;
  padding: 15px;
  background: #fed7d7;
  color: #c53030;
  border-radius: 8px;
}

.success-message {
  margin-top: 20px;
  padding: 15px;
  background: #c6f6d5;
  color: #22543d;
  border-radius: 8px;
}

.results-section {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
}

.results-title {
  font-size: 24px;
  font-weight: 600;
  color: #2d3748;
}

.results-count {
  background: #edf2f7;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 14px;
  color: #4a5568;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
}

.image-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.image-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
}

.image-wrapper {
  aspect-ratio: 4/3;
  background: #f7fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.image-wrapper img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.image-info {
  padding: 15px;
}

.image-title {
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 8px;
}

.image-meta {
  display: flex;
  gap: 8px;
}

.badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.badge-original {
  background: #e6fffa;
  color: #047481;
}

.badge-annotated {
  background: #fef5e7;
  color: #8b6914;
}
</style>