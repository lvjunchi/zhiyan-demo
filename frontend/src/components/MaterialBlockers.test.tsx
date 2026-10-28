import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { MaterialBlockers } from './MaterialBlockers'

it('routes blockers with their actual object ID and revision', async () => {
  const navigate = vi.fn()
  render(<MaterialBlockers blockers={[{ code: 'ENGINEERING_DECISION_NOT_READY', check: 'engineering_decisions_confirmed', message: '复用决策待复核', object_type: 'reusable_part_decision', object_id: 'part1', revision: 2 }]} onNavigate={navigate} />)
  await userEvent.click(screen.getByRole('button', { name: '处理：复用决策待复核' }))
  expect(navigate).toHaveBeenCalledWith('bases', { objectId: 'part1', revision: 2, message: '复用决策待复核' })
})
it('shows incomplete navigation evidence instead of inventing an object link', () => {
  render(<MaterialBlockers blockers={[{ code: 'UNKNOWN', check: 'unknown', message: '缺少依据' }]} onNavigate={vi.fn()} />)
  expect(screen.getByText('缺少可定位的关联信息，请核对门禁详情。')).toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})
