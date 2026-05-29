<template>
  <div>
    <div class="d-flex align-items-center justify-content-between mb-3">
      <div class="fw-semibold">История прогонов</div>
      <button class="btn btn-sm btn-outline-secondary" @click="load">
        <i class="bi bi-arrow-clockwise"></i>
      </button>
    </div>

    <div v-if="!tasks.length" class="text-muted">Прогонов пока нет.</div>

    <div v-else class="card border-0 shadow-sm">
      <table class="table mb-0">
        <thead class="table-light">
          <tr>
            <th style="width: 110px">ID</th>
            <th style="width: 170px">Время</th>
            <th style="width: 120px">Статус</th>
            <th class="text-end">Samples</th>
            <th class="text-end">Ref.Align</th>
            <th class="text-end">Rel</th>
            <th class="text-end">Prec</th>
            <th class="text-end">TPS</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in tasks" :key="t.id">
            <td><code class="small">{{ t.id }}</code></td>
            <td class="small">{{ fmt(t.finished_at || t.started_at) }}</td>
            <td>
              <span class="badge rounded-pill px-2" :class="badge(t.status)">
                {{ t.status }}
              </span>
            </td>
            <td class="text-end">
              <span v-if="t.result?.metrics">
                {{ t.result.metrics.samples }}
                <span v-if="t.result.metrics.samples_failed" class="text-danger small">
                  ({{ t.result.metrics.samples_failed }} fail)
                </span>
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="text-end small">{{ num(t, 'reference_alignment') }}</td>
            <td class="text-end small">{{ num(t, 'answer_relevance') }}</td>
            <td class="text-end small">{{ num(t, 'context_precision') }}</td>
            <td class="text-end small">{{ num(t, 'tps') }}</td>
            <td class="text-end">
              <button
                class="btn btn-sm btn-outline-primary"
                @click="open(t)"
              >
                Открыть
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal -->
    <div v-if="openedTask" class="task-modal-backdrop" @click.self="openedTask = null">
      <div class="task-modal-content">
        <div class="d-flex justify-content-between mb-3">
          <div class="fw-semibold">
            Прогон <code>{{ openedTask.id }}</code>
            <span class="badge ms-2" :class="badge(openedTask.status)">
              {{ openedTask.status }}
            </span>
          </div>
          <button class="btn-close" @click="openedTask = null"></button>
        </div>
        <div v-if="openedTask.result" class="small text-muted mb-3">
          Запущен: {{ fmt(openedTask.started_at) }} ·
          Завершён: {{ fmt(openedTask.finished_at) }}
        </div>
        <ResultBlock
          v-if="openedTask.result"
          :result="openedTask.result"
          :task-id="openedTask.id"
          @regen-complete="onRegenComplete"
        />
        <div v-else class="text-muted">Результата нет (вероятно был fail на старте).</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { qualityApi } from '../../api/endpoints'
import ResultBlock from './ResultBlock.vue'

const tasks = ref([])
const openedTask = ref(null)

async function load() {
  try {
    const data = await qualityApi.listTasks(100)
    tasks.value = data.tasks || []
  } catch (e) {
    /* ignore */
  }
}

async function open(t) {
  // Получаем полный task с samples (list возвращает без samples)
  try {
    openedTask.value = await qualityApi.taskStatus(t.id)
  } catch (e) {
    openedTask.value = t
  }
}

async function onRegenComplete() {
  if (!openedTask.value?.id) return
  try {
    const fresh = await qualityApi.taskStatus(openedTask.value.id)
    openedTask.value = fresh
    // Обновим строку в таблице тоже
    const idx = tasks.value.findIndex((t) => t.id === fresh.id)
    if (idx !== -1) tasks.value[idx] = fresh
  } catch (_e) {
    /* ignore */
  }
}

function fmt(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

function badge(s) {
  if (s === 'completed') return 'bg-success'
  if (s === 'failed') return 'bg-danger'
  if (s === 'cancelled') return 'bg-warning text-dark'
  if (s === 'running') return 'bg-info text-dark'
  return 'bg-secondary'
}

function num(t, key) {
  const v = t.result?.metrics?.[key]
  if (v == null) return '—'
  return v.toFixed(2)
}

onMounted(load)
</script>

<style scoped>
.task-modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: flex-start; justify-content: center;
  padding: 2rem;
  z-index: 1050;
  overflow-y: auto;
}
.task-modal-content {
  background: #fff;
  border-radius: 8px;
  padding: 1.5rem;
  width: 100%;
  max-width: 1100px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}
</style>
