import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetricCard from '../components/MetricCard.vue'

describe('MetricCard', () => {
  it('renders label, value, odz', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'Faithfulness', value: 0.87, odz: 0.8 },
    })
    expect(wrapper.text()).toContain('Faithfulness')
    expect(wrapper.text()).toContain('0.87')
    expect(wrapper.text()).toContain('0.8')
  })

  it('uses success color when value >= odz', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'X', value: 0.9, odz: 0.8 },
    })
    expect(wrapper.find('.text-success').exists()).toBe(true)
  })

  it('uses danger color when value < odz', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'X', value: 0.5, odz: 0.8 },
    })
    expect(wrapper.find('.text-danger').exists()).toBe(true)
  })

  it('appends unit to value', () => {
    const wrapper = mount(MetricCard, {
      props: { label: 'TPS', value: 6.2, odz: 5.0, unit: ' т/с' },
    })
    expect(wrapper.text()).toContain('6.2 т/с')
  })
})
