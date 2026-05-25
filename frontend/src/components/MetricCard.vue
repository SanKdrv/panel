<template>
  <div class="card border-0 shadow-sm p-3 text-center">
    <div class="text-muted small">{{ label }}</div>
    <div class="fw-bold fs-3 mt-1" :class="colorClass">
      {{ formattedValue }}
    </div>
    <div v-if="ci && ci.length === 2" class="small text-muted">
      95% CI: {{ fmtCi(ci[0]) }} – {{ fmtCi(ci[1]) }}
    </div>
    <div class="small text-muted">ОДЗ: ≥ {{ odz }}{{ unit }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: Number, required: true },
  odz: { type: Number, required: true },
  unit: { type: String, default: '' },
  higherIsBetter: { type: Boolean, default: true },
  ci: { type: Array, default: null }, // [low, high]
})

const formattedValue = computed(() => {
  const v = props.value
  const formatted = props.unit ? v.toFixed(1) : v.toFixed(2)
  return formatted + props.unit
})

const colorClass = computed(() => {
  const ok = props.higherIsBetter ? props.value >= props.odz : props.value <= props.odz
  return ok ? 'text-success' : 'text-danger'
})

function fmtCi(v) {
  return props.unit ? v.toFixed(1) : v.toFixed(2)
}
</script>
