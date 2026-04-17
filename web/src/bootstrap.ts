import { createApp, type App as VueApp } from 'vue'
import type { Router } from 'vue-router'
import { createPinia } from 'pinia'

import App from './App.vue'
import { initTheme } from './composables'
import elementPlusPlugin from './plugins/element-plus'
import router from './router'

import 'element-plus/dist/index.css'
import './assets/design-system.css'
import './assets/visual-hierarchy.css'
import './assets/animations.css'
import './assets/transitions.css'
import './assets/main.css'

export interface BootstrappedApp {
  app: VueApp
  router: Router
}

export function bootstrapApp(
  mountTarget: string | Element = '#app',
  appRouter: Router = router,
): BootstrappedApp {
  initTheme()

  const app = createApp(App)

  app.use(createPinia())
  app.use(appRouter)
  app.use(elementPlusPlugin)

  app.mount(mountTarget)

  return {
    app,
    router: appRouter,
  }
}
