<template>
  <div>
    <div class="page-title">
      <i class="bi bi-grid-1x2 me-2 text-primary"></i>Дашборд состояния системы
    </div>

    <div class="row g-3 mb-4">
      <div class="col-md-3">
        <div class="card border-0 shadow-sm text-center p-3">
          <div class="text-muted small">Статус системы</div>
          <div class="fw-bold fs-5 mt-1" :class="statusClass">
            <i class="bi" :class="statusIcon"></i> {{ overallStatus }}
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card border-0 shadow-sm text-center p-3">
          <div class="text-muted small">Uptime</div>
          <div class="fw-bold fs-5 mt-1">{{ uptimeFormatted }}</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card border-0 shadow-sm text-center p-3">
          <div class="text-muted small">Глубина очереди</div>
          <div class="fw-bold fs-5 mt-1">{{ queueDepth }} задач</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card border-0 shadow-sm text-center p-3">
          <div class="text-muted small">Последняя проверка</div>
          <div class="fw-bold fs-5 mt-1">{{ lastCheck }}</div>
        </div>
      </div>
    </div>

    <div class="row g-3">
      <div
        v-for="comp in components"
        :key="comp.name"
        class="col-md-4"
      >
        <div class="comp-card">
          <div class="d-flex justify-content-between align-items-start">
            <div>
              <div class="comp-name">{{ comp.title }}</div>
              <div class="comp-latency">
                <template v-if="comp.queue_depth !== null">
                  Queue depth: {{ comp.queue_depth }}
                </template>
                <template v-else-if="comp.latency_ms !== null">
                  Задержка: {{ comp.latency_ms }} мс
                </template>
                <template v-else>—</template>
              </div>
            </div>
            <span class="badge rounded-pill px-3 py-1" :class="badgeFor(comp.status)">
              {{ comp.status }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger mt-3">
      Не удалось загрузить состояние: {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { systemApi } from '../api/endpoints'

const COMPONENT_LABELS = {
  staging_area: 'Staging Area',
  vector_db: 'Векторная БД (Qdrant)',
  queue: 'Очередь сообщений',
  llm_service: 'LLM-сервис',
  embedding_service: 'Embedding-сервис',
  redis: 'Redis',
}

const health = ref(null)
const error = ref('')
const lastCheck = ref('—')
let pollTimer = null

const overallStatus = computed(() => health.value?.status || 'unknown')
const statusClass = computed(() => {
  const s = overallStatus.value
  if (s === 'healthy') return 'text-success'
  if (s === 'unhealthy') return 'text-danger'
  return 'text-muted'
})
const statusIcon = computed(() => {
  const s = overallStatus.value
  if (s === 'healthy') return 'bi-check-circle-fill'
  if (s === 'unhealthy') return 'bi-x-circle-fill'
  return 'bi-question-circle'
})

const uptimeFormatted = computed(() => {
  const s = health.value?.uptime_seconds
  if (!s) return '—'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return `${h} ч ${String(m).padStart(2, '0')} мин`
})

const queueDepth = computed(
  () => health.value?.components?.queue?.queue_depth ?? '—',
)

const components = computed(() => {
  const comps = health.value?.components || {}
  return Object.entries(comps).map(([key, c]) => ({
    name: key,
    title: COMPONENT_LABELS[key] || key,
    status: c.status,
    latency_ms: c.latency_ms ?? null,
    queue_depth: c.queue_depth ?? null,
  }))
})

function badgeFor(status) {
  if (['ready', 'healthy', 'available'].includes(status)) return 'badge-ready'
  if (['updating', 'processing', 'queued'].includes(status)) return 'badge-updating'
  return 'badge-unhealthy'
}

async function load() {
  try {
    const data = await systemApi.dashboard()
    health.value = data.health
    lastCheck.value = new Date().toLocaleTimeString('ru-RU')
    error.value = ''
  } catch (e) {
    error.value = e?.message || String(e)
  }
}

onMounted(() => {
  load()
  pollTimer = setInterval(load, 15000)
})
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>
