<template>
  <component 
    :is="as" 
    class="star-border-container" 
    :class="customClass"
    v-bind="$attrs"
  >
    <div 
      class="border-gradient-bottom"
      :style="{
        background: `radial-gradient(30% 65px at bottom center, ${color}, transparent)`,
        animationDuration: speed,
        animationDirection: 'reverse'
      }"
    ></div>
    <div 
      class="border-gradient-top"
      :style="{
        background: `radial-gradient(30% 65px at top center, ${color}, transparent)`,
        animationDuration: speed,
      }"
    ></div>
    <div class="inner-content">
      <slot></slot>
    </div>
  </component>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  as?: string | object
  customClass?: string
  color?: string
  speed?: string
  thickness?: number
}>(), {
  as: 'button',
  customClass: '',
  color: 'var(--el-color-primary, #409eff)',
  speed: '6s',
  thickness: 1
})
</script>

<style scoped>
.star-border-container {
  position: relative;
  display: inline-block;
  padding: 1px; /* 依赖于厚度，这里默认 1px，可通过动态style覆盖，但简单起见固定 */
  border-radius: 8px; /* 适应 el-button 的圆角 */
  overflow: hidden;
  border: none;
  background: transparent;
  cursor: pointer;
  vertical-align: middle;
}

.border-gradient-bottom,
.border-gradient-top {
  position: absolute;
  width: 300%;
  height: 300%;
  left: -100%;
  top: -100%;
  z-index: 0;
  animation: star-border-spin linear infinite;
}

.inner-content {
  position: relative;
  z-index: 1;
  background: var(--el-bg-color, #ffffff);
  border-radius: 7px; /* 比外层少 1px */
  height: 100%;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 如果 slot 里是 el-button，让它填满并去除自身边框以完美融合 */
.inner-content :deep(.el-button) {
  margin: 0;
  border: none !important;
  border-radius: inherit;
  width: 100%;
  height: 100%;
}

@keyframes star-border-spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
