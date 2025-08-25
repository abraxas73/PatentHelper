import { createRouter, createWebHashHistory } from 'vue-router'
import MainView from './views/MainView.vue'
import JobResultView from './views/JobResultView.vue'

const routes = [
  {
    path: '/',
    name: 'main',
    component: MainView
  },
  {
    path: '/job/:jobId',
    name: 'job-result',
    component: JobResultView,
    props: true
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router