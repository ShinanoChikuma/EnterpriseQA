import request from './request'

export function getApiSettings() {
  return request.get('/settings/api')
}

export function getApiModels(params) {
  return request.get('/settings/api/models', { params })
}

export function updateApiSettings(data) {
  return request.put('/settings/api', data)
}

export function formatDatabase() {
  return request.post('/settings/maintenance/format-database')
}
