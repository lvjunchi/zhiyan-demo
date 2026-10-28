import { api } from '../api'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { ModuleWorkspace } from './ModuleWorkspace'

it('keeps one concise work context and opens the related next module', async () => {
  vi.spyOn(api, 'getWorkspace').mockResolvedValue({ project_id: 'p1', stages: [], changes: [], scope_note: '合成测试' })
  const navigate = vi.fn()
  render(<ModuleWorkspace projectId="p1" tab="requirements" onNavigate={navigate}><p>需求数据</p></ModuleWorkspace>)
  expect(screen.getByRole('region', { name: '当前模块工作提示' })).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: '模块工作路径' })).not.toBeInTheDocument()
  expect(screen.getByText('需求数据')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '下一步：型谱选型与变型' }))
  expect(navigate).toHaveBeenCalledWith('bases')
})
