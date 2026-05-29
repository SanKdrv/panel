import api from './client'

export const authApi = {
  login: (username, password) =>
    api.post('/auth/login', { username, password }).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
}

export const systemApi = {
  health: () => api.get('/system/health').then((r) => r.data),
  dashboard: () => api.get('/system/dashboard').then((r) => r.data),
}

export const documentsApi = {
  listResourceTypes: () =>
    api.get('/documents/resource-types').then((r) => r.data),
  createResourceType: (name) =>
    api.post('/documents/resource-types', { name }).then((r) => r.data),
  upload: (payload) => api.post('/documents', payload).then((r) => r.data),
  importEmail: (id) =>
    api.post('/documents/import/email', { id }).then((r) => r.data),
  vectorDbStatus: () =>
    api.get('/documents/vector-db/status').then((r) => r.data),
}

export const promptsApi = {
  list: () => api.get('/prompts').then((r) => r.data),
  get: (leadType) => api.get(`/prompts/${leadType}`).then((r) => r.data),
  update: (leadType, prompt) =>
    api.put('/prompts', { lead_type: leadType, prompt }).then((r) => r.data),
}

export const generateApi = {
  trigger: (leadId, type) =>
    api.post('/generate', { lead_id: leadId, type }).then((r) => r.data),
  status: (token) =>
    api.get(`/generate/status/${token}`).then((r) => r.data),
}

export const leadsApi = {
  card: (leadId) => api.get(`/leads/${leadId}`).then((r) => r.data),
  byEmail: (email) =>
    api.get('/leads/by-email', { params: { email } }).then((r) => r.data),
}

export const qualityApi = {
  // CRUD gold dataset
  listGold: () => api.get('/quality/gold').then((r) => r.data),
  createGold: (stage, reference) =>
    api.post('/quality/gold', { stage, reference }).then((r) => r.data),
  updateGold: (id, payload) =>
    api.put(`/quality/gold/${id}`, payload).then((r) => r.data),
  deleteGold: (id) => api.delete(`/quality/gold/${id}`).then((r) => r.data),

  // Lead picker
  // Async lead search: возвращает search_id, дальше polling
  startLeadsSearch: (minId, maxId, n, minActions = 1) =>
    api
      .post('/quality/leads/search', {
        min_id: minId,
        max_id: maxId,
        n,
        min_actions: minActions,
      })
      .then((r) => r.data),
  getLeadsSearch: (searchId) =>
    api.get(`/quality/leads/search/${searchId}`).then((r) => r.data),
  cancelLeadsSearch: (searchId) =>
    api.post(`/quality/leads/search/${searchId}/cancel`).then((r) => r.data),

  // Tasks
  startTask: (leadIds, stages = null) =>
    api
      .post('/quality/tasks', { lead_ids: leadIds, stages })
      .then((r) => r.data),
  taskStatus: (taskId) =>
    api.get(`/quality/tasks/${taskId}`).then((r) => r.data),
  cancelTask: (taskId) =>
    api.post(`/quality/tasks/${taskId}/cancel`).then((r) => r.data),
  listTasks: (limit = 50) =>
    api.get('/quality/tasks', { params: { limit } }).then((r) => r.data),

  latest: () => api.get('/quality/latest').then((r) => r.data),
  startRegen: (taskId, pairs) =>
    api.post('/quality/regenerate', { task_id: taskId, pairs }).then((r) => r.data),
  getRegenStatus: (regenId) =>
    api.get(`/quality/regenerate/${regenId}`).then((r) => r.data),
  history: (rangeSeconds = 86400, stepSeconds = 300) =>
    api
      .get('/monitoring/quality/history', {
        params: { range: rangeSeconds, step: stepSeconds },
      })
      .then((r) => r.data),
}

export const monitoringApi = {
  servers: (rangeSeconds = 3600, stepSeconds = 30) =>
    api
      .get('/monitoring/servers', {
        params: { range: rangeSeconds, step: stepSeconds },
      })
      .then((r) => r.data),
}
