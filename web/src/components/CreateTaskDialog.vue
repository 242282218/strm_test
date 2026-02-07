<template>
  <el-dialog
    v-model="visible"
    title="新建任务"
    width="600px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="120px"
    >
      <el-form-item label="任务类型" prop="task_type">
        <el-select v-model="form.task_type" style="width: 100%" @change="onTaskTypeChange">
          <el-option label="STRM生成" value="strm_generation" />
          <el-option label="文件同步" value="file_sync" />
          <el-option label="媒体刮削" value="scrape" />
          <el-option label="智能重命名" value="rename" />
        </el-select>
      </el-form-item>

      <el-form-item label="优先级" prop="priority">
        <el-radio-group v-model="form.priority">
          <el-radio-button label="low">低</el-radio-button>
          <el-radio-button label="normal">中</el-radio-button>
          <el-radio-button label="high">高</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <!-- STRM生成参数 -->
      <template v-if="form.task_type === 'strm_generation'">
        <el-form-item label="网盘路径" prop="params.source_dir">
          <el-input v-model="form.params.source_dir" placeholder="/video" />
          <div class="form-tip">要扫描的夸克网盘目录路径</div>
        </el-form-item>
        <el-form-item label="本地路径" prop="params.target_dir">
          <el-input v-model="form.params.target_dir" placeholder="./strm" />
          <div class="form-tip">STRM文件保存的本地目录</div>
        </el-form-item>
        <el-form-item label="媒体类型" prop="params.media_type">
          <el-select v-model="form.params.media_type" style="width: 100%">
            <el-option label="自动识别" value="auto" />
            <el-option label="电影" value="movie" />
            <el-option label="电视剧" value="tv" />
          </el-select>
        </el-form-item>
        <el-form-item label="递归扫描">
          <el-switch v-model="form.params.recursive" />
          <span class="form-tip ml-2">扫描子目录</span>
        </el-form-item>
      </template>

      <!-- 文件同步参数 -->
      <template v-if="form.task_type === 'file_sync'">
        <el-form-item label="网盘路径" prop="params.remote_path">
          <el-input v-model="form.params.remote_path" placeholder="/video" />
          <div class="form-tip">要同步的夸克网盘目录</div>
        </el-form-item>
        <el-form-item label="本地路径" prop="params.local_path">
          <el-input v-model="form.params.local_path" placeholder="./downloads" />
          <div class="form-tip">文件保存的本地目录</div>
        </el-form-item>
        <el-form-item label="同步模式" prop="params.sync_mode">
          <el-select v-model="form.params.sync_mode" style="width: 100%">
            <el-option label="下载" value="download" />
            <el-option label="上传" value="upload" />
            <el-option label="双向同步" value="bidirectional" />
          </el-select>
        </el-form-item>
      </template>

      <!-- 媒体刮削参数 -->
      <template v-if="form.task_type === 'scrape'">
        <el-form-item label="刮削路径" prop="params.path">
          <el-input v-model="form.params.path" placeholder="./strm" />
          <div class="form-tip">要刮削的本地目录</div>
        </el-form-item>
        <el-form-item label="媒体类型" prop="params.media_type">
          <el-select v-model="form.params.media_type" style="width: 100%">
            <el-option label="自动识别" value="auto" />
            <el-option label="电影" value="movie" />
            <el-option label="电视剧" value="tv" />
          </el-select>
        </el-form-item>
        <el-form-item label="强制更新">
          <el-switch v-model="form.params.force_update" />
          <span class="form-tip ml-2">重新刮削已存在的媒体信息</span>
        </el-form-item>
      </template>

      <!-- 智能重命名参数 -->
      <template v-if="form.task_type === 'rename'">
        <el-form-item label="目标路径" prop="params.path">
          <el-input v-model="form.params.path" placeholder="./downloads" />
          <div class="form-tip">要重命名的文件目录</div>
        </el-form-item>
        <el-form-item label="命名模式" prop="params.pattern">
          <el-select v-model="form.params.pattern" style="width: 100%">
            <el-option label="标准模式" value="standard" />
            <el-option label="Plex模式" value="plex" />
            <el-option label="Emby模式" value="emby" />
          </el-select>
        </el-form-item>
        <el-form-item label="预览模式">
          <el-switch v-model="form.params.preview" />
          <span class="form-tip ml-2">只预览不实际重命名</span>
        </el-form-item>
      </template>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        创建任务
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { createTask, type TaskCreateRequest } from '@/api/tasks'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'success': []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive<TaskCreateRequest>({
  task_type: 'strm_generation',
  priority: 'normal',
  params: {
    source_dir: '/video',
    target_dir: './strm',
    media_type: 'auto',
    recursive: true
  }
})

const getRules = (): FormRules => {
  const baseRules: FormRules = {
    task_type: [{ required: true, message: '请选择任务类型', trigger: 'change' }],
    priority: [{ required: true, message: '请选择优先级', trigger: 'change' }]
  }

  // 根据任务类型添加特定规则
  if (form.task_type === 'strm_generation') {
    baseRules['params.source_dir'] = [{ required: true, message: '请输入网盘路径', trigger: 'blur' }]
    baseRules['params.target_dir'] = [{ required: true, message: '请输入本地路径', trigger: 'blur' }]
  } else if (form.task_type === 'file_sync') {
    baseRules['params.remote_path'] = [{ required: true, message: '请输入网盘路径', trigger: 'blur' }]
    baseRules['params.local_path'] = [{ required: true, message: '请输入本地路径', trigger: 'blur' }]
  } else if (form.task_type === 'scrape') {
    baseRules['params.path'] = [{ required: true, message: '请输入刮削路径', trigger: 'blur' }]
  } else if (form.task_type === 'rename') {
    baseRules['params.path'] = [{ required: true, message: '请输入目标路径', trigger: 'blur' }]
  }

  return baseRules
}

const rules = computed(() => getRules())

const onTaskTypeChange = () => {
  // 重置参数
  form.params = {}

  // 根据任务类型设置默认参数
  switch (form.task_type) {
    case 'strm_generation':
      form.params = {
        source_dir: '/video',
        target_dir: './strm',
        media_type: 'auto',
        recursive: true
      }
      break
    case 'file_sync':
      form.params = {
        remote_path: '/video',
        local_path: './downloads',
        sync_mode: 'download'
      }
      break
    case 'scrape':
      form.params = {
        path: './strm',
        media_type: 'auto',
        force_update: false
      }
      break
    case 'rename':
      form.params = {
        path: './downloads',
        pattern: 'standard',
        preview: true
      }
      break
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      await createTask({
        task_type: form.task_type,
        priority: form.priority,
        params: form.params
      })
      ElMessage.success('任务创建成功')
      emit('success')
      handleClose()
    } catch (error: unknown) {
      ElMessage.error('任务创建失败')
    } finally {
      submitting.value = false
    }
  })
}

const handleClose = () => {
  visible.value = false
  formRef.value?.resetFields()
  // 重置为默认值
  form.task_type = 'strm_generation'
  form.priority = 'normal'
  onTaskTypeChange()
}
</script>

<style scoped>
.form-tip {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.ml-2 {
  margin-left: 8px;
}
</style>
