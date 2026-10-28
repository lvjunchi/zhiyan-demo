export function testPorts(defaultApi: number, defaultUi: number) {
  const apiPort = Number(process.env.ZHIYAN_E2E_API_PORT ?? defaultApi)
  const uiPort = Number(process.env.ZHIYAN_E2E_UI_PORT ?? defaultUi)
  if (![apiPort, uiPort].every(port => Number.isInteger(port) && port > 0 && port <= 65535) || apiPort === uiPort) {
    throw new Error('浏览器测试需要两个不同的有效本机端口')
  }
  return { apiPort, uiPort, apiURL: `http://127.0.0.1:${apiPort}`, uiURL: `http://127.0.0.1:${uiPort}` }
}
