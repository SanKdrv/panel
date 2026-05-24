<template>
  <div>
    <div class="page-title">
      <i class="bi bi-person-lines-fill me-2 text-primary"></i>Карточка лида
    </div>

    <div class="card border-0 shadow-sm p-4 mb-4" style="max-width: 480px">
      <label class="form-label fw-semibold">Поиск лида</label>
      <div class="input-group">
        <input
          v-model="query"
          type="text"
          class="form-control"
          placeholder="lead_id"
          @keyup.enter="search"
        />
        <button class="btn btn-primary" @click="search">
          <i class="bi bi-search"></i>
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-muted">
      <i class="bi bi-arrow-repeat me-2"></i>Загрузка...
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div v-if="lead" class="row g-4">
      <div class="col-md-4">
        <div class="card border-0 shadow-sm p-4">
          <div class="fw-bold fs-5 mb-1">{{ lead.lead_id }}</div>
          <div class="text-muted small mb-3">—</div>
          <div class="d-flex flex-column gap-1">
            <div class="small">
              <span class="text-muted">Рекомендаций:</span>
              {{ lead.recommendations.length }}
            </div>
            <div class="small">
              <span class="text-muted">Задач за 24ч:</span>
              {{ lead.tasks.length }}
            </div>
            <div class="small">
              <span class="text-muted">Действий:</span>
              {{ lead.actions.length }}
            </div>
          </div>
        </div>
      </div>

      <div class="col-md-8">
        <ul class="nav nav-tabs mb-3">
          <li class="nav-item">
            <a
              class="nav-link"
              :class="{ active: tab === 'actions' }"
              href="#"
              @click.prevent="tab = 'actions'"
            >
              <i class="bi bi-activity me-1"></i>Цифровые следы
            </a>
          </li>
          <li class="nav-item">
            <a
              class="nav-link"
              :class="{ active: tab === 'tasks' }"
              href="#"
              @click.prevent="tab = 'tasks'"
            >
              <i class="bi bi-list-task me-1"></i>Задачи генерации
            </a>
          </li>
          <li class="nav-item">
            <a
              class="nav-link"
              :class="{ active: tab === 'recs' }"
              href="#"
              @click.prevent="tab = 'recs'"
            >
              <i class="bi bi-chat-square-text me-1"></i>Рекомендации
            </a>
          </li>
        </ul>

        <div v-show="tab === 'actions'">
          <div v-if="!lead.actions.length" class="text-muted">Нет действий</div>
          <div
            v-for="a in lead.actions"
            :key="a.id"
            class="timeline-item"
          >
            <div class="small fw-semibold">{{ a.type }}</div>
            <pre class="text-muted" style="font-size: 0.8rem">{{ formatData(a.data) }}</pre>
          </div>
        </div>

        <div v-show="tab === 'tasks'">
          <table v-if="lead.tasks.length" class="table table-sm table-bordered bg-white">
            <thead class="table-light">
              <tr>
                <th>Токен</th>
                <th>Тип</th>
                <th>Статус</th>
                <th>Создана</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in lead.tasks" :key="t.id">
                <td><code>{{ t.id }}</code></td>
                <td>{{ t.type }}</td>
                <td>
                  <span class="badge rounded-pill px-2" :class="taskBadge(t.status)">
                    {{ t.status }}
                  </span>
                </td>
                <td>{{ t.created_at || '—' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="text-muted">Нет задач за последние 24 ч</div>
        </div>

        <div v-show="tab === 'recs'">
          <div v-if="!lead.recommendations.length" class="text-muted">
            Нет рекомендаций
          </div>
          <div
            v-for="r in lead.recommendations"
            :key="r.id"
            class="card border-0 bg-light p-3 mb-2"
            style="font-size: 0.875rem"
          >
            <div class="d-flex justify-content-between mb-1">
              <span class="fw-semibold">{{ r.type }}</span>
            </div>
            <pre style="white-space: pre-wrap; margin: 0">{{ formatData(r.data) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { leadsApi } from '../api/endpoints'

const query = ref('lead_00142')
const lead = ref(null)
const loading = ref(false)
const error = ref('')
const tab = ref('actions')

async function search() {
  if (!query.value.trim()) return
  loading.value = true
  error.value = ''
  lead.value = null
  try {
    lead.value = await leadsApi.card(query.value.trim())
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || 'Ошибка'
  } finally {
    loading.value = false
  }
}

function taskBadge(status) {
  if (status === 'completed') return 'badge-ready'
  if (status === 'failed') return 'badge-unhealthy'
  return 'badge-updating'
}

function formatData(d) {
  if (typeof d === 'string') return d
  return JSON.stringify(d, null, 2)
}
</script>
