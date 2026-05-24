<template>
  <div>
    <div class="d-flex align-items-center justify-content-between mb-4">
      <div class="page-title mb-0">
        <i class="bi bi-bar-chart-line me-2 text-primary"></i>Мониторинг серверов
      </div>
      <div class="d-flex align-items-center gap-2">
        <select v-model.number="rangeSeconds" class="form-select form-select-sm" style="width: 140px">
          <option :value="600">10 минут</option>
          <option :value="3600">1 час</option>
          <option :value="21600">6 часов</option>
          <option :value="86400">24 часа</option>
        </select>
        <button class="btn btn-outline-secondary btn-sm" @click="load">
          <i class="bi bi-arrow-clockwise"></i>
        </button>
        <a
          v-if="grafanaUrl"
          :href="grafanaUrl"
          target="_blank"
          rel="noopener"
          class="btn btn-outline-primary btn-sm"
        >
          <i class="bi bi-box-arrow-up-right me-1"></i>Открыть Grafana
        </a>
      </div>
    </div>

    <div v-if="loading" class="text-muted mb-3">
      <i class="bi bi-arrow-repeat me-2"></i>Загрузка...
    </div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div class="row g-4">
      <div class="col-md-6">
        <div class="card border-0 shadow-sm p-3">
          <div class="fw-semibold mb-2">CPU, %</div>
          <LineChart :series="cpuSeries" unit="%" :y-max="100" />
        </div>
      </div>
      <div class="col-md-6">
        <div class="card border-0 shadow-sm p-3">
          <div class="fw-semibold mb-2">RAM, %</div>
          <LineChart :series="ramSeries" unit="%" :y-max="100" />
        </div>
      </div>
      <div class="col-md-6">
        <div class="card border-0 shadow-sm p-3">
          <div class="fw-semibold mb-2">Disk, %</div>
          <LineChart :series="diskSeries" unit="%" :y-max="100" />
        </div>
      </div>
      <div class="col-md-6">
        <div class="card border-0 shadow-sm p-3">
          <div class="fw-semibold mb-2">Текущие значения</div>
          <table class="table table-sm mb-0">
            <thead>
              <tr>
                <th>Сервер</th>
                <th class="text-end">CPU</th>
                <th class="text-end">RAM</th>
                <th class="text-end">Disk</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in latestTable" :key="row.label">
                <td>{{ row.label }}</td>
                <td class="text-end">{{ fmt(row.cpu) }}</td>
                <td class="text-end">{{ fmt(row.ram) }}</td>
                <td class="text-end">{{ fmt(row.disk) }}</td>
              </tr>
              <tr v-if="!latestTable.length">
                <td colspan="4" class="text-muted text-center">нет данных</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { monitoringApi, systemApi } from '../api/endpoints'
import LineChart from '../components/LineChart.vue'

const rangeSeconds = ref(3600)
const loading = ref(false)
const error = ref('')
const data = ref({ metrics: { cpu: [], ram: [], disk: [] } })
const grafanaUrl = ref('')

let pollTimer = null

const cpuSeries  = computed(() => data.value.metrics.cpu  || [])
const ramSeries  = computed(() => data.value.metrics.ram  || [])
const diskSeries = computed(() => data.value.metrics.disk || [])

const latestTable = computed(() => {
  const labels = new Set()
  for (const m of ['cpu', 'ram', 'disk']) {
    for (const s of data.value.metrics[m] || []) labels.add(s.label)
  }
  return [...labels].map((label) => {
    const last = (arr) => {
      const s = arr.find((x) => x.label === label)
      if (!s || !s.points.length) return null
      return s.points[s.points.length - 1][1]
    }
    return {
      label,
      cpu: last(cpuSeries.value),
      ram: last(ramSeries.value),
      disk: last(diskSeries.value),
    }
  })
})

function fmt(v) {
  return v == null ? '—' : `${v.toFixed(1)}%`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const step = Math.max(15, Math.floor(rangeSeconds.value / 120))
    data.value = await monitoringApi.servers(rangeSeconds.value, step)
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка'
  } finally {
    loading.value = false
  }
}

watch(rangeSeconds, () => load())

onMounted(async () => {
  try {
    const dash = await systemApi.dashboard()
    grafanaUrl.value = dash.grafana_external_url || ''
  } catch (e) {
    /* ignore */
  }
  await load()
  pollTimer = setInterval(load, 30000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>
