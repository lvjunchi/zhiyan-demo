import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { WorkspaceJourney } from './WorkspaceJourney'

const data = {
  project_id: 'p1', scope_note: '仅展示持久化引用',
  stages: [
    { key: 'requirements', label: '需求确认', action: '核对来源与版本', record_count: 2, pending_count: 1, stale_count: 0, state: 'attention', notes: [] },
    { key: 'testing', label: '试验验证', action: '复核当前用例', record_count: 1, pending_count: 0, stale_count: 1, state: 'attention', notes: ['有效覆盖 3/5'] },
  ],
  changes: [{ requirement_id: 'r1', display_code: 'B-003', parameter_name: '发动机最大扭矩', from_revision: 1, to_revision: 2, created_at: '2026-10-20T00:00:00+00:00', before: { value_text: '2600', unit: 'N·m' }, after: { value_text: '2800', unit: 'N·m' }, impacts: [{ object_id: 'tc7', object_type: 'test_case', display_code: 'TC-007', revision: 1, review_status: 'confirmed', validity: 'stale', tab: 'testing', applicable: true, references: [{ upstream_id: 'r1', upstream_type: 'requirement', downstream_type: 'test_case', downstream_id: 'tc7', referenced_revision: 1, current_revision: 2, evidence: '用例需求版本引用' }] }] }],
}
afterEach(() => { vi.unstubAllGlobals() })
it('separates the current task, persisted metrics and a clearly labelled next-step region', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => data }))
  const navigate = vi.fn(), user = userEvent.setup()
  render(<WorkspaceJourney projectId="p1" tab="requirements" onNavigate={navigate} />)
  expect(await screen.findByText('核对来源与版本')).toBeVisible()
  const next = screen.getByRole('region', { name: '下一步操作' })
  expect(within(next).getByText('型谱选型与变型')).toBeVisible()
  expect(within(next).getByText('按需继续处理，当前审核状态不会自动改变')).toBeVisible()
  await user.click(within(next).getByRole('button', { name: '下一步：型谱选型与变型' }))
  expect(navigate).toHaveBeenCalledWith('bases')
  expect(screen.getByText('待办检查').querySelector('strong')).toHaveTextContent('1')
})
it('shows real work state and navigates to a stale object without hiding its confirmation', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => data }))
  const navigate = vi.fn(), user = userEvent.setup()
  render(<WorkspaceJourney projectId="p1" tab="requirements" onNavigate={navigate} />)
  expect(await screen.findByText('核对来源与版本')).toBeInTheDocument()
  expect(screen.queryByRole('navigation', { name: '项目阶段导航' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '下一步：型谱选型与变型' }))
  expect(navigate).toHaveBeenCalledWith('bases')
  await user.click(screen.getByRole('button', { name: /变更影响/ }))
  expect(screen.getByText('2600 N·m')).toBeInTheDocument()
  expect(screen.getByText('2800 N·m')).toBeInTheDocument()
  expect(screen.getByText('已确认')).toBeInTheDocument()
  expect(within(screen.getByRole('row', { name: /TC-007/ })).getByText('待复核')).toBeInTheDocument()
  expect(screen.getByText(/引用 V1.*当前 V2/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '处理 TC-007' }))
  expect(navigate).toHaveBeenCalledWith('testing', expect.objectContaining({ objectId: 'tc7', origin: 'change' }))
})
it('does not fabricate progress after failure and retries explicitly', async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new Error('离线')).mockResolvedValue({ ok: true, status: 200, json: async () => ({ ...data, changes: [] }) })
  vi.stubGlobal('fetch', fetcher)
  const user = userEvent.setup()
  render(<WorkspaceJourney projectId="p1" tab="requirements" onNavigate={vi.fn()} />)
  expect(await screen.findByText(/操作进度暂不可用/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '重试进度' }))
  expect(await screen.findByText('核对来源与版本')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /变更影响/ }))
  expect(screen.getByText(/尚无可对比的需求修订/)).toBeInTheDocument()
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
})

it('refreshes after a successful write and displays an exact source field change', async () => {
  const updated = { ...data, changes: [{ ...data.changes[0], before: { value_text: '2600', source_excerpt: '原协议' }, after: { value_text: '2800', source_excerpt: '变更单 CN-01' } }] }
  const fetcher = vi.fn().mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ ...data, changes: [] }) }).mockResolvedValue({ ok: true, status: 200, json: async () => updated })
  vi.stubGlobal('fetch', fetcher)
  render(<WorkspaceJourney projectId="p1" tab="requirements" onNavigate={vi.fn()} />)
  await screen.findByText('核对来源与版本')
  window.dispatchEvent(new Event('zhiyan:data-changed'))
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
  await userEvent.click(await screen.findByRole('button', { name: '变更影响 · 1' }))
  expect(screen.getByText('来源摘录')).toBeInTheDocument()
  expect(screen.getByText('原协议')).toBeInTheDocument()
  expect(screen.getByText('变更单 CN-01')).toBeInTheDocument()
})
