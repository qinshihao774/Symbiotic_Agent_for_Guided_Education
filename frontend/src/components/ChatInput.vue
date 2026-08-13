<template>
  <div class="chat-input-container">
    <div class="messageBox">
      <div class="fileUploadWrapper">
        <label for="file">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 337 337">
            <circle
              stroke-width="20"
              stroke="#6c6c6c"
              fill="none"
              r="158.5"
              cy="168.5"
              cx="168.5"
            ></circle>
            <path
              stroke-linecap="round"
              stroke-width="25"
              stroke="#6c6c6c"
              d="M167.759 79V259"
            ></path>
            <path
              stroke-linecap="round"
              stroke-width="25"
              stroke="#6c6c6c"
              d="M79 167.138H259"
            ></path>
          </svg>
          <span class="tooltip">Add an image</span>
        </label>
        <input type="file" id="file" name="file" />
      </div>
      <textarea
        required
        placeholder="输入你的问题... (Enter 发送, Shift+Enter 换行)"
        id="messageInput"
        v-model="input"
        ref="textareaRef"
        @keydown="handleKeydown"
        @input="adjustHeight"
        :disabled="loading"
      ></textarea>
      <button
        id="sendButton"
        @click="loading ? emit('cancel') : handleSend()"
        :disabled="!loading && !input.trim()"
        :title="loading ? '停止执行' : '发送'"
      >
        <span v-if="loading" class="stop-icon" aria-label="停止执行" />
        <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 664 663">
          <path
            fill="none"
            d="M646.293 331.888L17.7538 17.6187L155.245 331.888M646.293 331.888L17.753 646.157L155.245 331.888M646.293 331.888L318.735 330.228L155.245 331.888"
          ></path>
          <path
            stroke-linejoin="round"
            stroke-linecap="round"
            stroke-width="33.67"
            stroke="#6c6c6c"
            d="M646.293 331.888L17.7538 17.6187L155.245 331.888M646.293 331.888L17.753 646.157L155.245 331.888M646.293 331.888L318.735 330.228L155.245 331.888"
          ></path>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

const props = defineProps<{ loading: boolean }>()
const emit = defineEmits<{
  send: [content: string]
  cancel: []
}>()

const input = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function handleSend() {
  const text = input.value.trim()
  if (!text || props.loading) return
  emit('send', text)
  input.value = ''
  nextTick(() => {
    resetHeight()
  })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function adjustHeight() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = '24px'
  const scrollHeight = el.scrollHeight
  el.style.height = Math.min(scrollHeight, 64) + 'px'
}

function resetHeight() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = '24px'
}

watch(input, () => {
  nextTick(adjustHeight)
})
</script>

<style scoped>
.chat-input-container {
  padding: 16px;
  background: transparent;
  display: flex;
  justify-content: center;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.messageBox {
  width: 100%;
  max-width: 1200px;
  min-height: 44px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  background-color: #ffffff;
  padding: 10px 15px;
  border-radius: 10px;
  border: 1px solid #ccc;
  box-sizing: border-box;
}

.messageBox:focus-within {
  border: 1px solid #999;
}

.fileUploadWrapper {
  width: fit-content;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: Arial, Helvetica, sans-serif;
}

#file {
  display: none;
}

.fileUploadWrapper label {
  cursor: pointer;
  width: fit-content;
  height: fit-content;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.fileUploadWrapper label svg {
  height: 18px;
}

.fileUploadWrapper label svg path {
  transition: all 0.3s;
}

.fileUploadWrapper label svg circle {
  transition: all 0.3s;
}

.fileUploadWrapper label:hover svg path {
  stroke: #000;
}

.fileUploadWrapper label:hover svg circle {
  stroke: #000;
  fill: #e0e0e0;
}

.fileUploadWrapper label:hover .tooltip {
  display: block;
  opacity: 1;
}

.tooltip {
  position: absolute;
  top: -40px;
  display: none;
  opacity: 0;
  color: #000;
  font-size: 10px;
  text-wrap: nowrap;
  background-color: #fff;
  padding: 6px 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  box-shadow: 0px 5px 10px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
  z-index: 10;
}

#messageInput {
  flex: 1;
  min-height: 24px;
  height: 24px;
  background-color: transparent;
  outline: none;
  border: none;
  padding: 2px 10px;
  color: #000;
  resize: none;
  line-height: 20px;
  font-size: 14px;
  font-family: inherit;
  overflow-y: auto;
}

#messageInput::-webkit-scrollbar {
  width: 4px;
}
#messageInput::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 2px;
}

#messageInput:focus ~ #sendButton svg path,
#messageInput:valid ~ #sendButton svg path {
  fill: #e0e0e0;
  stroke: #000;
}

#sendButton {
  width: fit-content;
  height: 24px;
  background-color: transparent;
  outline: none;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
}

#sendButton svg {
  height: 18px;
  transition: all 0.3s;
}

#sendButton svg path {
  transition: all 0.3s;
}

.stop-icon {
  width: 11px;
  height: 11px;
  border-radius: 2px;
  background: #475569;
}

#sendButton:hover svg path {
  fill: #e0e0e0;
  stroke: #000;
}

#sendButton:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
</style>
