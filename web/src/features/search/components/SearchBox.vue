<template>
  <div class="search-box-container">
    <div class="search-box" :class="{ 'focused': isFocused }">
      <el-icon class="search-icon" :size="24"><Search /></el-icon>
      <input
        ref="inputRef"
        v-model="localQuery"
        type="text"
        class="search-input"
        :placeholder="placeholder"
        @focus="isFocused = true"
        @blur="isFocused = false"
        @keyup.enter="handleSearch"
      />
      <el-button
        type="primary"
        size="large"
        class="search-btn"
        :loading="loading"
        @click="handleSearch"
      >
        搜索
      </el-button>
    </div>

    <!-- Quick Tags -->
    <div class="quick-tags">
      <span class="tags-label">热门搜索：</span>
      <el-tag
        v-for="tag in hotTags"
        :key="tag"
        class="quick-tag"
        effect="plain"
        size="small"
        @click="handleTagClick(tag)"
      >
        {{ tag }}
      </el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Search } from '@/components/icons'

const props = withDefaults(defineProps<{
  modelValue?: string
  loading?: boolean
  hotTags?: string[]
  placeholder?: string
}>(), {
  modelValue: '',
  loading: false,
  hotTags: () => ['流浪地球', '三体', '狂飙', '奥本海默', '芭比', '封神'],
  placeholder: '搜索电影、电视剧、动漫...'
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'search': [keyword: string]
}>()

const localQuery = ref(props.modelValue)
const isFocused = ref(false)
const inputRef = ref<HTMLInputElement>()

watch(() => props.modelValue, (val) => {
  localQuery.value = val
})

watch(localQuery, (val) => {
  emit('update:modelValue', val)
})

const handleSearch = () => {
  if (localQuery.value.trim()) {
    emit('search', localQuery.value.trim())
  }
}

const handleTagClick = (tag: string) => {
  localQuery.value = tag
  emit('search', tag)
}

defineExpose({
  focus: () => inputRef.value?.focus()
})
</script>

<style scoped>
.search-box-container {
  max-width: 700px;
  margin: 0 auto;
}

.search-box {
  display: flex;
  align-items: center;
  background: var(--bg-primary);
  border-radius: var(--radius-2xl);
  padding: 8px;
  box-shadow: var(--shadow-lg), 0 0 0 1px var(--border-color);
  transition: all var(--transition-normal);
}

.search-box.focused {
  box-shadow: var(--shadow-xl), 0 0 0 2px var(--primary-500);
  transform: translateY(-2px);
}

.search-icon {
  margin: 0 16px;
  color: var(--text-tertiary);
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 16px;
  padding: 12px 0;
  outline: none;
  color: var(--text-primary);
}

.search-input::placeholder {
  color: var(--text-tertiary);
}

.search-btn {
  border-radius: var(--radius-xl) !important;
  padding: 0 32px !important;
  height: 48px !important;
  font-size: 16px !important;
  font-weight: 600;
}

/* Quick Tags */
.quick-tags {
  margin-top: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
}

.tags-label {
  color: var(--text-secondary);
  font-size: 14px;
}

.quick-tag {
  cursor: pointer;
  transition: all var(--transition-fast);
}

.quick-tag:hover {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

@media (max-width: 768px) {
  .search-box {
    flex-direction: column;
    gap: 8px;
  }

  .search-input {
    width: 100%;
    text-align: center;
  }

  .search-btn {
    width: 100%;
  }
}
</style>
