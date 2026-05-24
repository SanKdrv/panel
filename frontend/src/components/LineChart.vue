<template>
  <div class="chart-wrap">
    <Line :data="chartData" :options="chartOptions" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  PointElement,
  LineElement,
  CategoryScale,
  LinearScale,
  TimeScale,
  Filler,
} from 'chart.js'
import 'chartjs-adapter-date-fns'

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  PointElement,
  LineElement,
  CategoryScale,
  LinearScale,
  TimeScale,
  Filler,
)

const props = defineProps({
  series: { type: Array, required: true }, // [{label, points: [[ts_ms, val], ...]}]
  unit: { type: String, default: '' },
  yMax: { type: Number, default: null },
  yMin: { type: Number, default: 0 },
})

const palette = [
  '#0d6efd',
  '#198754',
  '#dc3545',
  '#fd7e14',
  '#6f42c1',
  '#20c997',
]

const chartData = computed(() => ({
  datasets: props.series.map((s, i) => ({
    label: s.label,
    data: (s.points || []).map(([t, v]) => ({ x: t, y: v })),
    borderColor: palette[i % palette.length],
    backgroundColor: palette[i % palette.length] + '22',
    fill: true,
    tension: 0.25,
    pointRadius: 0,
    borderWidth: 2,
  })),
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { position: 'bottom', labels: { boxWidth: 12 } },
    tooltip: {
      callbacks: {
        label: (ctx) =>
          `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)}${props.unit}`,
      },
    },
  },
  scales: {
    x: {
      type: 'time',
      time: { displayFormats: { minute: 'HH:mm', hour: 'HH:mm' } },
      grid: { display: false },
    },
    y: {
      min: props.yMin,
      max: props.yMax ?? undefined,
      ticks: {
        callback: (v) => `${v}${props.unit}`,
      },
    },
  },
}))
</script>

<style scoped>
.chart-wrap {
  position: relative;
  height: 240px;
}
</style>
