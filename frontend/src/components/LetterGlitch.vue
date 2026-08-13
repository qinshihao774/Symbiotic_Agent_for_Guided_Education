<template>
  <div ref="container" class="letter-glitch-container">
    <canvas ref="canvas"></canvas>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const container = ref<HTMLElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)

let animationFrameId: number
let letters: string[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&^*".split("")

onMounted(() => {
  const ctx = canvas.value?.getContext('2d')
  if (!ctx || !canvas.value || !container.value) return

  let width = container.value.clientWidth
  let height = container.value.clientHeight
  canvas.value.width = width
  canvas.value.height = height

  const fontSize = 16
  const columns = width / fontSize
  const drops: number[] = []

  for (let x = 0; x < columns; x++) {
    drops[x] = 1
  }

  const draw = () => {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.05)'
    ctx.fillRect(0, 0, width, height)

    ctx.fillStyle = '#58bc82' // template.txt 中定义的绿色 --clr
    ctx.font = `${fontSize}px monospace`

    for (let i = 0; i < drops.length; i++) {
      const text = letters[Math.floor(Math.random() * letters.length)]
      ctx.fillText(text, i * fontSize, drops[i] * fontSize)

      if (drops[i] * fontSize > height && Math.random() > 0.975) {
        drops[i] = 0
      }
      drops[i]++
    }

    animationFrameId = requestAnimationFrame(draw)
  }

  draw()

  const handleResize = () => {
    if (!container.value || !canvas.value) return
    width = container.value.clientWidth
    height = container.value.clientHeight
    canvas.value.width = width
    canvas.value.height = height
  }

  window.addEventListener('resize', handleResize)

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    cancelAnimationFrame(animationFrameId)
  })
})
</script>

<style scoped>
.letter-glitch-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #000;
}

canvas {
  display: block;
}
</style>
