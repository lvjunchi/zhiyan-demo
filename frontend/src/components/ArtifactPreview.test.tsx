import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { ArtifactPreview } from './ArtifactPreview'

it('opens an accessible read-only result preview and restores trigger focus on escape', async () => {
  const user = userEvent.setup()
  render(<ArtifactPreview title="设计成果" code="DR-01" revision={2} status="draft" mode="rule"><p>输入扭矩校核依据</p></ArtifactPreview>)
  const trigger = screen.getByRole('button', { name: '预览设计成果' })
  await user.click(trigger)
  expect(screen.getByRole('dialog', { name: '设计成果预览' })).toBeInTheDocument()
  expect(screen.getByText('草案')).toBeInTheDocument()
  expect(screen.getByText('输入扭矩校核依据')).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})
