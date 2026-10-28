import type { Page } from '@playwright/test'
import { TAB_GROUPS } from '../src/navigation'

/** Use the same visible group -> module path as a person using the sidebar. */
export async function openWorkspaceTab(page: Page, name: string) {
  const group = TAB_GROUPS.find(item => item.tabs.some(tab => tab.label === name))
  if (group && !group.standalone) {
    const toggle = page.getByRole('button', { name: group.title, exact: true })
    await toggle.waitFor({ state: 'visible' })
    if (await toggle.getAttribute('aria-expanded') === 'false') await toggle.click()
  }
  await page.getByRole('tab', { name, exact: true }).click()
}
