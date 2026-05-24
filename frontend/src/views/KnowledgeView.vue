<template>
  <div>
    <div class="page-title">
      <i class="bi bi-journal-text me-2 text-primary"></i>База знаний
    </div>

    <div
      v-if="vectorStatus"
      class="alert d-flex align-items-center gap-2 mb-4"
      :class="vectorStatus === 'updating' ? 'alert-warning' : 'alert-success'"
      role="alert"
    >
      <i
        class="bi fs-5"
        :class="vectorStatus === 'updating' ? 'bi-arrow-repeat' : 'bi-check-circle'"
      ></i>
      <div>
        Векторная БД: <strong>{{ vectorStatus }}</strong>
      </div>
    </div>

    <ul class="nav nav-tabs mb-4">
      <li class="nav-item">
        <a
          class="nav-link"
          :class="{ active: tab === 'upload' }"
          href="#"
          @click.prevent="tab = 'upload'"
        >
          <i class="bi bi-upload me-1"></i>Загрузить документ
        </a>
      </li>
      <li class="nav-item">
        <a
          class="nav-link"
          :class="{ active: tab === 'mautic' }"
          href="#"
          @click.prevent="tab = 'mautic'"
        >
          <i class="bi bi-envelope me-1"></i>Импорт из Mautic
        </a>
      </li>
      <li class="nav-item">
        <a
          class="nav-link"
          :class="{ active: tab === 'types' }"
          href="#"
          @click.prevent="tab = 'types'"
        >
          <i class="bi bi-tags me-1"></i>Типы ресурсов
        </a>
      </li>
    </ul>

    <!-- Upload tab -->
    <div v-show="tab === 'upload'">
      <div class="card border-0 shadow-sm p-4" style="max-width: 640px">
        <div class="mb-3">
          <label class="form-label fw-semibold">Тип ресурса</label>
          <select v-model="upload.resource_type" class="form-select">
            <option v-for="rt in resourceTypes" :key="rt.id" :value="rt.name">
              {{ rt.name }}
            </option>
          </select>
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">
            Заголовок <span class="text-muted fw-normal">(необязательно)</span>
          </label>
          <input
            v-model="upload.title"
            type="text"
            class="form-control"
            placeholder="Например: Прайс-лист май 2025"
          />
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">
            URL источника <span class="text-muted fw-normal">(необязательно)</span>
          </label>
          <input
            v-model="upload.url"
            type="url"
            class="form-control"
            placeholder="https://..."
          />
        </div>
        <div class="mb-4">
          <label class="form-label fw-semibold">Содержимое документа</label>
          <textarea
            v-model="upload.text"
            class="form-control"
            rows="6"
            placeholder="Вставьте текст документа..."
          ></textarea>
        </div>
        <button class="btn btn-primary" :disabled="uploading" @click="doUpload">
          <i class="bi bi-cloud-upload me-2"></i>
          {{ uploading ? 'Загрузка...' : 'Загрузить' }}
        </button>
        <div v-if="uploadResult" class="alert alert-success mt-3 py-2">
          Загружено. ID ресурса: <strong>{{ uploadResult.resource_id }}</strong>,
          статус: {{ uploadResult.status }}.
        </div>
        <div v-if="uploadError" class="alert alert-danger mt-3 py-2">
          {{ uploadError }}
        </div>
      </div>

      <div v-if="recentUploads.length" class="mt-4">
        <div class="fw-semibold mb-2">Последние загрузки в этой сессии</div>
        <table class="table table-bordered bg-white" style="max-width: 640px">
          <thead class="table-light">
            <tr>
              <th>ID</th>
              <th>Заголовок</th>
              <th>Тип</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in recentUploads" :key="u.resource_id">
              <td>{{ u.resource_id }}</td>
              <td>{{ u.title || '—' }}</td>
              <td>{{ u.resource_type }}</td>
              <td>
                <span class="badge badge-ready rounded-pill px-2">
                  {{ u.status }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Mautic tab -->
    <div v-show="tab === 'mautic'">
      <div class="card border-0 shadow-sm p-4" style="max-width: 500px">
        <p class="text-muted">
          Импортировать email-рассылки из Mautic в базу знаний. Дубликаты будут
          пропущены автоматически.
        </p>
        <div class="mb-3">
          <label class="form-label fw-semibold">
            ID письма в Mautic
            <span class="text-muted fw-normal"
              >(оставьте пустым для массового импорта)</span
            >
          </label>
          <input
            v-model.number="mauticId"
            type="number"
            class="form-control"
            placeholder="Например: 17"
          />
        </div>
        <button class="btn btn-primary" :disabled="importing" @click="doImport">
          <i class="bi bi-envelope-arrow-down me-2"></i>
          {{ importing ? 'Импорт...' : 'Импортировать' }}
        </button>
        <div v-if="importResult" class="alert alert-success mt-3 py-2">
          <i class="bi bi-check-circle me-1"></i>
          {{ formatImportResult(importResult) }}
        </div>
        <div v-if="importError" class="alert alert-danger mt-3 py-2">
          {{ importError }}
        </div>
      </div>
    </div>

    <!-- Types tab -->
    <div v-show="tab === 'types'">
      <div class="card border-0 shadow-sm p-4" style="max-width: 500px">
        <div class="fw-semibold mb-3">Существующие типы ресурсов</div>
        <ul class="list-group mb-4">
          <li
            v-for="rt in resourceTypes"
            :key="rt.id"
            class="list-group-item d-flex justify-content-between"
          >
            {{ rt.name }}
            <span class="badge bg-secondary">id: {{ rt.id }}</span>
          </li>
          <li v-if="!resourceTypes.length" class="list-group-item text-muted">
            Нет типов ресурсов
          </li>
        </ul>
        <div class="d-flex gap-2">
          <input
            v-model="newTypeName"
            type="text"
            class="form-control"
            placeholder="Новый тип..."
            @keyup.enter="addType"
          />
          <button class="btn btn-primary px-3" @click="addType">
            <i class="bi bi-plus-lg"></i>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { documentsApi } from '../api/endpoints'

const tab = ref('upload')

const resourceTypes = ref([])
const vectorStatus = ref('')

const upload = ref({ resource_type: '', text: '', title: '', url: '' })
const uploading = ref(false)
const uploadResult = ref(null)
const uploadError = ref('')
const recentUploads = ref([])

const mauticId = ref(null)
const importing = ref(false)
const importResult = ref(null)
const importError = ref('')

const newTypeName = ref('')

async function loadResourceTypes() {
  try {
    const data = await documentsApi.listResourceTypes()
    resourceTypes.value = data.resource_types || []
    if (!upload.value.resource_type && resourceTypes.value.length) {
      upload.value.resource_type = resourceTypes.value[0].name
    }
  } catch (e) {
    /* ignore */
  }
}

async function loadVectorStatus() {
  try {
    const data = await documentsApi.vectorDbStatus()
    vectorStatus.value = data.status || ''
  } catch (e) {
    /* ignore */
  }
}

async function doUpload() {
  uploadError.value = ''
  uploadResult.value = null
  if (!upload.value.resource_type || !upload.value.text.trim()) {
    uploadError.value = 'Тип и содержимое обязательны'
    return
  }
  uploading.value = true
  try {
    const payload = {
      resource_type: upload.value.resource_type,
      text: upload.value.text,
      title: upload.value.title || null,
      url: upload.value.url || null,
    }
    const data = await documentsApi.upload(payload)
    uploadResult.value = data
    recentUploads.value.unshift({
      resource_id: data.resource_id,
      title: payload.title,
      resource_type: payload.resource_type,
      status: data.status,
    })
    upload.value.text = ''
    upload.value.title = ''
    upload.value.url = ''
  } catch (e) {
    uploadError.value = e?.response?.data?.detail || e?.message || 'Ошибка'
  } finally {
    uploading.value = false
  }
}

async function doImport() {
  importError.value = ''
  importResult.value = null
  importing.value = true
  try {
    importResult.value = await documentsApi.importEmail(mauticId.value || null)
  } catch (e) {
    importError.value = e?.response?.data?.detail || e?.message || 'Ошибка'
  } finally {
    importing.value = false
  }
}

function formatImportResult(r) {
  if (r.count !== undefined) return `Добавлено писем: ${r.count}`
  if (r.status === 'created') return 'Письмо добавлено'
  if (r.status === 'already_exists') return 'Уже существует'
  if (r.status === 'not_found') return 'Не найдено в Mautic'
  return JSON.stringify(r)
}

async function addType() {
  const name = newTypeName.value.trim()
  if (!name) return
  try {
    await documentsApi.createResourceType(name)
    newTypeName.value = ''
    await loadResourceTypes()
  } catch (e) {
    alert(e?.response?.data?.detail || 'Ошибка')
  }
}

onMounted(() => {
  loadResourceTypes()
  loadVectorStatus()
})
</script>
