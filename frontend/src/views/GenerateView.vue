<template>
  <div>
    <div class="page-title">
      <i class="bi bi-lightning me-2 text-primary"></i>Ручная генерация рекомендации
    </div>

    <div class="row g-4">
      <div class="col-md-5">
        <div class="card border-0 shadow-sm p-4 h-100">
          <div class="mb-3">
            <label class="form-label fw-semibold">
              Идентификатор лида (lead_id)
            </label>
            <input v-model="leadId" type="text" class="form-control" />
          </div>
          <div class="mb-4">
            <label class="form-label fw-semibold">Тип рекомендации</label>
            <select v-model="type" class="form-select">
              <option value="cold">cold</option>
              <option value="warm">warm</option>
              <option value="hot">hot</option>
              <option value="after_sale">after_sale</option>
            </select>
          </div>
          <button
            class="btn btn-primary w-100"
            :disabled="status === 'queued' || status === 'processing'"
            @click="generate"
          >
            <i class="bi bi-play-fill me-2"></i>Сгенерировать
          </button>

          <div v-if="status" class="mt-4">
            <div class="fw-semibold mb-2 small text-muted">Статус задачи</div>
            <div class="step-indicator">
              <div class="step" :class="stepClass('queued')">
                <div class="step-dot"></div>
                queued — задача поставлена в очередь
              </div>
              <div class="step" :class="stepClass('processing')">
                <div class="step-dot"></div>
                processing — генерация...
              </div>
              <div class="step" :class="stepClass('completed')">
                <div class="step-dot"></div>
                completed — готово
              </div>
            </div>
          </div>
          <div v-if="error" class="alert alert-danger mt-3 py-2">
            {{ error }}
          </div>
        </div>
      </div>

      <div class="col-md-7">
        <div class="card border-0 shadow-sm p-4 h-100">
          <div class="fw-semibold mb-3">
            Результат генерации
            <span v-if="status" class="badge ms-2" :class="statusBadgeClass">
              {{ status }}
            </span>
          </div>
          <div class="bg-light rounded p-3" style="font-size: 0.9rem; min-height: 200px">
            <template v-if="result">{{ result }}</template>
            <template v-else>
              <span class="text-muted">Результат появится после генерации.</span>
            </template>
          </div>
          <div v-if="result" class="d-flex gap-2 mt-3">
            <button class="btn btn-outline-secondary btn-sm" @click="copyResult">
              <i class="bi bi-clipboard me-1"></i>Скопировать
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { generateApi, leadsApi } from '../api/endpoints'

const leadId = ref('lead_00142')
const type = ref('warm')

const token = ref('')
const status = ref('')
const result = ref('')
const error = ref('')

let pollTimer = null

const statusBadgeClass = computed(() => {
  if (status.value === 'completed') return 'bg-success'
  if (status.value === 'failed') return 'bg-danger'
  return 'bg-warning text-dark'
})

function stepClass(step) {
  const order = ['queued', 'processing', 'completed']
  const cur = order.indexOf(status.value)
  const tgt = order.indexOf(step)
  if (cur < 0 || tgt < 0) return 'wait'
  if (tgt < cur) return 'done'
  if (tgt === cur) return 'active'
  return 'wait'
}

async function generate() {
  error.value = ''
  result.value = ''
  status.value = ''
  token.value = ''
  try {
    const data = await generateApi.trigger(leadId.value, type.value)
    token.value = data.token
    status.value = data.status || 'queued'
    startPolling()
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка'
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    if (!token.value) return
    try {
      const data = await generateApi.status(token.value)
      status.value = data.status
      if (data.status === 'completed') {
        clearInterval(pollTimer)
        pollTimer = null
        // Fetch result via leads card
        try {
          const card = await leadsApi.card(leadId.value)
          const recs = card.recommendations || []
          if (recs.length) {
            const data = recs[0].data
            result.value = typeof data === 'string' ? data : JSON.stringify(data, null, 2)
          } else {
            result.value = '(пусто)'
          }
        } catch (e) {
          result.value = `(не удалось получить: ${e.message})`
        }
      } else if (data.status === 'failed') {
        clearInterval(pollTimer)
        pollTimer = null
        error.value = 'Генерация не удалась'
      }
    } catch (e) {
      /* keep polling */
    }
  }, 2000)
}

function copyResult() {
  navigator.clipboard.writeText(result.value)
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>
