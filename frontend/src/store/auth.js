import { ref, computed } from 'vue'

const TOKEN_KEY = 'admin_token'
const USER_KEY = 'admin_user'

const token = ref(localStorage.getItem(TOKEN_KEY) || '')
const username = ref(localStorage.getItem(USER_KEY) || '')

export function useAuth() {
  const isAuthenticated = computed(() => !!token.value)

  function setSession(newToken, newUsername) {
    token.value = newToken
    username.value = newUsername
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, newUsername)
  }

  function logout() {
    token.value = ''
    username.value = ''
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return {
    token,
    username,
    isAuthenticated,
    setSession,
    logout,
  }
}
