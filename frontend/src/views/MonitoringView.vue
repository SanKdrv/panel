<template>
  <div>
    <div class="page-title">
      <i class="bi bi-bar-chart-line me-2 text-primary"></i>Мониторинг серверов
    </div>

    <div v-if="embedUrl">
      <iframe
        :src="embedUrl"
        width="100%"
        height="500"
        frameborder="0"
        class="rounded shadow-sm"
      ></iframe>
      <div class="mt-3 small">
        <a v-if="dashboardUrl" :href="dashboardUrl" target="_blank">
          <i class="bi bi-box-arrow-up-right me-1"></i>Открыть дашборд в Grafana
        </a>
      </div>
    </div>

    <div v-else class="grafana-placeholder">
      <i class="bi bi-bar-chart-fill" style="font-size: 3rem; margin-bottom: 1rem; color: #adb5bd"></i>
      <div class="fw-semibold">Grafana Dashboard</div>
      <div class="small mt-1">CPU / RAM / Disk / Network — три сервера в реальном времени</div>
      <div class="small text-muted mt-1">
        GRAFANA_EMBED_URL не задан в .env
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { systemApi } from '../api/endpoints'

const embedUrl = ref('')
const dashboardUrl = ref('')

onMounted(async () => {
  try {
    const data = await systemApi.dashboard()
    embedUrl.value = data.grafana_embed_url || ''
    dashboardUrl.value = data.grafana_dashboard_url || ''
  } catch (e) {
    /* ignore */
  }
})
</script>
