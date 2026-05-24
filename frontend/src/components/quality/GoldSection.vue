<template>
  <div>
    <p class="text-muted">
      Эталонные ответы для каждой стадии воронки. Используются модулем оценки
      качества как референс при сравнении с реальной генерацией RAG-системы.
    </p>

    <div class="card border-0 shadow-sm p-4 mb-4" style="max-width: 760px">
      <div class="fw-semibold mb-3">Добавить эталон</div>
      <div class="row g-2 align-items-start">
        <div class="col-md-3">
          <select v-model="newEntry.stage" class="form-select form-select-sm">
            <option v-for="s in stages" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div class="col-md-7">
          <textarea
            v-model="newEntry.reference"
            class="form-control form-control-sm"
            rows="2"
            placeholder="Эталонный ответ..."
          ></textarea>
        </div>
        <div class="col-md-2">
          <button class="btn btn-primary btn-sm w-100" :disabled="!canAdd" @click="add">
            <i class="bi bi-plus-lg"></i> Добавить
          </button>
        </div>
      </div>
      <div v-if="error" class="alert alert-danger mt-2 py-2 small">{{ error }}</div>
    </div>

    <div class="card border-0 shadow-sm">
      <table class="table mb-0">
        <thead class="table-light">
          <tr>
            <th style="width: 140px">Стадия</th>
            <th>Эталон</th>
            <th style="width: 110px" class="text-end">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in entries" :key="e.id">
            <td>
              <span class="badge rounded-pill px-2" :class="badgeClass(e.stage)">
                {{ e.stage }}
              </span>
            </td>
            <td>
              <textarea
                v-if="editingId === e.id"
                v-model="editingRef"
                class="form-control form-control-sm"
                rows="3"
              ></textarea>
              <div v-else style="white-space: pre-wrap; font-size: 0.875rem">
                {{ e.reference }}
              </div>
            </td>
            <td class="text-end">
              <template v-if="editingId === e.id">
                <button class="btn btn-sm btn-primary me-1" @click="saveEdit(e)">
                  <i class="bi bi-check-lg"></i>
                </button>
                <button class="btn btn-sm btn-outline-secondary" @click="cancelEdit">
                  <i class="bi bi-x-lg"></i>
                </button>
              </template>
              <template v-else>
                <button
                  class="btn btn-sm btn-outline-secondary me-1"
                  @click="startEdit(e)"
                >
                  <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" @click="remove(e)">
                  <i class="bi bi-trash"></i>
                </button>
              </template>
            </td>
          </tr>
          <tr v-if="!entries.length">
            <td colspan="3" class="text-muted text-center py-3">
              Нет эталонов
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { qualityApi } from '../../api/endpoints'

const entries = ref([])
const stages = ref(['cold', 'warm', 'hot', 'after_sale'])
const error = ref('')

const newEntry = ref({ stage: 'cold', reference: '' })
const canAdd = computed(
  () => newEntry.value.reference.trim().length > 0,
)

const editingId = ref('')
const editingRef = ref('')

async function load() {
  try {
    const data = await qualityApi.listGold()
    entries.value = data.entries || []
    stages.value = data.stages || stages.value
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message
  }
}

async function add() {
  error.value = ''
  try {
    await qualityApi.createGold(newEntry.value.stage, newEntry.value.reference)
    newEntry.value.reference = ''
    await load()
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message
  }
}

function startEdit(e) {
  editingId.value = e.id
  editingRef.value = e.reference
}

function cancelEdit() {
  editingId.value = ''
  editingRef.value = ''
}

async function saveEdit(e) {
  try {
    await qualityApi.updateGold(e.id, { reference: editingRef.value })
    editingId.value = ''
    await load()
  } catch (err) {
    error.value = err?.response?.data?.detail || err?.message
  }
}

async function remove(e) {
  if (!confirm(`Удалить эталон ${e.stage}?`)) return
  try {
    await qualityApi.deleteGold(e.id)
    await load()
  } catch (err) {
    error.value = err?.response?.data?.detail || err?.message
  }
}

function badgeClass(s) {
  return {
    cold: 'bg-secondary',
    warm: 'bg-warning text-dark',
    hot: 'bg-danger',
    after_sale: 'bg-success',
  }[s]
}

onMounted(load)
</script>
