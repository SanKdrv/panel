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
}

export const qualityApi = {
  evaluate: () => api.post('/quality/evaluate').then((r) => r.data),
  latest: () => api.get('/quality/latest').then((r) => r.data),
}
