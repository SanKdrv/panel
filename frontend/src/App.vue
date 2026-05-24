<template>
  <div v-if="!isAuthenticated">
    <router-view />
  </div>
  <div v-else>
    <AppSidebar />
    <main id="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuth } from './store/auth'
import AppSidebar from './components/AppSidebar.vue'

const { isAuthenticated } = useAuth()
</script>
