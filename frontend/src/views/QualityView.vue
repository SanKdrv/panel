<template>
  <div>
    <div class="page-title">
      <i class="bi bi-patch-check me-2 text-primary"></i>Оценка качества генераций
    </div>

    <ul class="nav nav-tabs mb-4">
      <li class="nav-item">
        <a
          class="nav-link"
          :class="{ active: tab === 'run' }"
          href="#"
          @click.prevent="tab = 'run'"
        >
          <i class="bi bi-play-fill me-1"></i>Запуск оценки
        </a>
      </li>
      <li class="nav-item">
        <a
          class="nav-link"
          :class="{ active: tab === 'gold' }"
          href="#"
          @click.prevent="tab = 'gold'"
        >
          <i class="bi bi-book me-1"></i>Эталоны (Gold dataset)
        </a>
      </li>
      <li class="nav-item">
        <a
          class="nav-link"
          :class="{ active: tab === 'history' }"
          href="#"
          @click.prevent="tab = 'history'"
        >
          <i class="bi bi-graph-up me-1"></i>Тренд
        </a>
      </li>
    </ul>

    <!-- ===== RUN TAB ===== -->
    <div v-show="tab === 'run'">
      <RunSection />
    </div>

    <!-- ===== GOLD TAB ===== -->
    <div v-show="tab === 'gold'">
      <GoldSection />
    </div>

    <!-- ===== HISTORY TAB ===== -->
    <div v-show="tab === 'history'">
      <div class="d-flex align-items-center justify-content-between mb-3">
        <div class="fw-semibold">Тренд метрик качества</div>
        <select
          v-model.number="historyRange"
          class="form-select form-select-sm"
          style="width: 140px"
        >
          <option :value="3600">1 час</option>
          <option :value="21600">6 часов</option>
          <option :value="86400">24 часа</option>
          <option :value="604800">7 дней</option>
        </select>
      </div>

      <div class="card border-0 shadow-sm p-4 mb-3">
        <div class="small text-muted mb-2">
          Faithfulness · Answer Relevance · Context Precision (0…1)
        </div>
        <LineChart :series="qualitySeries" :y-max="1" :y-min="0" />
      </div>

      <div class="card border-0 shadow-sm p-4">
        <div class="small text-muted mb-2">TPS, токенов/с</div>
        <LineChart :series="tpsSeries" unit=" т/с" :y-min="0" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { qualityApi } from '../api/endpoints'
import LineChart from '../components/LineChart.vue'
import RunSection from '../components/quality/RunSection.vue'
import GoldSection from '../components/quality/GoldSection.vue'

const tab = ref('run')
const historyRange = ref(86400)
const historyData = ref({}) // map metric_name -> points[]

const METRIC_LABELS = {
  rag_faithfulness: 'Faithfulness',
  rag_answer_relevance: 'Answer Relevance',
  rag_context_precision: 'Context Precision',
  rag_tps: 'TPS',
}

const QUALITY_KEYS = [
  'rag_faithfulness',
  'rag_answer_relevance',
  'rag_context_precision',
]

const qualitySeries = computed(() =>
  QUALITY_KEYS.map((k) => ({
    label: METRIC_LABELS[k],
    points: historyData.value[k] || [],
  })),
)

const tpsSeries = computed(() => [
  { label: 'TPS', points: historyData.value.rag_tps || [] },
])

async function loadHistory() {
  try {
    const step = Math.max(60, Math.floor(historyRange.value / 200))
    const data = await qualityApi.history(historyRange.value, step)
    historyData.value = data.metrics || {}
  } catch (e) {
    /* ignore */
  }
}

watch(historyRange, loadHistory)
watch(tab, (v) => {
  if (v === 'history') loadHistory()
})

onMounted(loadHistory)
</script>
