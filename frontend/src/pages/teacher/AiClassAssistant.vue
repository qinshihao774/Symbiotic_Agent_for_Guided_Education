<template>
  <div class="ai-assistant-page">
    <div class="chat-header">
      <h3>AI 班级分析助手</h3>
      <span class="chat-subtitle">通过 Agent 接入数据库，查询班级情况与学生知识点掌握度</span>
    </div>

    <div class="chat-container">
      <div class="chat-messages">
        <div class="empty-state">
          <el-icon :size="48" color="#c0c4cc"><MessageCircle /></el-icon>
          <p>向 AI 班级分析助手提问，例如：</p>
          <div class="suggestion-chips">
            <el-tag
              v-for="q in suggestions"
              :key="q"
              class="suggestion-chip"
              type="info"
              effect="plain"
            >
              {{ q }}
            </el-tag>
          </div>
        </div>
      </div>
      <div class="chat-input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="3"
          placeholder="输入问题，例如：班级平均掌握度最低的知识点有哪些？"
          resize="none"
        />
        <el-button type="primary" :disabled="!inputText.trim()" class="send-btn">
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { MessageCircle } from 'lucide-vue-next'

const inputText = ref('')

const suggestions = [
  '班级平均掌握度最低的知识点有哪些？',
  '最近一周哪些学生退步明显？',
  '数据结构的哪个章节需要重点复习？',
  '生成班级整体学情摘要',
]
</script>

<style scoped>
.ai-assistant-page { display: flex; flex-direction: column; height: calc(100vh - 48px); }
.chat-header { padding: 16px 20px; border-bottom: 1px solid rgba(0,0,0,0.06); }
.chat-header h3 { margin: 0; font-size: 1.1rem; }
.chat-subtitle { font-size: 0.85rem; color: #999; }
.chat-container { flex: 1; display: flex; flex-direction: column; }
.chat-messages { flex: 1; display: flex; align-items: center; justify-content: center; padding: 24px; }
.empty-state { text-align: center; color: #999; }
.empty-state p { margin: 16px 0; }
.suggestion-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.suggestion-chip { cursor: pointer; }
.chat-input-area { padding: 16px 20px; border-top: 1px solid rgba(0,0,0,0.06); display: flex; gap: 12px; align-items: flex-end; }
.send-btn { flex-shrink: 0; }
</style>
