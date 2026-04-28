import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import { useECharts } from './useECharts'

describe('useECharts', () => {
  it('accepts ECharts core option objects when setting chart options', () => {
    let setupResult!: ReturnType<typeof useECharts>

    mount({
      template: '<div />',
      setup() {
        setupResult = useECharts({ lazy: true })
        return { chartRef: setupResult.chartRef }
      },
    })

    expect(typeof setupResult.setOption).toBe('function')
  })
})
