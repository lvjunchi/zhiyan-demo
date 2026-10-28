import { expect, it } from 'vitest'
import { readWorkspace } from './workspaceTypes'

const valid = { project_id: 'p1', stages: [{ key: 'testing', label: '试验验证', action: '复核', state: 'attention', record_count: 2, pending_count: 1, stale_count: 1, notes: [] }], changes: [], scope_note: '受控引用' }
it('validates workspace identity and rejects malformed counters and navigation destinations', () => {
  expect(readWorkspace(valid, 'p1').stages[0].stale_count).toBe(1)
  for (const value of [null, [], { ...valid, project_id: 'other' }, { ...valid, stages: [valid.stages[0], valid.stages[0]] }, { ...valid, stages: [{ ...valid.stages[0], pending_count: -1 }] }, { ...valid, stages: [{ ...valid.stages[0], key: 'http://invalid' }] }, { ...valid, changes: [{}] }]) {
    expect(() => readWorkspace(value, 'p1')).toThrow('项目操作进度响应无效')
  }
})
