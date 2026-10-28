import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './api'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    headers: { get: () => null },
  } as unknown as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api client', () => {
  it('requires freshness metadata before showing a calculated coordination result', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({
      project_id: 'p1', topic_count: 1, metrics_available: 1, highest_risk: 'high',
      topics: [{ id: 't1', display_code: 'CT-01', expected_participants: [], records: [], risk_acceptances: [], latest_metrics: { id: 'm1', metrics: {}, risk: {}, cost: {} } }],
    })))
    await expect(api.getCoordinationOverview('p1')).rejects.toThrow('协同响应无效')
  })
  it('rejects malformed project, requirement, plan, coordination and package state responses', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({})))
    await expect(api.listProjects()).rejects.toThrow('项目响应无效')
    await expect(api.listRequirements('p1')).rejects.toThrow('需求响应无效')
    await expect(api.getTestPlan('p1')).rejects.toThrow('试验方案响应无效')
    await expect(api.getCoordinationOverview('p1')).rejects.toThrow('协同响应无效')
    await expect(api.listMaterialPackages('p1')).rejects.toThrow('材料列表响应无效')
    await expect(api.getMaterialPackage('pkg1')).rejects.toThrow('材料详情响应无效')
  })
  it('rejects malformed source, engineering and revision responses before rendering them', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({})))
    await expect(api.listSourceDocuments('p1')).rejects.toThrow('来源文档响应无效')
    await expect(api.listEngineeringRecords('p1')).rejects.toThrow('工程决策响应无效')
    await expect(api.engineeringDetail('variant', 'v1')).rejects.toThrow('工程版本响应无效')
    await expect(api.requirementRevisions('r1')).rejects.toThrow('需求版本响应无效')
    await expect(api.confirmEngineering('variant', 'v1', { expected_revision: 1, actor: '工程师', role: 'design_engineer', decision: 'confirmed', comment: '核对' })).rejects.toThrow('工程审核响应无效')
  })
  it('targets every backend endpoint with the expected method and body', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (!init?.method) {
          if (url === '/api/projects' || url.endsWith('/requirements') || url.endsWith('/material-packages')) return jsonResponse([])
          if (url.endsWith('/test-plan')) return jsonResponse({ plan: { id: 'tp1', display_code: 'TP-01', revision: 1, status: 'draft' }, cases: [], confirmations: [] })
          if (url.endsWith('/coordination-overview')) return jsonResponse({ project_id: 'p1', topic_count: 0, metrics_available: 0, highest_risk: 'insufficient', topics: [] })
          if (url === '/api/material-packages/pkg1') return jsonResponse({ id: 'pkg1', project_id: 'p1', display_code: 'MP-01', package_no: 1, status: 'draft', snapshot_hash: 'a'.repeat(64), zip_sha256: 'b'.repeat(64), zip_size: 10, snapshot: {}, manifest: { files: [] }, gate: { checks: [], blockers: [], warnings: [], summary: { check_count: 0, passed_check_count: 0 } } })
        }
        return jsonResponse({})
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    await api.listProjects()
    await api.listRequirements('p1')
    await api.confirmRequirement('r1', {
      expected_revision: 2,
      actor: '演示工程师',
      role: 'design_engineer',
      decision: 'confirmed',
      comment: '',
    })
    await api.updateRequirement('r1', {
      expected_revision: 2,
      value_text: '2800',
    })
    await api.createSourceDocument('p1', {
      display_code: 'DOC-01',
      doc_type: 'protocol',
      version: 'V1',
      content: '正文',
      mode: 'manual',
    })
    await api.parseSourceDocument('doc1', { gearCount: 'REQ-01' })
    await api.listIssues('p1')
    await api.closeIssue('i1', { expected_status: 'open' })
    await api.reopenIssue('i1', { expected_status: 'closed' })
    await api.recommendBases('p1', 3)
    await api.runVariantAnalysis('p1', 'JX-12A')
    await api.findSimilarProjects('p1', 3)
    await api.generateDesignReview('p1', 'JX-12A')
    await api.getDesignReview('p1')
    await api.confirmDesignReview('dr1', { expected_revision: 1 })
    await api.generateDfmea('p1', 'JX-12A')
    await api.getDfmea('p1')
    await api.updateFmeaItem('f1', { expected_revision: 1 })
    await api.confirmFmeaScores('f1', { expected_revision: 1 })
    await api.confirmDfmea('df1', { expected_revision: 1 })

    await api.generateTestPlan('p1')
    await api.getTestPlan('p1')
    await api.confirmTestPlan('tp1', { expected_revision: 1 })
    await api.confirmTestCase('tc1', { expected_revision: 1 })
    await api.updateTestCase('tc1', { expected_revision: 1 })
    await api.recordTestRun('tc1', { expected_revision: 1 })
    await api.getTraceabilityMatrix('p1')

    await api.listSampleDeliveries('p1')
    await api.createSampleDelivery('p1', { supplier: '样件厂' })
    await api.getSampleComparison('sd1')
    await api.createSampleComparison('sd1', { actor: '演示工程师' })
    await api.confirmSampleComparison('sc1', { expected_revision: 1 })
    await api.uploadSampleFile(
      'sd1',
      new File(['drawing'], 'drawing.pdf', { type: 'application/pdf' }),
      '演示工程师',
    )

    await api.runConsistencyCheck('p1')
    await api.getLatestConsistencyCheck('p1')
    await api.listConflicts('p1')
    await api.confirmConsistencyCheck('cc1', { expected_revision: 1 })
    await api.closeConflict('cf1', { expected_revision: 1 })

    await api.getCoordinationOverview('p1')
    await api.createCoordinationTopic('p1', { name: '议题' })
    await api.createCoordinationRecord('t1', { external_id: 'M-1' })
    await api.calculateCoordinationMetrics('t1', { labor_hours: 2 })
    await api.acceptCoordinationRisk('t1', { metric_run_id: 'mr1' })

    await api.listMaterialPackages('p1')
    await api.createMaterialPackage('p1', { include_originals: false })
    await api.getMaterialPackage('pkg1')
    await api.approveMaterialPackage('pkg1', {
      expected_snapshot_hash: 'a'.repeat(64),
    })

    const calls = fetchMock.mock.calls.map(
      ([url, init]) =>
        [String(url), init?.method ?? 'GET'] as [string, string],
    )
    expect(calls).toContainEqual([
      '/api/projects/p1/requirements',
      'GET',
    ])
    expect(calls).toContainEqual([
      '/api/requirements/r1',
      'PATCH',
    ])
    expect(calls).toContainEqual([
      '/api/source-documents/doc1/parse',
      'POST',
    ])
    expect(calls).toContainEqual([
      '/api/projects/p1/variant-analysis',
      'POST',
    ])
    expect(calls).toContainEqual([
      '/api/test-cases/tc1/runs',
      'POST',
    ])
    expect(calls).toContainEqual([
      '/api/projects/p1/traceability-matrix',
      'GET',
    ])
    expect(calls).toContainEqual([
      '/api/sample-deliveries/sd1/file?file_name=drawing.pdf&actor=%E6%BC%94%E7%A4%BA%E5%B7%A5%E7%A8%8B%E5%B8%88',
      'PUT',
    ])
    expect(calls).toContainEqual([
      '/api/coordination-topics/t1/metrics',
      'POST',
    ])
    expect(calls).toContainEqual([
      '/api/material-packages/pkg1/approvals',
      'POST',
    ])

    const bodies = fetchMock.mock.calls.map(([, init]) =>
      typeof init?.body === 'string' ? JSON.parse(init.body) : null,
    )
    expect(bodies).toContainEqual({ top_n: 3 })
    expect(bodies).toContainEqual({ base_display_code: 'JX-12A' })
    expect(bodies).toContainEqual({
      display_code_map: { gearCount: 'REQ-01' },
    })
    expect(bodies).toContainEqual({ expected_status: 'open' })
    expect(bodies).toContainEqual({ labor_hours: 2 })
    expect(bodies).toContainEqual({ include_originals: false })

    const upload = fetchMock.mock.calls.find(([url]) =>
      String(url).includes('/file?'),
    )
    expect(upload?.[1]?.headers).toMatchObject({
      'Content-Type': 'application/pdf',
    })
    expect(upload?.[1]?.body).toBeInstanceOf(File)
  })

  it('returns 204 as undefined and rejects unparseable success bodies', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        status: 204,
        json: async () => null,
      })),
    )
    await expect(api.confirmRequirement('r1', { expected_revision: 1, actor: '工程师', role: '演示角色', decision: 'confirmed', comment: '核对' })).resolves.toBeUndefined()

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => {
          throw new SyntaxError('empty')
        },
      })),
    )
    await expect(api.listProjects()).rejects.toMatchObject({
      name: 'ApiError',
      status: 200,
      code: 'INVALID_RESPONSE',
      message: '服务端返回了无法解析的响应',
    })
  })

  it('maps backend error bodies and falls back when they are absent', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(
          {
            error: {
              code: 'VERSION_CONFLICT',
              message: '需求已被更新',
              details: { current_revision: 3 },
            },
          },
          409,
        ),
      ),
    )
    const error = await api
      .listProjects()
      .catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 409,
      code: 'VERSION_CONFLICT',
      message: '需求已被更新',
      details: { current_revision: 3 },
    })

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 500,
        json: async () => {
          throw new SyntaxError('html')
        },
      })),
    )
    await expect(api.listProjects()).rejects.toMatchObject({
      status: 500,
      code: 'UNKNOWN_ERROR',
      message: '请求失败（HTTP 500）',
    })
  })

  it('downloads a package blob with decoded filename and hash header', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      headers: {
        get: (name: string) => {
          if (name === 'content-disposition') {
            return "attachment; filename*=UTF-8''%E6%9D%90%E6%96%99%E5%8C%85.zip"
          }
          if (name === 'x-content-sha256') return 'b'.repeat(64)
          return null
        },
      },
      blob: async () => new Blob(['zip']),
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.downloadMaterialPackage('pkg1')
    expect(result.filename).toBe('材料包.zip')
    expect(result.sha256).toBe('b'.repeat(64))
    expect(result.blob).toBeInstanceOf(Blob)
  })

  it('treats a missing download filename as null and reports blob errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        status: 200,
        headers: { get: () => null },
        blob: async () => new Blob([]),
      })),
    )
    const result = await api.downloadMaterialPackage('pkg1')
    expect(result.filename).toBeNull()
    expect(result.sha256).toBeNull()

    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(
          {
            error: {
              code: 'PACKAGE_NOT_READY',
              message: '材料包尚未就绪',
            },
          },
          400,
        ),
      ),
    )
    await expect(api.downloadMaterialPackage('pkg1')).rejects.toMatchObject({
      status: 400,
      code: 'PACKAGE_NOT_READY',
    })
  })
})
