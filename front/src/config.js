// API endpoint configuration
const isProduction = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1'
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

// AWS API Gateway endpoint for production
const AWS_API_URL = 'https://ginihhv5d6.execute-api.ap-northeast-2.amazonaws.com/prod'

// Local FastAPI endpoint for development
const LOCAL_API_URL = 'http://localhost:8000/api/v1'

export default {
  API_URL: isLocal ? LOCAL_API_URL : AWS_API_URL,
  isProduction,
  isLocal
}
