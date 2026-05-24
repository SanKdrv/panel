<template>
  <div class="login-overlay">
    <div class="login-card">
      <div class="brand-logo"><i class="bi bi-cpu me-2"></i>RAG Admin</div>
      <div class="brand-sub">Панель управления RAG-системой</div>
      <form @submit.prevent="doLogin">
        <div class="mb-3">
          <label class="form-label fw-semibold">Логин</label>
          <div class="input-group">
            <span class="input-group-text"><i class="bi bi-person"></i></span>
            <input
              v-model="username"
              type="text"
              class="form-control"
              placeholder="admin"
              autofocus
            />
          </div>
        </div>
        <div class="mb-4">
          <label class="form-label fw-semibold">Пароль</label>
          <div class="input-group">
            <span class="input-group-text"><i class="bi bi-lock"></i></span>
            <input
              v-model="password"
              type="password"
              class="form-control"
              placeholder="••••••••"
            />
          </div>
          <div class="form-text text-muted">
            Учётные данные задаются в <code>.env</code>
          </div>
        </div>
        <button type="submit" class="btn btn-primary w-100" :disabled="loading">
          <i class="bi bi-box-arrow-in-right me-2"></i>
          {{ loading ? 'Вход...' : 'Войти' }}
        </button>
        <div v-if="error" class="alert alert-danger mt-3 py-2" role="alert">
          <i class="bi bi-exclamation-triangle me-1"></i>{{ error }}
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { authApi } from '../api/endpoints'
import { useAuth } from '../store/auth'

const router = useRouter()
const route = useRoute()
const { setSession } = useAuth()

const username = ref('admin')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function doLogin() {
  error.value = ''
  loading.value = true
  try {
    const data = await authApi.login(username.value, password.value)
    setSession(data.access_token, username.value)
    const redirect = route.query.redirect || '/dashboard'
    router.push(redirect)
  } catch (e) {
    error.value =
      e?.response?.data?.detail || 'Неверный логин или пароль'
  } finally {
    loading.value = false
  }
}
</script>
