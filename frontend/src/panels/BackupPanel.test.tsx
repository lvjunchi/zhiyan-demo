import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { BackupPanel } from './BackupPanel'

afterEach(() => vi.unstubAllGlobals())
it('validates a backup and shows a review before any restore request', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ counts: { projects: 1, requirements: 13 }, projects: [{ id: 'p1', name: '研发项目', display_code: 'P01' }], snapshot_sha256: 'a'.repeat(64), expected_state_hash: 'b'.repeat(64) })))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  render(<BackupPanel />)
  await user.upload(screen.getByLabelText('选择备份文件'), new File(['{}'], 'backup.json', { type: 'application/json' }))
  expect(await screen.findByText('研发项目')).toBeVisible()
  expect(screen.getByText('校验通过，尚未恢复')).toBeVisible()
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(fetchMock.mock.calls[0]).toBeDefined()
  expect(screen.getByRole('button', { name: '确认恢复并切换数据' })).toBeDisabled()
})
it('shows invalid-file errors without calling restore', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  render(<BackupPanel />)
  await user.upload(screen.getByLabelText('选择备份文件'), new File(['{bad'], 'bad.json', { type: 'application/json' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('备份文件不是有效 JSON')
  expect(fetchMock).not.toHaveBeenCalled()
})
