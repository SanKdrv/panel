<template>
  <div>
    <div class="page-title">
      <i class="bi bi-patch-check me-2 text-primary"></i>Оценка качества генераций
    </div>

    <div class="d-flex align-items-center gap-3 mb-4">
      <button class="btn btn-primary" :disabled="running" @click="runEvaluation">
        <i class="bi bi-play-fill me-2"></i>
        {{ running ? 'Идёт оценка...' : 'Запустить оценку' }}
      </button>
      <span v-if="lastRun" class="text-muted small">
        Последний запуск: {{ formatTime(lastRun) }}
      </span>
    </div>

    <div v-if="metrics" class="row g-3 mb-4">
      <div class="col-md-3">
        <MetricCard
          label="Faithfulness"
          :value="metrics.faithfulness"
          :odz="odz.faithfulness"
          unit=""
          higherIsBetter
        />
      </div>
      <div class="col-md-3">
        <MetricCard
          label="Answer Relevance"
          :value="metrics.answer_relevance"
          :odz="odz.answer_relevance"
          unit=""
          higherIsBetter
        />
      </div>
      <div class="col-md-3">
        <MetricCard
          label="Context Precision"
          :value="metrics.context_precision"
          :odz="odz.context_precision"
          unit=""
          higherIsBetter
        />
      </div>
      <div class="col-md-3">
        <MetricCard
          label="TPS"
          :value="metrics.tps"
          :odz="odz.tps"
          unit=" т/с"
          higherIsBetter
        />
      </div>
    </div>

    <div v-if="metrics" class="card border-0 shadow-sm">
      <div class="card-body">
        <table class="table table-bordered mb-0">
          <thead class="table-light">
            <tr>
              <th>Метрика</th>
              <th>Метод измерения</th>
              <th>ОДЗ</th>
              <th>Значение</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in tableRows" :key="row.name">
              <td>{{ row.name }}</td>
              <td>{{ row.method }}</td>
              <td>≥ {{ row.odz }}{{ row.unit }}</td>
              <td>{{ row.value }}{{ row.unit }}</td>
              <td :class="row.pass ? 'status-pass' : 'status-fail'">
                <i
                  class="bi"
                  :class="row.pass ? 'bi-check-circle-fill' : 'bi-x-circle-fill'"
                ></i>
                {{ row.pass ? ' Пройдено' : ' Не пройдено' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div
      v-if="metrics"
      class="alert mt-3 d-flex align-items-center gap-2"
      :class="allPass ? 'alert-success' : 'alert-warning'"
      role="alert"
    >
      <i class="bi fs-5" :class="allPass ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill'"></i>
      <div v-if="allPass">
        Все метрики соответствуют установленным требованиям. Система готова к эксплуатации.
      </div>
      <div v-else>
        Часть метрик не достигла ОДЗ — рекомендуется пересмотреть промпты или
        обновить базу знаний.
      </div>
    </div>

    <div v-if="!metrics && !running" class="text-muted">
      Запустите оценку, чтобы увидеть метрики.
    </div>

    <div v-if="error" class="alert alert-danger mt-3">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { qualityApi } from '../api/endpoints'
import MetricCard from '../components/MetricCard.vue'

const running = ref(false)
const error = ref('')
const metrics = ref(null)
const odz = ref({
  faithfulness: 0.8,
  answer_relevance: 0.75,
  context_precision: 0.7,
  tps: 5.0,
})
const lastRun = ref('')

const tableRows = computed(() => {
  if (!metrics.value) return []
  const rows = [
    {
      name: 'Faithfulness',
      method: 'LLM-as-judge (Ollama)',
      value: metrics.value.faithfulness,
      odz: odz.value.faithfulness,
      unit: '',
    },
    {
      name: 'Answer Relevance',
      method: 'Косинусное сходство эмбеддингов',
      value: metrics.value.answer_relevance,
      odz: odz.value.answer_relevance,
      unit: '',
    },
    {
      name: 'Context Precision',
      method: 'Доля ключевых слов эталона в ответе',
      value: metrics.value.context_precision,
      odz: odz.value.context_precision,
      unit: '',
    },
    {
      name: 'TPS',
      method: 'Токенов/с при вызовах RAG API',
      value: metrics.value.tps,
      odz: odz.value.tps,
      unit: ' т/с',
    },
  ]
  rows.forEach((r) => (r.pass = r.value >= r.odz))
  return rows
})

const allPass = computed(() => tableRows.value.every((r) => r.pass))

async function loadLatest() {
  try {
    const data = await qualityApi.latest()
    if (data.metrics) {
      metrics.value = data.metrics
      if (data.odz) odz.value = data.odz
      lastRun.value = data.finished_at || ''
    }
  } catch (e) {
    /* ignore */
  }
}

async function runEvaluation() {
  running.value = true
  error.value = ''
  try {
    await qualityApi.evaluate()
    await loadLatest()
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка'
  } finally {
    running.value = false
  }
}

function formatTime(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

onMounted(loadLatest)
</script>
