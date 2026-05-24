<template>
  <div>
    <div class="page-title">
      <i class="bi bi-chat-left-text me-2 text-primary"></i>Управление промптами
    </div>
    <p class="text-muted mb-3">
      Выберите стадию воронки и отредактируйте системный промпт.
      Изменения применяются немедленно.
    </p>

    <ul class="nav nav-pills mb-4">
      <li v-for="lt in leadTypes" :key="lt.code" class="nav-item">
        <a
          class="nav-link px-4"
          :class="{ active: active === lt.code }"
          href="#"
          @click.prevent="active = lt.code"
        >
          {{ lt.label }}
        </a>
      </li>
    </ul>

    <div class="card border-0 shadow-sm p-4" style="max-width: 720px">
      <label class="form-label fw-semibold">
        Системный промпт — стадия
        <span class="badge" :class="badgeClass(active)">{{ active }}</span>
      </label>
      <textarea
        v-model="currentPrompt"
        class="form-control font-monospace"
        rows="12"
      ></textarea>
      <div class="d-flex gap-2 mt-3">
        <button class="btn btn-primary" :disabled="saving" @click="save">
          <i class="bi bi-floppy me-2"></i>
          {{ saving ? 'Сохранение...' : 'Сохранить' }}
        </button>
        <button class="btn btn-outline-secondary" @click="reset">
          <i class="bi bi-arrow-counterclockwise me-2"></i>Сбросить
        </button>
      </div>
      <div v-if="message" class="alert mt-3 py-2" :class="messageClass">
        {{ message }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { promptsApi } from '../api/endpoints'

const leadTypes = [
  { code: 'cold', label: 'Cold' },
  { code: 'warm', label: 'Warm' },
  { code: 'hot', label: 'Hot' },
  { code: 'after_sale', label: 'After Sale' },
]

const active = ref('cold')
const prompts = ref({}) // map: lead_type -> prompt
const originalPrompts = ref({})
const saving = ref(false)
const message = ref('')
const isError = ref(false)

const currentPrompt = computed({
  get: () => prompts.value[active.value] || '',
  set: (v) => {
    prompts.value[active.value] = v
  },
})

const messageClass = computed(() =>
  isError.value ? 'alert-danger' : 'alert-success',
)

function badgeClass(code) {
  return {
    cold: 'bg-secondary',
    warm: 'bg-warning text-dark',
    hot: 'bg-danger',
    after_sale: 'bg-success',
  }[code]
}

async function load() {
  try {
    const list = await promptsApi.list()
    list.forEach((p) => {
      prompts.value[p.lead_type] = p.prompt || ''
      originalPrompts.value[p.lead_type] = p.prompt || ''
    })
  } catch (e) {
    message.value = e?.message || 'Не удалось загрузить промпты'
    isError.value = true
  }
}

async function save() {
  message.value = ''
  saving.value = true
  try {
    const data = await promptsApi.update(active.value, currentPrompt.value)
    originalPrompts.value[active.value] = data.prompt
    message.value = 'Промпт обновлён'
    isError.value = false
  } catch (e) {
    message.value = e?.response?.data?.detail || e?.message || 'Ошибка'
    isError.value = true
  } finally {
    saving.value = false
  }
}

function reset() {
  prompts.value[active.value] = originalPrompts.value[active.value] || ''
  message.value = ''
}

watch(active, () => {
  message.value = ''
})

onMounted(load)
</script>
