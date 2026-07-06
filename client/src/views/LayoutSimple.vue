<template>
  <el-container class="layout-container">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
      <div class="logo">
        <el-icon :size="24"><ChatDotSquare /></el-icon>
        <span v-show="!isCollapse" class="logo-text">企业知识库</span>
      </div>

      <el-menu
        :default-active="$route.path"
        :collapse="isCollapse"
        :router="true"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        class="aside-menu"
      >
        <el-menu-item index="/home">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>数据概览</template>
        </el-menu-item>
        <el-menu-item index="/knowledge-base">
          <el-icon><FolderOpened /></el-icon>
          <template #title>知识库管理</template>
        </el-menu-item>
        <el-menu-item index="/document">
          <el-icon><Document /></el-icon>
          <template #title>文档管理</template>
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>智能问答</template>
        </el-menu-item>
        <el-menu-item index="/chat-history">
          <el-icon><Clock /></el-icon>
          <template #title>对话历史</template>
        </el-menu-item>

        <el-menu-item index="/settings" class="menu-item-bottom">
          <el-icon><Setting /></el-icon>
          <template #title>设置</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <span class="page-title">{{ $route.meta.title }}</span>
        </div>
        <div class="header-right">
          <el-button text class="api-setting-trigger" @click="openApiSettings">
            API 设置
          </el-button>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <el-dialog v-model="dialogVisible" title="API 设置" width="500px">
    <el-skeleton :rows="4" animated :loading="dialogLoading">
      <el-form ref="formRef" :model="formData" :rules="rules" label-width="100px">
        <el-form-item label="API 来源" prop="api_source">
          <el-select
            v-model="formData.api_source"
            placeholder="请选择 API 来源"
            style="width: 100%"
            :disabled="dialogLoading"
            @change="handleSourceChange"
          >
            <el-option
              v-for="item in apiSourceOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="API 密钥" prop="api_key">
          <el-input
            v-model="formData.api_key"
            type="password"
            show-password
            placeholder="请输入 API 密钥"
            :disabled="dialogLoading"
            @blur="handleApiKeyBlur"
          />
        </el-form-item>

        <el-form-item label="模型" prop="model">
          <el-select
            v-model="formData.model"
            placeholder="请选择模型"
            style="width: 100%"
            :loading="modelsLoading"
            :disabled="dialogLoading || !formData.api_source"
            @visible-change="handleModelDropdownVisible"
          >
            <el-option
              v-for="item in modelOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </el-skeleton>

    <template #footer>
      <el-button :disabled="dialogLoading" @click="dialogVisible = false">取消</el-button>
      <el-button
        type="primary"
        :loading="submitLoading"
        :disabled="dialogLoading"
        @click="handleSubmit"
      >
        确定
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { getApiModels, getApiSettings, updateApiSettings } from '../api/settings'

const isCollapse = ref(false)
const dialogVisible = ref(false)
const dialogLoading = ref(false)
const submitLoading = ref(false)
const modelsLoading = ref(false)
const formRef = ref(null)

const apiSourceOptions = ref([])
const modelOptions = ref([])
const apiKeys = ref({})
const activeSource = ref('deepseek')

const formData = reactive({
  api_source: 'deepseek',
  api_key: '',
  model: ''
})

const rules = {
  api_source: [{ required: true, message: '请选择 API 来源', trigger: 'change' }],
  api_key: [{ required: true, message: '请输入 API 密钥', trigger: 'blur' }],
  model: [{ required: true, message: '请选择模型', trigger: 'change' }]
}

watch(
  () => formData.api_key,
  (value) => {
    apiKeys.value[activeSource.value] = value || ''
  }
)

async function openApiSettings() {
  dialogVisible.value = true
  if (dialogLoading.value) {
    return
  }
  dialogLoading.value = true
  try {
    await loadApiSettings()
  } finally {
    dialogLoading.value = false
  }
}

async function loadApiSettings() {
  const res = await getApiSettings()
  const settings = res.data.settings || {}

  apiSourceOptions.value = res.data.api_source_options || []
  apiKeys.value = { ...(settings.api_keys || {}) }

  formData.api_source = settings.api_source || 'deepseek'
  formData.model = settings.model || ''
  activeSource.value = formData.api_source
  formData.api_key = apiKeys.value[formData.api_source] || settings.api_key || ''

  await loadModelOptions({ preserveModel: true, silentIfNoKey: true })
}

async function loadModelOptions({ preserveModel = false, silentIfNoKey = false } = {}) {
  const apiKey = (formData.api_key || '').trim()
  if (!formData.api_source || !apiKey) {
    modelOptions.value = []
    if (!preserveModel) {
      formData.model = ''
    }
    if (!silentIfNoKey) {
      ElMessage.warning('请先输入 API 密钥')
    }
    return
  }

  modelsLoading.value = true
  try {
    const res = await getApiModels({
      provider: formData.api_source,
      api_key: apiKey
    })

    modelOptions.value = res.data.options || []
    syncModelSelection({ preserveModel })
  } finally {
    modelsLoading.value = false
  }
}

function syncModelSelection({ preserveModel = false } = {}) {
  if (!modelOptions.value.length) {
    formData.model = ''
    return
  }

  const modelExists = modelOptions.value.some((item) => item.value === formData.model)
  if (preserveModel && modelExists) {
    return
  }

  formData.model = modelOptions.value[0].value
}

async function handleSourceChange(nextSource) {
  activeSource.value = nextSource
  formData.api_key = apiKeys.value[nextSource] || ''
  await loadModelOptions({ preserveModel: false, silentIfNoKey: true })
}

async function handleApiKeyBlur() {
  await loadModelOptions({ preserveModel: true, silentIfNoKey: true })
}

async function handleModelDropdownVisible(visible) {
  if (!visible) {
    return
  }
  await loadModelOptions({ preserveModel: true, silentIfNoKey: false })
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    apiKeys.value[formData.api_source] = formData.api_key
    await updateApiSettings({
      ...formData,
      api_key: formData.api_key.trim(),
      api_keys: apiKeys.value
    })
    ElMessage.success('API 设置已保存')
    dialogVisible.value = false
  } finally {
    submitLoading.value = false
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.aside {
  display: flex;
  flex-direction: column;
  background-color: #304156;
  transition: width 0.3s;
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  gap: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.aside-menu {
  display: flex;
  flex-direction: column;
  flex: 1;
  border-right: none;
}

.menu-item-bottom {
  margin-top: auto;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #ebeef5;
  background: #fff;
  padding: 0 20px;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: #606266;
}

.page-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.api-setting-trigger {
  font-size: 13px;
  color: #606266;
  padding: 0;
}

.main {
  background: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
</style>
