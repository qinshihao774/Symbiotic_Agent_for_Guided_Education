<template>
  <BorderGlow class="messages-page" background-color="transparent">
    <!-- 主页面，当弹窗打开时模糊背景 -->
    <div :class="['glass-card', 'page-container', { 'blur-bg': selectedMessage }]">
      <h2 class="page-title">消息提醒</h2>
      
      <!-- 列表区域，独立滚动 -->
      <div class="list-container scroll-area">
        <div class="message-list">
          <div 
            v-for="msg in messages" 
            :key="msg.id" 
            class="message-item"
            :class="{ 'unread-item': !msg.isRead }"
            @dblclick="openMessageDetail(msg)"
          >
            <!-- 未读红点提示 -->
            <div class="unread-dot" v-if="!msg.isRead"></div>
            
            <div class="msg-sender" :class="{ 'font-bold': !msg.isRead }">{{ msg.sender }}:</div>
            <div class="msg-content" :class="{ 'font-bold': !msg.isRead }">{{ msg.content }}</div>
            <div class="msg-time">{{ msg.time }}</div>
          </div>
        </div>
        <div class="spacer"></div>
      </div>
    </div>

    <!-- 消息详情悬浮弹窗 -->
    <transition name="fade-scale">
      <div v-if="selectedMessage" class="modal-overlay" @click.self="closeMessageDetail">
        <div class="modal-content glass-card">
          <div class="modal-header">
            <h3>消息详情</h3>
            <el-button link class="close-btn" @click="closeMessageDetail">关闭</el-button>
          </div>
          <div class="modal-body scroll-area">
            <div class="detail-sender"><strong>发送者：</strong> {{ selectedMessage.sender }}</div>
            <div class="detail-time"><strong>时间：</strong> {{ selectedMessage.time }}</div>
            <div class="divider"></div>
            <div class="detail-text">{{ selectedMessage.content }}</div>
          </div>
        </div>
      </div>
    </transition>
  </BorderGlow>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import BorderGlow from '@/components/BorderGlow.vue'
import { messages } from '@/store/messages'

// 当前选中的消息，用于展示详情弹窗
const selectedMessage = ref<any>(null)

// 双击打开消息详情，并将消息标记为已读
const openMessageDetail = (msg: any) => {
  selectedMessage.value = msg
  if (!msg.isRead) {
    msg.isRead = true
  }
}

// 关闭消息详情
const closeMessageDetail = () => {
  selectedMessage.value = null
}
</script>

<style scoped>
.messages-page {
  color: #000;
  height: calc(100vh - 170px);
  margin: 20px;
  position: relative; /* 为绝对定位的弹窗提供参考 */
}

.page-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #e5e8e4;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.5);
  transition: filter 0.3s ease;
}

/* 当弹窗出现时，背景模糊化 */
.blur-bg {
  filter: blur(8px);
  pointer-events: none; /* 防止背景被点击 */
}

.page-title {
  margin: 0 0 16px 0;
  font-size: 1.2rem;
  font-weight: bold;
  color: #000;
  flex-shrink: 0;
}

.list-container {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.scroll-area {
  overflow-y: auto;
  padding-right: 8px;
}

/* 自定义滚动条 */
.scroll-area::-webkit-scrollbar {
  width: 6px;
}
.scroll-area::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.02);
  border-radius: 4px;
}
.scroll-area::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 4px;
}
.scroll-area::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

.spacer {
  height: 16px;
}

/* 消息列表样式 */
.message-list {
  display: flex;
  flex-direction: column;
}

.message-item {
  display: flex;
  align-items: center;
  padding: 16px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  transition: background-color 0.2s;
  cursor: pointer;
  position: relative;
}

.message-item:hover {
  background-color: rgba(255, 255, 255, 0.4);
  border-radius: 8px;
}

.message-item:last-child {
  border-bottom: none;
}

/* 未读消息项特殊样式 */
.unread-item {
  background-color: rgba(255, 255, 255, 0.2);
}

.unread-dot {
  width: 8px;
  height: 8px;
  background-color: #f56c6c;
  border-radius: 50%;
  margin-right: 12px;
  flex-shrink: 0;
}

.msg-sender {
  width: 80px;
  flex-shrink: 0;
}

.msg-content {
  flex: 1;
  margin: 0 16px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #333;
}

.font-bold {
  font-weight: bold;
  color: #000;
}

.msg-time {
  width: 140px;
  text-align: right;
  color: #666;
  font-size: 0.9rem;
  flex-shrink: 0;
}

/* --- 弹窗样式 --- */
.modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 12px;
}

.modal-content {
  width: 60%;
  max-width: 600px;
  min-height: 300px;
  max-height: 80%;
  display: flex;
  flex-direction: column;
  padding: 24px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.8);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: bold;
}

.close-btn {
  font-size: 1rem;
  color: #666;
}
.close-btn:hover {
  color: #f56c6c;
}

.modal-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  font-size: 1rem;
  line-height: 1.6;
}

.detail-sender, .detail-time {
  margin-bottom: 8px;
  color: #333;
}

.divider {
  height: 1px;
  background: rgba(0, 0, 0, 0.1);
  margin: 16px 0;
}

.detail-text {
  color: #000;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 弹窗过渡动画 */
.fade-scale-enter-active,
.fade-scale-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.fade-scale-enter-from,
.fade-scale-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>