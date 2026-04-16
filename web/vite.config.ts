import { defineConfig, loadEnv, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import viteCompression from 'vite-plugin-compression'
import { visualizer } from 'rollup-plugin-visualizer'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production'
  const env = loadEnv(mode, process.cwd(), '')
  const devProxyTarget = env.VITE_API_PROXY_TARGET?.trim() || 'http://127.0.0.1:8000'

  const plugins: Plugin[] = [vue()]

  // 生产环境压缩配置
  if (isProduction) {
    // Gzip 压缩
    plugins.push(
      viteCompression({
        algorithm: 'gzip',
        ext: '.gz',
        threshold: 1024, // 大于 1KB 的文件才压缩
        deleteOriginFile: false
      })
    )
    // Brotli 压缩
    plugins.push(
      viteCompression({
        algorithm: 'brotliCompress',
        ext: '.br',
        threshold: 1024,
        deleteOriginFile: false
      })
    )
    // 构建分析
    plugins.push(
      visualizer({
        filename: 'dist/stats.html',
        open: false,
        gzipSize: true,
        brotliSize: true
      })
    )
  }

  return {
    plugins,
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    },
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: devProxyTarget,
          changeOrigin: true
        },
        '/dav': {
          target: devProxyTarget,
          changeOrigin: true
        }
      }
    },
    build: {
      // 目标环境：现代浏览器支持 esnext
      target: 'esnext',
      // 代码分割配置
      rollupOptions: {
        output: {
          // 精细化代码分割策略
          manualChunks: (id) => {
            // 核心框架：vue, vue-router, pinia
            if (id.includes('node_modules/vue/') ||
                id.includes('node_modules/@vue/') ||
                id.includes('node_modules/vue-router/') ||
                id.includes('node_modules/pinia/')) {
              return 'vendor'
            }
            // UI 组件库：element-plus
            if (id.includes('node_modules/element-plus/') ||
                id.includes('node_modules/@element-plus/')) {
              return 'ui'
            }
            // 图表库：echarts/zrender 拆分为更细的公共块，避免单个超大 chunk
            if (id.includes('node_modules/echarts/charts/')) {
              return 'charts-series'
            }
            if (id.includes('node_modules/echarts/components/')) {
              return 'charts-components'
            }
            if (id.includes('node_modules/echarts/renderers/') ||
                id.includes('node_modules/zrender/')) {
              return 'charts-renderer'
            }
            if (id.includes('node_modules/echarts/')) {
              return 'charts-core'
            }
            // 工具库：axios 及其依赖
            if (id.includes('node_modules/axios/') ||
                id.includes('node_modules/follow-redirects/') ||
                id.includes('node_modules/proxy-from-env/') ||
                id.includes('node_modules/asynckit/') ||
                id.includes('node_modules/combined-stream/') ||
                id.includes('node_modules/mime-types/') ||
                id.includes('node_modules/form-data/')) {
              return 'utils'
            }
            // 其他 node_modules
            if (id.includes('node_modules/')) {
              return 'vendor'
            }
          },
          // 入口文件名
          entryFileNames: 'assets/js/[name]-[hash].js',
          // chunk 文件名
          chunkFileNames: 'assets/js/[name]-[hash].js',
          // 静态资源文件名
          assetFileNames: (assetInfo) => {
            const name = assetInfo.name || ''
            if (/\.(gif|jpe?g|png|svg|webp|ico)$/i.test(name)) {
              return 'assets/images/[name]-[hash][extname]'
            }
            if (/\.css$/i.test(name)) {
              return 'assets/css/[name]-[hash][extname]'
            }
            if (/\.(woff2?|eot|ttf|otf)$/i.test(name)) {
              return 'assets/fonts/[name]-[hash][extname]'
            }
            return 'assets/[name]-[hash][extname]'
          },
          // 分割大包，避免单个 chunk 过大
          inlineDynamicImports: false
        }
      },
      // 小于 4KB 的资源内联为 base64
      assetsInlineLimit: 4096,
      // 启用 CSS 代码分割
      cssCodeSplit: true,
      // 启用 source map（生产环境可选关闭）
      sourcemap: !isProduction,
      // 压缩配置 (使用 esbuild，比 terser 更快)
      minify: isProduction ? 'esbuild' : false,
      esbuild: isProduction ? {
        drop: ['console', 'debugger'],
        legalComments: 'none'
      } : undefined,
      // chunk 大小警告阈值（提高到 1MB，因为图表库本身较大）
      chunkSizeWarningLimit: 1000
    },
    // 优化依赖预构建
    optimizeDeps: {
      include: [
        'vue',
        'vue-router',
        'pinia',
        'element-plus',
        'axios',
        'echarts/core',
        'echarts/renderers'
      ],
      exclude: ['@element-plus/icons-vue']
    },
    // CSS 配置
    css: {
      devSourcemap: true,
      preprocessorOptions: {
        scss: {
          additionalData: ``
        }
      }
    }
  }
})
