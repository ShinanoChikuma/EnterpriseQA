/**
 * 统计数据API
 */
import request from './request'

/** 获取首页统计概览 */
export function getOverview() {
  return request.get('/stats/overview')
}
