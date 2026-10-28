import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { IDBFactory } from 'fake-indexeddb'
import { clearImportDrafts, flushImportDrafts, readImportDrafts, removeImportDraft, saveImportDraft, type ImportDraft } from './importDrafts'

beforeEach(()=>vi.stubGlobal('indexedDB',new IDBFactory()))
afterEach(async()=>{await flushImportDrafts();vi.unstubAllGlobals()})
const draft=(projectId='p1',importId='i1'):ImportDraft=>({projectId,importId,displayCode:'DOC-1',docType:'protocol',version:'V1',content:'核对正文',mappingText:'',original:{filename:'协议.docx',sha256:'a'.repeat(64),data_base64:'b3JpZ2luYWw='},updatedAt:'2026-10-25T09:00:00.000Z'})

it('persists edits and separate originals without mixing projects or processing attempts',async()=>{
 await saveImportDraft(draft());await saveImportDraft(draft('p1','i2'));await saveImportDraft(draft('p2'))
 await saveImportDraft({...draft(),content:'修改后的正文',mappingText:'engineMaxTorque=REQ-1',version:'V2'})
 const current=await readImportDrafts('p1')
 expect(current).toHaveLength(2);expect(current.find(row=>row.importId==='i1')).toMatchObject({content:'修改后的正文',version:'V2',mappingText:'engineMaxTorque=REQ-1',original:draft().original})
 expect(await readImportDrafts('p2')).toEqual([draft('p2')])
})

it('supports original attachments larger than the localStorage limit and preserves empty edits',async()=>{
 const large={...draft(),content:'',original:{...draft().original!,data_base64:'A'.repeat(8*1024*1024)}}
 await saveImportDraft(large)
 expect(await readImportDrafts('p1')).toEqual([large])
 await saveImportDraft({...large,original:undefined})
 expect((await readImportDrafts('p1'))[0].original).toBeUndefined()
})

it('serializes an in-flight save before cancellation and clears only the chosen project',async()=>{
 const saving=saveImportDraft(draft());const removing=removeImportDraft('p1','i1')
 await Promise.all([saving,removing]);expect(await readImportDrafts('p1')).toEqual([])
 await saveImportDraft({...draft(),importId:undefined});await saveImportDraft(draft('p2'))
 await clearImportDrafts('p1');expect(await readImportDrafts('p1')).toEqual([])
 expect(await readImportDrafts('p2')).toHaveLength(1)
 await clearImportDrafts();expect(await readImportDrafts('p2')).toEqual([])
})

it('rejects malformed persisted form data rather than recovering it into another project',async()=>{
 await saveImportDraft(draft())
 await new Promise<void>((resolve,reject)=>{
  const request=indexedDB.open('zhiyan-import-drafts-v1',1)
  request.onsuccess=()=>{const db=request.result,tx=db.transaction('drafts','readwrite');tx.objectStore('drafts').put({...draft(),key:JSON.stringify(['p1','i1']),content:42});tx.oncomplete=()=>{db.close();resolve()};tx.onabort=()=>reject(tx.error)}
 })
 await expect(readImportDrafts('p1')).rejects.toThrow('草稿格式无效')
})

it('reports unavailable storage and transaction failures instead of pretending to save',async()=>{
 vi.stubGlobal('indexedDB',undefined)
 await expect(saveImportDraft(draft())).rejects.toThrow('不支持草稿存储')
 vi.stubGlobal('indexedDB',new IDBFactory())
 const put=vi.spyOn(globalThis,'structuredClone').mockImplementationOnce(()=>{throw new Error('缓存写入失败')})
 await expect(saveImportDraft(draft())).rejects.toThrow('缓存写入失败')
 put.mockRestore()
 expect(await readImportDrafts('p1')).toEqual([])
 await saveImportDraft(draft());expect(await readImportDrafts('p1')).toHaveLength(1)
})
