import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../store/auth'

import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import KnowledgeView from '../views/KnowledgeView.vue'
import PromptsView from '../views/PromptsView.vue'
import GenerateView from '../views/GenerateView.vue'
import LeadsView from '../views/LeadsView.vue'
import MonitoringView from '../views/MonitoringView.vue'
import QualityView from '../views/QualityView.vue'

const routes = [
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: DashboardView },
  { path: '/knowledge', name: 'knowledge', component: KnowledgeView },
  { path: '/prompts', name: 'prompts', component: PromptsView },
  { path: '/generate', name: 'generate', component: GenerateView },
  { path: '/leads', name: 'leads', component: LeadsView },
  { path: '/monitoring', name: 'monitoring', component: MonitoringView },
  { path: '/quality', name: 'quality', component: QualityView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const { isAuthenticated } = useAuth()
  if (!to.meta.public && !isAuthenticated.value) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && isAuthenticated.value) {
    return { name: 'dashboard' }
  }
})

export default router
