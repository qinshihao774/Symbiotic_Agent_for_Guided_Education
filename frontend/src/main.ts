import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'

import App from './App.vue'
import router from './router'
import './assets/index.css'
import 'element-plus/dist/index.css'
import 'highlight.js/styles/vs2015.css'
import 'katex/dist/katex.min.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.mount('#app')
