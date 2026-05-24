<template>
  <nav id="sidebar">
    <div class="brand"><i class="bi bi-cpu"></i> RAG Admin</div>
    <div
      class="px-3 py-2 border-bottom d-flex align-items-center justify-content-between"
      style="font-size: 0.8rem; color: #6c757d"
    >
      <span><i class="bi bi-person-circle me-1"></i>{{ username || 'admin' }}</span>
      <a
        href="#"
        @click.prevent="onLogout"
        class="text-danger"
        style="font-size: 0.8rem; text-decoration: none"
      >
        <i class="bi bi-box-arrow-right"></i> Выйти
      </a>
    </div>
    <ul class="nav flex-column pt-2">
      <li class="nav-item">
        <router-link class="nav-link" to="/dashboard">
          <i class="bi bi-grid-1x2"></i>Дашборд
        </router-link>
      </li>
      <li class="nav-item">
        <router-link class="nav-link" to="/knowledge">
          <i class="bi bi-journal-text"></i>База знаний
        </router-link>
      </li>
      <li class="nav-item">
        <router-link class="nav-link" to="/prompts">
          <i class="bi bi-chat-left-text"></i>Промпты
        </router-link>
      </li>
      <li class="nav-item">
        <router-link class="nav-link" to="/generate">
          <i class="bi bi-lightning"></i>Генерация
        </router-link>
      </li>
      <li class="nav-item">
        <router-link class="nav-link" to="/leads">
          <i class="bi bi-person-lines-fill"></i>Лиды
        </router-link>
      </li>
      <li class="nav-item">
        <router-link class="nav-link" to="/monitoring">
          <i class="bi bi-bar-chart-line"></i>Мониторинг
        </router-link>
      </li>
      <li class="nav-item">
        <router-link class="nav-link" to="/quality">
          <i class="bi bi-patch-check"></i>Оценка качества
        </router-link>
      </li>
    </ul>
  </nav>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuth } from '../store/auth'

const router = useRouter()
const { username, logout } = useAuth()

function onLogout() {
  logout()
  router.push('/login')
}
</script>
