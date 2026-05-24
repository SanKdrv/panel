<template>
  <div>
    <div class="row g-3 mb-3">
      <div class="col-md-3">
        <MetricCard
          label="Faithfulness"
          :value="m.faithfulness"
          :odz="odz.faithfulness"
        />
      </div>
      <div class="col-md-3">
        <MetricCard
          label="Answer Relevance"
          :value="m.answer_relevance"
          :odz="odz.answer_relevance"
        />
      </div>
      <div class="col-md-3">
        <MetricCard
          label="Context Precision"
          :value="m.context_precision"
          :odz="odz.context_precision"
        />
      </div>
      <div class="col-md-3">
        <MetricCard
          label="TPS"
          :value="m.tps"
          :odz="odz.tps"
          unit=" т/с"
        />
      </div>
    </div>

    <div v-if="result.lead_ids?.length" class="small text-muted mb-3">
      Использованные лиды: {{ result.lead_ids.join(', ') }} · samples: {{ m.samples }}
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
              <tr style="cursor: pointer" @click="toggle(i)">
                <td>#{{ s.lead_id }}</td>
                <td>
                  <span class="badge rounded-pill px-2" :class="badge(s.stage)">
                    {{ s.stage }}
                  </span>
                </td>
                <td class="text-end" :class="cls(s.faithfulness, odz.faithfulness)">
                  {{ s.faithfulness.toFixed(2) }}
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
              <tr v-if="opened[i]">
                <td colspan="7" class="bg-light">
                  <div class="row g-3 p-2">
                    <div class="col-md-6">
                      <div class="small fw-semibold text-muted mb-1">Эталон</div>
                      <div class="small" style="white-space: pre-wrap">
                        {{ s.reference }}
                      </div>
                    </div>
                    <div class="col-md-6">
                      <div class="small fw-semibold text-muted mb-1">
                        Сгенерировано ({{ s.tokens }} токенов за {{ s.duration_s }}с)
                      </div>
                      <div class="small" style="white-space: pre-wrap">
                        {{ s.generated }}
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
    m.value.faithfulness      >= (odz.value.faithfulness      || 0) &&
    m.value.answer_relevance  >= (odz.value.answer_relevance  || 0) &&
    m.value.context_precision >= (odz.value.context_precision || 0) &&
    m.value.tps               >= (odz.value.tps               || 0)
  )
})

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
