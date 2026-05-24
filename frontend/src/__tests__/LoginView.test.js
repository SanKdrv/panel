import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LoginView from '../views/LoginView.vue'

vi.mock('../api/endpoints', () => ({
  authApi: {
    login: vi.fn(),
  },
}))

import { authApi } from '../api/endpoints'

const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: {} }),
}))

describe('LoginView', () => {
  beforeEach(() => {
    localStorage.clear()
    pushMock.mockReset()
    authApi.login.mockReset()
  })

  it('submits credentials and redirects on success', async () => {
    authApi.login.mockResolvedValue({ access_token: 'tok', expires_in: 3600 })
    const wrapper = mount(LoginView)
    await wrapper.find('input[type="text"]').setValue('admin')
    await wrapper.find('input[type="password"]').setValue('secret')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(authApi.login).toHaveBeenCalledWith('admin', 'secret')
    expect(pushMock).toHaveBeenCalledWith('/dashboard')
    expect(localStorage.getItem('admin_token')).toBe('tok')
  })

  it('shows error on failed login', async () => {
    authApi.login.mockRejectedValue({
      response: { data: { detail: 'Invalid' } },
    })
    const wrapper = mount(LoginView)
    await wrapper.find('input[type="password"]').setValue('wrong')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text()).toContain('Invalid')
    expect(pushMock).not.toHaveBeenCalled()
  })
})
