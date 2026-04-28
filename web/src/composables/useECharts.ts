import { ref, onMounted, onBeforeUnmount, type Ref } from 'vue'
import * as echarts from 'echarts/core'
import type { EChartsCoreOption } from 'echarts/core'

export interface UseEChartsOptions {
  lazy?: boolean
  onChartReady?: (chart: echarts.ECharts) => void
}

/**
 * ECharts 封装 Hook - 自动初始化和清理图表实例
 *
 * @example
 * const { chartRef, setOption, resize } = useECharts()
 *
 * <template>
 *   <div ref="chartRef" class="chart-container"></div>
 * </template>
 */
export function useECharts(options: UseEChartsOptions = {}) {
  const { lazy = false, onChartReady } = options
  const chartRef: Ref<HTMLElement | null> = ref(null)
  let chartInstance: echarts.ECharts | null = null

  const initChart = () => {
    if (!chartRef.value || chartInstance) return
    chartInstance = echarts.init(chartRef.value)
    onChartReady?.(chartInstance)
  }

  const setOption = (option: EChartsCoreOption, notMerge = false, lazyUpdate = false) => {
    if (!chartInstance) {
      if (lazy) {
        // 懒加载模式下，先初始化再设置 option
        initChart()
      } else {
        console.warn('ECharts instance not initialized. Use lazy: true option or call initChart first.')
        return
      }
    }
    chartInstance?.setOption(option, notMerge, lazyUpdate)
  }

  const resize = () => {
    chartInstance?.resize()
  }

  const dispose = () => {
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
  }

  const clear = () => {
    chartInstance?.clear()
  }

  const showLoading = () => {
    chartInstance?.showLoading()
  }

  const hideLoading = () => {
    chartInstance?.hideLoading()
  }

  // 自动初始化（非懒加载模式）
  onMounted(() => {
    if (!lazy) {
      initChart()
    }
  })

  // 自动清理
  onBeforeUnmount(() => {
    dispose()
  })

  return {
    chartRef,
    setOption,
    resize,
    dispose,
    clear,
    showLoading,
    hideLoading,
    initChart
  }
}
