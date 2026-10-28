import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { SettingsPanel } from './SettingsPanel'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

it('persists display preferences and verifies service health', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ status: 'ok', database: 'connected', schema_version: '012_design_validity' }), { status: 200 })))
  const user = userEvent.setup()
  const { unmount } = render(<SettingsPanel />)
  expect(await screen.findByText('数据库已连接')).toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('信息密度'), 'compact')
  await user.click(screen.getByLabelText('减少界面动效'))
  await user.click(screen.getByRole('button', { name: '保存显示设置' }))
  expect(screen.getByRole('status')).toHaveTextContent('显示设置已保存')
  unmount()
  render(<SettingsPanel />)
  expect(screen.getByLabelText('信息密度')).toHaveValue('compact')
  expect(screen.getByLabelText('减少界面动效')).toBeChecked()
  expect(document.documentElement.dataset.density).toBe('compact')
})

it('reports connection and preference storage failures honestly', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('服务未启动') }))
  const user = userEvent.setup()
  render(<SettingsPanel />)
  expect(await screen.findByText(/服务未启动/)).toBeInTheDocument()
  const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('空间不足') })
  await user.click(screen.getByRole('button', { name: '保存显示设置' }))
  expect(screen.getByRole('alert')).toHaveTextContent('设置未能保存')
  spy.mockRestore()
})
