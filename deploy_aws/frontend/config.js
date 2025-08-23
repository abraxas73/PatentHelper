// AWS API Gateway configuration
const config = {
  development: {
    API_URL: 'http://localhost:8000/api/v1',
    DOMAIN: 'localhost:5173'
  },
  production: {
    API_URL: 'https://ginihhv5d6.execute-api.ap-northeast-2.amazonaws.com/prod',
    DOMAIN: 'd38f9rplbkj0f2.cloudfront.net'
  }
};

export default config[import.meta.env.MODE] || config.development;