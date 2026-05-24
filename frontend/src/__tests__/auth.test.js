import { describe, it, expect, beforeEach } from 'vitest'
import { useAuth } from '../store/auth'

describe('auth store', () => {
  beforeEach(() => {
    localStorage.clear()
    const { logout } = useAuth()
    logout()
  })

  it('is unauthenticated by default', () => {
    const { isAuthenticated } = useAuth()
    expect(isAuthenticated.value).toBe(false)
  })

  it('setSession persists to localStorage', () => {
    const { setSession, isAuthenticated, username, token } = useAuth()
    setSession('tok123', 'admin')
    expect(isAuthenticated.value).toBe(true)
    expect(token.value).toBe('tok123')
    expect(username.value).toBe('admin')
    expect(localStorage.getItem('admin_token')).toBe('tok123')
  })

  it('logout clears state and storage', () => {
    const { setSession, logout, isAuthenticated, token } = useAuth()
    setSession('t', 'u')
    logout()
    expect(isAuthenticated.value).toBe(false)
    expect(token.value).toBe('')
    expect(localStorage.getItem('admin_token')).toBeNull()
  })
})
