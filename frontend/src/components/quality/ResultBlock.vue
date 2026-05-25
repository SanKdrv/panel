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
          title="poll вернул fail, но после паузы 30 с в RAG нашлась новая рекомендация"
        >
          восстановлено: {{ m.samples_recovered }}
        </span>
      </span>
      <span v-if="m.samples_failed">
        · <span class="text-danger">failed: {{ m.samples_failed }}</span>
      </span>
      <span v-if="m.samples_total"> из {{ m.samples_total }}</span>
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
      <div class="card-body p-0">
        <table class="table mb-0">
          <thead class="table-light">
            <tr>
              <th style="width: 100px">Лид</th>
              <th style="width: 100px">Стадия</th>
              <th class="text-end" style="width: 90px">Faith</th>
              <th class="text-end" style="width: 90px">Rel</th>
              <th class="text-end" style="width: 90px">Prec</th>
              <th class="text-end" style="width: 90px">TPS</th>
              <th style="width: 40px"></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="(s, i) in samples" :key="i">
              <!-- Failed sample row -->
              <tr v-if="s.status === 'failed'" style="cursor: pointer" @click="toggle(i)" class="table-danger">
                <td>#{{ s.lead_id }}</td>
                <td>
                  <span class="badge rounded-pill px-2" :class="badge(s.stage)">
                    {{ s.stage }}
                  </span>
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
                <td colspan="7" class="bg-light">
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
import { ref, computed } from 'vue'
import MetricCard from '../MetricCard.vue'

const props = defineProps({
  result: { type: Object, required: true },
})

const m = computed(() => props.result.metrics)
const odz = computed(() => props.result.odz || {})
const samples = computed(() => props.result.samples || [])

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
  // backward-compat: старые samples могли быть с ключом faithfulness
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
</script>
