<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>系统维护</span>
        </div>
      </template>

      <div class="setting-section">
        <div class="setting-title">格式化数据库</div>
        <div class="setting-description">
          清空全部知识库、文档和对话历史，同时重置它们的 ID。该操作不可恢复，并会删除已上传文件和本地向量索引。
        </div>
        <div class="setting-actions">
          <el-button type="danger" :loading="formatting" @click="handleFormatDatabase">
            格式化数据库
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { ref } from 'vue'

import { formatDatabase } from '../api/settings'

const formatting = ref(false)

async function handleFormatDatabase() {
  await ElMessageBox.confirm(
    '该操作会清空全部知识库、文档、对话历史，并重置它们的 ID。此操作不可恢复，是否继续？',
    '确认格式化数据库',
    {
      type: 'warning',
      confirmButtonText: '确认格式化',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger'
    }
  )

  formatting.value = true
  try {
    await formatDatabase()
    ElMessage.success('格式化数据库成功')
  } finally {
    formatting.value = false
  }
}
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: #303133;
}

.setting-section {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 4px 0;
}

.setting-title {
  min-width: 140px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  line-height: 32px;
}

.setting-description {
  flex: 1;
  color: #606266;
  line-height: 1.8;
}

.setting-actions {
  display: flex;
  align-items: center;
}

@media (max-width: 768px) {
  .setting-section {
    flex-direction: column;
    gap: 12px;
  }

  .setting-title {
    min-width: 0;
    line-height: 1.5;
  }
}
</style>
