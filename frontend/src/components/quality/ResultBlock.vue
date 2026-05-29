<template>
  <div>
    <div class="row g-3 mb-3">
      <div class="col-md-3">
        <MetricCard
          label="Reference Alignment"
          :value="m.reference_alignment"
          :odz="odz.reference_alignment"
          :ci="m.ci?.reference_alignment"
        />
      </div>
      <div class="col-md-3">
        <MetricCard
          label="Answer Relevance"
          :value="m.answer_relevance"
          :odz="odz.answer_relevance"
          :ci="m.ci?.answer_relevance"
        />
      </div>
      <div class="col-md-3">
        <MetricCard
          label="Context Precision"
          :value="m.context_precision"
          :odz="odz.context_precision"
          :ci="m.ci?.context_precision"
        />
      </div>
      <div class="col-md-3">
        <MetricCard
          label="TPS"
          :value="m.tps"
          :odz="odz.tps"
          unit=" т/с"
          :ci="m.ci?.tps"
        />
      </div>
    </div>

    <div v-if="result.lead_ids?.length" class="small text-muted mb-3">
      Использованные лиды: {{ result.lead_ids.join(', ') }} ·
      успешных samples: <strong>{{ m.samples }}</strong>
      <span v-if="m.samples_recovered">
        ·
        <span
          class="text-warning"
          title="poll вернул fail, но после паузы 120 с в RAG нашлась новая рекомендация"
        >
          восстановлено: {{ m.samples_recovered }}
        </span>
      </span>
      <span v-if="m.samples_failed">
        · <span class="text-danger">failed: {{ m.samples_failed }}</span>
      </span>
      <span v-if="m.samples_total"> из {{ m.samples_total }}</span>
    </div>

    <!-- Gold dataset snapshot -->
    <div v-if="goldSnapshot.length" class="card border-0 shadow-sm mb-3">
      <div class="card-body p-0">
        <div
          class="d-flex justify-content-between align-items-center px-3 py-2 border-bottom"
          style="cursor: pointer"
          @click="goldOpen = !goldOpen"
        >
          <span class="fw-semibold small">
            <i class="bi bi-book me-1"></i>
            Эталоны прогона ({{ goldSnapshot.length }})
          </span>
          <i class="bi" :class="goldOpen ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
        </div>
        <table v-if="goldOpen" class="table mb-0">
          <thead class="table-light">
            <tr>
              <th style="width: 140px">Стадия</th>
              <th>Эталонный ответ</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(g, gi) in goldSnapshot" :key="gi">
              <td>
                <span class="badge rounded-pill px-2" :class="badge(g.stage)">
                  {{ g.stage }}
                </span>
                <div v-if="g.id" class="text-muted small mt-1">{{ g.id }}</div>
              </td>
              <td class="small" style="white-space: pre-wrap">
                {{ g.reference }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="alert d-flex align-items-center gap-2" :class="allPass ? 'alert-success' : 'alert-warning'">
      <i class="bi fs-5" :class="allPass ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill'"></i>
      <div>
        <span v-if="allPass">
          Все метрики соответствуют ОДЗ. Система готова к эксплуатации.
        </span>
        <span v-else>
          Часть метрик ниже ОДЗ — рекомендуется пересмотреть промпты или
          обновить базу знаний.
        </span>
      </div>
    </div>

    <!-- Detail per sample -->
    <div v-if="samples.length" class="card border-0 shadow-sm mt-3">
      <!-- Filter panel -->
      <div class="px-3 py-2 border-bottom bg-light">
        <div class="d-flex align-items-center gap-3 flex-wrap">
          <span class="fw-semibold small">
            <i class="bi bi-funnel me-1"></i>Фильтры
          </span>
          <div class="form-check form-check-inline mb-0">
            <input
              id="filterOdz"
              v-model="filterOnlyFailed"
              class="form-check-input"
              type="checkbox"
            />
            <label for="filterOdz" class="form-check-label small">
              Только вне ОДЗ
            </label>
          </div>
          <button
            class="btn btn-sm btn-link p-0 text-decoration-none small"
            @click="showAdvanced = !showAdvanced"
          >
            {{ showAdvanced ? 'Скрыть пороги ▲' : 'Пороги по метрикам ▼' }}
          </button>

          <!-- Regen button (ФТ15) — shown only when rows are selected and taskId provided -->
          <button
            v-if="taskId && selectedCount > 0"
            class="btn btn-sm btn-warning"
            :disabled="isRegening"
            @click="startRegen"
          >
            <span v-if="isRegening">
              <span class="spinner-border spinner-border-sm me-1"></span>Перегенерация...
            </span>
            <span v-else>
              <i class="bi bi-arrow-repeat me-1"></i>Перегенерировать ({{ selectedCount }})
            </span>
          </button>

          <span class="ms-auto small text-muted">
            Показано: {{ filteredSamples.length }} / {{ samples.length }}
          </span>
        </div>

        <div v-if="showAdvanced" class="row g-2 mt-2">
          <div
            v-for="mf in metricFilters"
            :key="mf.key"
            class="col-6 col-md-3"
          >
            <label class="form-label small text-muted mb-1">
              {{ mf.label }}
              <span class="text-secondary">(ОДЗ ≥ {{ odzVal(mf.key).toFixed(2) }})</span>
            </label>
            <div class="input-group input-group-sm">
              <span class="input-group-text" style="font-size: 0.75rem">min</span>
              <input
                v-model.number="mf.min"
                type="number"
                step="0.01"
                min="0"
                max="1"
                class="form-control"
                style="font-size: 0.75rem"
              />
              <span class="input-group-text" style="font-size: 0.75rem">max</span>
              <input
                v-model.number="mf.max"
                type="number"
                step="0.01"
                min="0"
                max="1"
                class="form-control"
                style="font-size: 0.75rem"
              />
            </div>
          </div>
        </div>
      </div>

      <div class="card-body p-0">
        <table class="table mb-0">
          <thead class="table-light">
            <tr>
              <!-- Checkbox "select all" (ФТ15) — only shown when taskId provided -->
              <th v-if="taskId" style="width: 36px" class="text-center">
                <input
                  type="checkbox"
                  class="form-check-input"
                  :checked="allSelected"
                  :indeterminate.prop="someSelected"
                  @change="toggleSelectAll"
                />
              </th>
              <th style="width: 100px">Лид</th>
              <th style="width: 100px">Стадия</th>
              <th class="text-end" style="width: 90px">
                Faith
                <span class="text-secondary" style="font-size:0.7rem">≥{{ odzVal('reference_alignment').toFixed(2) }}</span>
              </th>
              <th class="text-end" style="width: 90px">
                Rel
                <span class="text-secondary" style="font-size:0.7rem">≥{{ odzVal('answer_relevance').toFixed(2) }}</span>
              </th>
              <th class="text-end" style="width: 90px">
                Prec
                <span class="text-secondary" style="font-size:0.7rem">≥{{ odzVal('context_precision').toFixed(2) }}</span>
              </th>
              <th class="text-end" style="width: 90px">
                TPS
                <span class="text-secondary" style="font-size:0.7rem">≥{{ odzVal('tps').toFixed(1) }}</span>
              </th>
              <th style="width: 40px"></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="(s, i) in filteredSamples" :key="i">
              <!-- Failed sample row -->
              <tr v-if="s.status === 'failed'" style="cursor: pointer" @click="toggle(i)" class="table-danger">
                <td v-if="taskId" class="text-center" @click.stop>
                  <input
                    type="checkbox"
                    class="form-check-input"
                    :checked="!!selectedForRegen[regenKey(s)]"
                    :disabled="isRegening"
                    @change="toggleRegen(s)"
                  />
                </td>
                <td>#{{ s.lead_id }}</td>
                <td>
                  <span class="badge rounded-pill px-2" :class="badge(s.stage)">
                    {{ s.stage }}
                  </span>
                  <span v-if="regenProgress[regenKey(s)]" :class="regenBadgeClass(s)" class="badge rounded-pill px-2 ms-1">
                    <span v-if="regenProgress[regenKey(s)] === 'processing'" class="spinner-border spinner-border-sm" style="width:.65em;height:.65em"></span>
                    <span v-else>{{ regenProgress[regenKey(s)] }}</span>
                  </span>
                  <button
                    v-if="regenProgress[regenKey(s)] === 'queued'"
                    class="btn btn-sm p-0 ms-1 text-danger"
                    style="line-height:1"
                    title="Отменить"
                    @click.stop="cancelPair(s.lead_id, s.stage)"
                  ><i class="bi bi-x-lg" style="font-size:0.7rem"></i></button>
                </td>
                <td colspan="4" class="text-danger small">
                  <i class="bi bi-x-circle-fill me-1"></i>
                  failed: {{ s.error }}
                </td>
                <td class="text-center">
                  <i class="bi" :class="opened[i] ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                </td>
              </tr>

              <!-- OK sample row -->
              <tr v-else style="cursor: pointer" @click="toggle(i)">
                <td v-if="taskId" class="text-center" @click.stop>
                  <input
                    type="checkbox"
                    class="form-check-input"
                    :checked="!!selectedForRegen[regenKey(s)]"
                    :disabled="isRegening"
                    @change="toggleRegen(s)"
                  />
                </td>
                <td>#{{ s.lead_id }}</td>
                <td>
                  <span class="badge rounded-pill px-2" :class="badge(s.stage)">
                    {{ s.stage }}
                  </span>
                  <span
                    v-if="s.recovered"
                    class="badge rounded-pill bg-warning text-dark px-2 ms-1"
                    title="восстановлен: poll сказал fail, но рекомендация всё-таки появилась"
                  >
                    восст.
                  </span>
                  <span v-if="regenProgress[regenKey(s)]" :class="regenBadgeClass(s)" class="badge rounded-pill px-2 ms-1">
                    <span v-if="regenProgress[regenKey(s)] === 'processing'" class="spinner-border spinner-border-sm" style="width:.65em;height:.65em"></span>
                    <span v-else>{{ regenProgress[regenKey(s)] }}</span>
                  </span>
                  <button
                    v-if="regenProgress[regenKey(s)] === 'queued'"
                    class="btn btn-sm p-0 ms-1 text-danger"
                    style="line-height:1"
                    title="Отменить"
                    @click.stop="cancelPair(s.lead_id, s.stage)"
                  ><i class="bi bi-x-lg" style="font-size:0.7rem"></i></button>
                </td>
                <td class="text-end" :class="cls(refAlign(s), odz.reference_alignment)">
                  {{ refAlign(s).toFixed(2) }}
                </td>
                <td class="text-end" :class="cls(s.answer_relevance, odz.answer_relevance)">
                  {{ s.answer_relevance.toFixed(2) }}
                </td>
                <td class="text-end" :class="cls(s.context_precision, odz.context_precision)">
                  {{ s.context_precision.toFixed(2) }}
                </td>
                <td class="text-end" :class="cls(s.tps, odz.tps)">
                  {{ s.tps.toFixed(1) }}
                </td>
                <td class="text-center">
                  <i class="bi" :class="opened[i] ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                </td>
              </tr>

              <!-- Expanded -->
              <tr v-if="opened[i]">
                <td :colspan="taskId ? 8 : 7" class="bg-light">
                  <div v-if="s.status === 'failed'" class="p-2">
                    <div class="small fw-semibold text-muted mb-1">Причина</div>
                    <div class="small text-danger">{{ s.error }}</div>
                    <div class="small fw-semibold text-muted mt-3 mb-1">Эталон (не использован)</div>
                    <div class="small" style="white-space: pre-wrap">{{ s.reference }}</div>
                  </div>
                  <div v-else class="row g-3 p-2">
                    <div class="col-md-6">
                      <div class="small fw-semibold text-muted mb-1">Эталон</div>
                      <div class="small" style="white-space: pre-wrap">
                        {{ s.reference }}
                      </div>
                    </div>
                    <div class="col-md-6">
                      <div class="small fw-semibold text-muted mb-1">
                        Сгенерировано
                        <span class="fw-normal">
                          (всего
                          <span :title="'все поля кроме _system — используется для TPS'">
                            {{ s.tokens_for_tps ?? s.tokens }}
                          </span>
                          токенов,
                          <span :title="'только пользовательский текст — используется для метрик качества'">
                            {{ s.tokens }} полезных
                          </span>
                          за {{ s.duration_s }}с)
                        </span>
                      </div>
                      <div class="small" style="white-space: pre-wrap">
                        {{ s.generated }}
                      </div>
                      <div v-if="s.diagnostics?.length" class="small text-warning mt-2">
                        <i class="bi bi-exclamation-triangle me-1"></i>
                        <span v-for="(d, di) in s.diagnostics" :key="di">
                          {{ d }}<span v-if="di < s.diagnostics.length - 1">; </span>
                        </span>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import MetricCard from '../MetricCard.vue'
import { qualityApi } from '../../api/endpoints'

const props = defineProps({
  result: { type: Object, required: true },
  taskId: { type: String, default: null },
})

const emit = defineEmits(['regen-complete', 'regen-start', 'regen-end'])

const m = computed(() => props.result.metrics)
const odz = computed(() => props.result.odz || {})
const samples = computed(() => props.result.samples || [])
const goldSnapshot = computed(() => props.result.gold_snapshot || [])
const goldOpen = ref(false)

// ---- Filters (ФТ16) ----
const filterOnlyFailed = ref(false)
const showAdvanced = ref(false)

const metricFilters = reactive([
  { key: 'reference_alignment', label: 'Faith', min: null, max: null },
  { key: 'answer_relevance',    label: 'Rel',   min: null, max: null },
  { key: 'context_precision',   label: 'Prec',  min: null, max: null },
  { key: 'tps',                 label: 'TPS',   min: null, max: null },
])

function odzVal(key) {
  return odz.value[key] ?? 0
}

function sampleMetric(s, key) {
  if (key === 'reference_alignment') return refAlign(s)
  return s[key] ?? 0
}

function isOutOfOdz(s) {
  if (s.status === 'failed') return true
  return metricFilters.some(
    (mf) => sampleMetric(s, mf.key) < odzVal(mf.key),
  )
}

const filteredSamples = computed(() => {
  return samples.value.filter((s) => {
    if (filterOnlyFailed.value && !isOutOfOdz(s)) return false
    for (const mf of metricFilters) {
      const v = sampleMetric(s, mf.key)
      if (mf.min !== null && mf.min !== '' && v < mf.min) return false
      if (mf.max !== null && mf.max !== '' && v > mf.max) return false
    }
    return true
  })
})
// ---- end Filters ----

const opened = ref({})
function toggle(i) {
  opened.value[i] = !opened.value[i]
}

const allPass = computed(() => {
  if (!m.value) return false
  return (
    m.value.reference_alignment      >= (odz.value.reference_alignment      || 0) &&
    m.value.answer_relevance  >= (odz.value.answer_relevance  || 0) &&
    m.value.context_precision >= (odz.value.context_precision || 0) &&
    m.value.tps               >= (odz.value.tps               || 0)
  )
})

function refAlign(s) {
  const v = s.reference_alignment ?? s.faithfulness
  return typeof v === 'number' ? v : 0
}

function cls(v, odzV) {
  return v >= odzV ? 'text-success' : 'text-danger'
}

function badge(s) {
  return {
    cold: 'bg-secondary',
    warm: 'bg-warning text-dark',
    hot: 'bg-danger',
    after_sale: 'bg-success',
  }[s]
}

// ---- Selective regeneration (ФТ15) ----

function regenKey(s) {
  return `${s.lead_id}:${s.stage}`
}

const selectedForRegen = reactive({})  // regenKey → boolean
const isRegening = ref(false)
const regenProgress = reactive({})     // regenKey → 'queued'|'processing'|'done'|'failed'|'cancelled'
const activeRegenId = ref(null)        // regen_id текущей активной регенерации

function toggleRegen(s) {
  const k = regenKey(s)
  selectedForRegen[k] = !selectedForRegen[k]
}

const selectedCount = computed(() =>
  Object.values(selectedForRegen).filter(Boolean).length,
)

const allSelected = computed(() => {
  if (!filteredSamples.value.length) return false
  return filteredSamples.value.every((s) => !!selectedForRegen[regenKey(s)])
})

const someSelected = computed(() => {
  if (allSelected.value) return false
  return filteredSamples.value.some((s) => !!selectedForRegen[regenKey(s)])
})

function toggleSelectAll(e) {
  const v = e.target.checked
  filteredSamples.value.forEach((s) => {
    selectedForRegen[regenKey(s)] = v
  })
}

async function startRegen() {
  if (!props.taskId) return
  const pairs = Object.entries(selectedForRegen)
    .filter(([, v]) => v)
    .map(([k]) => {
      const idx = k.indexOf(':')
      return { lead_id: k.slice(0, idx), stage: k.slice(idx + 1) }
    })
  if (!pairs.length) return

  isRegening.value = true
  emit('regen-start')
  pairs.forEach((p) => {
    regenProgress[`${p.lead_id}:${p.stage}`] = 'queued'
  })

  try {
    const data = await qualityApi.startRegen(props.taskId, pairs)
    activeRegenId.value = data.regen_id
    await pollRegen(data.regen_id)
  } catch (e) {
    console.error('Regen start failed:', e)
  } finally {
    isRegening.value = false
    activeRegenId.value = null
    emit('regen-end')
  }
}

async function cancelPair(leadId, stage) {
  if (!activeRegenId.value) return
  try {
    await qualityApi.cancelRegenPairs(activeRegenId.value, [{ lead_id: leadId, stage }])
    regenProgress[`${leadId}:${stage}`] = 'cancelled'
    selectedForRegen[`${leadId}:${stage}`] = false
  } catch (_e) { /* ignore */ }
}

function pollRegen(regenId) {
  return new Promise((resolve) => {
    const timer = setInterval(async () => {
      try {
        const data = await qualityApi.getRegenStatus(regenId)
        for (const p of data.progress) {
          regenProgress[`${p.lead_id}:${p.stage}`] = p.status
        }
        if (data.status !== 'running') {
          clearInterval(timer)
          Object.keys(selectedForRegen).forEach((k) => { selectedForRegen[k] = false })
          if (data.status === 'completed') emit('regen-complete')
          resolve()
        }
      } catch (_e) { /* keep polling */ }
    }, 2000)
  })
}

// При монтировании спрашиваем бэкенд: вдруг уже идёт регенерация для этой таски?
// Это работает и для возврата на страницу, и для другого браузера.
onMounted(async () => {
  if (!props.taskId) return
  try {
    const data = await qualityApi.getActiveRegen()
    if (data.status !== 'running' || data.task_id !== props.taskId) return

    isRegening.value = true
    activeRegenId.value = data.regen_id
    emit('regen-start')
    for (const p of data.progress) {
      regenProgress[`${p.lead_id}:${p.stage}`] = p.status
    }
    try {
      await pollRegen(data.regen_id)
    } finally {
      isRegening.value = false
      activeRegenId.value = null
      emit('regen-end')
    }
  } catch (_e) { /* ignore */ }
})

function regenBadgeClass(s) {
  const st = regenProgress[regenKey(s)]
  if (st === 'processing') return 'bg-warning text-dark'
  if (st === 'done') return 'bg-success'
  if (st === 'failed') return 'bg-danger'
  if (st === 'cancelled') return 'bg-secondary'
  return 'bg-secondary'
}
</script>
