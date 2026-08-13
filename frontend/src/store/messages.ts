import { ref, computed } from 'vue'

// 模拟消息数据
export const messages = ref(
  Array.from({ length: 30 }).map((_, index) => {
    const senders = ['消息A', '消息B', '消息C']
    return {
      id: index + 1,
      sender: senders[index % 3],
      content: `这是一条占位消息测试文本。这是消息 ${index + 1} 的详细内容。双击可以查看这部分被展开的消息。这里增加一些文字来测试长文本的情况。`,
      time: '2026-07-20 10:00',
      isRead: index >= 5 // 默认前 5 条未读
    }
  })
)

// 计算未读消息数量
export const unreadCount = computed(() => {
  return messages.value.filter(msg => !msg.isRead).length
})