<template>
  <div>
    <!-- ===== STEP 1: form ===== -->
    <div v-if="step === 'form'" class="card border-0 shadow-sm p-4" style="max-width: 720px">
      <div class="fw-semibold mb-3">Поиск тестовых лидов</div>
      <div class="row g-2 mb-3">
        <div class="col-md-3">
          <label class="form-label small text-muted">Min lead_id</label>
          <input v-model.number="form.min" type="number" class="form-control" />
        </div>
        <div class="col-md-3">
          <label class="form-label small text-muted">Max lead_id</label>
          <input v-model.number="form.max" type="number" class="form-control" />
        </div>
        <div class="col-md-3">
          <label class="form-label small text-muted">Сколько лидов</label>
          <input v-model.number="form.n" type="number" class="form-control" />
        </div>
        <div class="col-md-3">
          <label class="form-label small text-muted">
            Min actions
            <i class="bi bi-info-circle" title="Минимальное число цифровых следов для отбора лида"></i>
          </label>
          <input v-model.number="form.minActions" type="number" min="1" class="form-control" />
        </div>
      </div>
      <p class="small text-muted mb-3">
        Выберем случайные лид-id из диапазона, проверим что у них есть как
        минимум <strong>{{ form.minActions }}</strong>
        action{{ form.minActions === 1 ? '' : 's' }} в RAG-системе, и
        предложим выбрать кого включить в прогон.
      </p>
      <button class="btn btn-primary" :disabled="finding" @click="findLeads">
        <i class="bi bi-search me-2"></i>
        {{ finding ? 'Поиск...' : 'Найти лидов' }}
      </button>
      <div v-if="error" class="alert alert-danger mt-3 py-2 small">{{ error }}</div>
    </div>

    <!-- ===== STEP 2: pick leads ===== -->
    <div v-if="step === 'pick'" class="card border-0 shadow-sm p-4" style="max-width: 720px">
      <div class="fw-semibold mb-2">
        Найдено {{ foundLeads.length }} валидных
        <span v-if="foundLeads.length < form.n" class="text-warning">
          (запрашивали {{ form.n }})
        </span>
      </div>
      <p class="small text-muted mb-3">
        Отметьте тех, на ком провести прогон. Каждый лид прогонится по
        {{ goldCount }} эталонам — итого {{ selectedLeads.length * goldCount }}
        генераций. RAG-генерация занимает ~4 минуты, ориентируйтесь на
        ≈{{ Math.ceil((selectedLeads.length * goldCount * 4)) }} минут.
      </p>
      <div class="mb-3">
        <button class="btn btn-sm btn-outline-secondary me-2" @click="selectAll(true)">
          Выбрать всех
        </button>
        <button class="btn btn-sm btn-outline-secondary" @click="selectAll(false)">
          Снять выделение
        </button>
      </div>
      <ul class="list-group mb-3">
        <li
          v-for="l in foundLeads"
          :key="l.lead_id"
          class="list-group-item d-flex align-items-center"
        >
          <input
            type="checkbox"
            v-model="selectedSet[l.lead_id]"
            class="form-check-input me-3"
          />
          <span class="fw-semibold me-3">#{{ l.lead_id }}</span>
          <span class="text-muted small">{{ l.actions_count }} actions</span>
        </li>
      </ul>
      <div class="d-flex gap-2">
        <button class="btn btn-outline-secondary" @click="step = 'form'">
          <i class="bi bi-arrow-left me-1"></i>Назад
        </button>
        <button
          class="btn btn-primary"
          :disabled="!selectedLeads.length"
          @click="startEvaluation"
        >
          <i class="bi bi-play-fill me-2"></i>
          Запустить на {{ selectedLeads.length }} лидах
        </button>
      </div>
    </div>

    <!-- ===== STEP 3: progress + result ===== -->
    <div v-if="step === 'run'" class="card border-0 shadow-sm p-4">
      <div class="fw-semibold mb-3">
        Оценка качества
        <span class="badge ms-2" :class="statusBadge">{{ task?.status }}</span>
      </div>

      <div v-if="task && task.total" class="mb-3">
        <div class="d-flex justify-content-between small text-muted mb-1">
          <span>{{ task.current_step || 'старт...' }}</span>
          <span>{{ task.done }} / {{ task.total }}</span>
        </div>
        <div class="progress" style="height: 6px">
          <div
            class="progress-bar"
            :class="task.status === 'failed' ? 'bg-danger' : 'bg-primary'"
            :style="{ width: progressPercent + '%' }"
          ></div>
        </div>
      </div>

      <div v-if="task?.status === 'running'" class="mb-3">
        <button
          class="btn btn-sm btn-outline-danger"
          :disabled="cancelling"
          @click="cancelTask"
        >
          <i class="bi me-1" :class="cancelling ? 'bi-hourglass-split' : 'bi-stop-circle'"></i>
          {{ cancelling ? 'Останавливается... (ждём окончания текущего шага)' : 'Остановить' }}
        </button>
      </div>

      <ResultBlock v-if="task?.result?.metrics" :result="task.result" />

      <div v-if="['completed', 'failed', 'cancelled'].includes(task?.status)" class="mt-3">
        <button class="btn btn-outline-secondary" @click="restart">
          <i class="bi bi-arrow-counterclockwise me-1"></i>Новый прогон
        </button>
      </div>

      <div v-if="error" class="alert alert-danger mt-3 py-2 small">{{ error }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { qualityApi } from '../../api/endpoints'
import ResultBlock from './ResultBlock.vue'

const step = ref('form') // form | pick | run
const form = ref({ min: 1, max: 200, n: 5, minActions: 1 })

const ACTIVE_TASK_KEY = 'quality_active_task_id'

const finding = ref(false)
const error = ref('')

const foundLeads = ref([])
const selectedSet = ref({})

const task = ref(null)
const goldCount = ref(4)
const cancelling = ref(false)
let pollTimer = null

const selectedLeads = computed(() =>
  foundLeads.value
    .map((l) => l.lead_id)
    .filter((id) => selectedSet.value[id]),
)

const progressPercent = computed(() => {
  if (!task.value?.total) return 0
  return Math.min(100, Math.round((task.value.done / task.value.total) * 100))
})

const statusBadge = computed(() => {
  const s = task.value?.status
  if (s === 'completed') return 'bg-success'
  if (s === 'failed') return 'bg-danger'
  if (s === 'cancelled') return 'bg-warning text-dark'
  if (s === 'running') return 'bg-warning text-dark'
  return 'bg-secondary'
})

async function findLeads() {
  error.value = ''
  finding.value = true
  try {
    const data = await qualityApi.findLeads(
      form.value.min,
      form.value.max,
      form.value.n,
      form.value.minActions,
    )
    foundLeads.value = data.found || []
    selectedSet.value = {}
    foundLeads.value.forEach((l) => (selectedSet.value[l.lead_id] = true))

    // Получим число gold-эталонов чтобы показать оценку времени
    try {
      const gold = await qualityApi.listGold()
      goldCount.value = (gold.entries || []).length || 1
    } catch {
      /* ignore */
    }

    if (!foundLeads.value.length) {
      error.value = 'Не найдено ни одного валидного лида в диапазоне'
      return
    }
    step.value = 'pick'
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message
  } finally {
    finding.value = false
  }
}

function selectAll(v) {
  foundLeads.value.forEach((l) => (selectedSet.value[l.lead_id] = v))
}

async function startEvaluation() {
  error.value = ''
  try {
    const data = await qualityApi.startTask(selectedLeads.value)
    localStorage.setItem(ACTIVE_TASK_KEY, data.task_id)
    step.value = 'run'
    task.value = { id: data.task_id, status: 'queued', done: 0, total: 0 }
    startPolling()
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    if (!task.value?.id) return
    try {
      const data = await qualityApi.taskStatus(task.value.id)
      task.value = data
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        clearInterval(pollTimer)
        pollTimer = null
        cancelling.value = false
        localStorage.removeItem(ACTIVE_TASK_KEY)
      }
    } catch (e) {
      // Если 404 — задача потеряна (рестарт бэка), сбросим.
      if (e?.response?.status === 404) {
        clearInterval(pollTimer)
        pollTimer = null
        localStorage.removeItem(ACTIVE_TASK_KEY)
        error.value = 'Задача не найдена на сервере (возможно, был рестарт)'
      }
    }
  }, 2000)
}

async function cancelTask() {
  if (!task.value?.id || cancelling.value) return
  cancelling.value = true
  try {
    await qualityApi.cancelTask(task.value.id)
  } catch (e) {
    cancelling.value = false
  }
}

function restart() {
  task.value = null
  step.value = 'form'
  localStorage.removeItem(ACTIVE_TASK_KEY)
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

onMounted(async () => {
  // 1) Есть активный task_id в localStorage → подхватим
  const savedId = localStorage.getItem(ACTIVE_TASK_KEY)
  if (savedId) {
    try {
      const data = await qualityApi.taskStatus(savedId)
      task.value = data
      step.value = 'run'
      if (data.status === 'running' || data.status === 'queued') {
        startPolling()
      } else {
        // Уже завершилась — оставим как есть, но уберём ключ
        localStorage.removeItem(ACTIVE_TASK_KEY)
      }
      return
    } catch (e) {
      // 404: задача потеряна → почистим
      localStorage.removeItem(ACTIVE_TASK_KEY)
    }
  }

  // 2) Иначе — попробуем подгрузить последний завершённый результат
  try {
    const latest = await qualityApi.latest()
    if (latest?.status === 'completed' && latest.result) {
      task.value = latest
      step.value = 'run'
    }
  } catch (e) {
    /* ничего, остаёмся на форме */
  }
})
</script>
