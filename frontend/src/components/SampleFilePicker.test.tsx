import { afterEach, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SampleFilePicker } from './SampleFilePicker'
afterEach(()=>vi.unstubAllGlobals())
it('rejects an HTML fallback without replacing a selected file and permits a local-asset retry',async()=>{
  const onFile=vi.fn()
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce({ok:true,headers:new Headers({'Content-Type':'text/html'})}).mockResolvedValueOnce({ok:true,headers:new Headers({'Content-Type':'image/svg+xml'}),arrayBuffer:async()=>new TextEncoder().encode('<svg/>').buffer}))
  const user=userEvent.setup();render(<SampleFilePicker label="原件" file={new File(['old'],'original.pdf')} onFile={onFile}/>)
  await user.click(screen.getByRole('button',{name:'使用演示图纸'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('本地演示图纸读取失败')
  expect(onFile).not.toHaveBeenCalled()
  expect(screen.getByText('已选择：original.pdf')).toBeVisible()
  await user.click(screen.getByRole('button',{name:'使用演示图纸'}))
  await waitFor(()=>expect(onFile).toHaveBeenCalledWith(expect.objectContaining({name:'07_样件尺寸示意.svg',type:'image/svg+xml',size:6})))
})
it('ignores an in-flight asset selection after the parent starts saving',async()=>{
  let resolve!:(response:unknown)=>void
  vi.stubGlobal('fetch',vi.fn(()=>new Promise(result=>{resolve=result})))
  const onFile=vi.fn();const user=userEvent.setup()
  const {rerender}=render(<SampleFilePicker label="原件" file={null} onFile={onFile}/>)
  await user.click(screen.getByRole('button',{name:'使用演示图纸'}))
  rerender(<SampleFilePicker label="原件" file={null} onFile={onFile} disabled/>)
  resolve({ok:true,headers:new Headers({'Content-Type':'image/svg+xml'}),arrayBuffer:async()=>new ArrayBuffer(1)})
  await waitFor(()=>expect(screen.getByRole('button',{name:'使用演示图纸'})).toBeDisabled())
  expect(onFile).not.toHaveBeenCalled()
})
