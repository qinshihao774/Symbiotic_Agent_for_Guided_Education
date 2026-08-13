import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useLearningStore = defineStore('learning', () => {
  const progress = ref<any>(null)
  const plan = ref<any>(null)
  return { progress, plan }
})
