#!/usr/bin/env node
/**
 * SenseNova workbench launcher CLI.
 *
 * The launcher starts the built Express/React workbench against a local deck
 * directory and writes a small session file so agents can query, reuse, or stop
 * the same preview server.
 */
import { spawn } from 'node:child_process'
import { closeSync, existsSync, openSync } from 'node:fs'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import net from 'node:net'
import { networkInterfaces } from 'node:os'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const defaultPort = 18087
const editorRoutePath = '/editor'
const progressRoutePath = '/progress'
const legacyEditorRoutePath = '/ppt-editor'
const legacyProgressRoutePath = '/ppt-progress'
const workbenchRoutePaths = [editorRoutePath, progressRoutePath, legacyEditorRoutePath, legacyProgressRoutePath]
const hiddenProcessOptions = { windowsHide: true }

/** Parses simple --key value CLI arguments without adding a dependency. */
function parseArgs(argv) {
  const [command = 'start', ...rest] = argv
  const args = { command }
  for (let index = 0; index < rest.length; index += 1) {
    const token = rest[index]
    if (!token.startsWith('--')) {
      continue
    }

    const key = token.slice(2)
    const next = rest[index + 1]
    if (!next || next.startsWith('--')) {
      args[key] = 'true'
      continue
    }

    args[key] = next
    index += 1
  }

  return args
}

/** Returns CLI usage text for invalid invocations. */
function usage() {
  return [
    'Usage:',
    '  sensenova-ppt-workbench start --deck-dir "<path>" [--port 0] [--source-session-id "<id>"] [--agent-provider hermes|openclaw|codex|claude-code|workbuddy] [--agent-transport webui|gateway|rest|acp] [--agent-managed] [--gateway-api-key "<secret>"]',
    '  sensenova-ppt-workbench status --deck-dir "<path>"',
    '  sensenova-ppt-workbench stop --deck-dir "<path>"',
  ].join('\n')
}

/** Resolves and validates the required deck directory argument. */
function requireDeckDir(args) {
  const deckDir = String(args['deck-dir'] || '').trim()
  if (!deckDir) {
    throw new Error(`--deck-dir is required.\n${usage()}`)
  }

  const resolved = path.resolve(deckDir)
  if (!existsSync(resolved)) {
    throw new Error(`Deck directory does not exist: ${resolved}`)
  }

  return resolved
}

/** Returns the session metadata path inside the deck workspace. */
function sessionFilePath(deckDir) {
  return path.join(deckDir, '.workbench', 'session.json')
}

/** Reads an existing launcher session if one was written previously. */
async function readSession(deckDir) {
  try {
    return JSON.parse(await readFile(sessionFilePath(deckDir), 'utf8'))
  } catch {
    return null
  }
}

/** Persists launcher session metadata for reuse/status/stop commands. */
async function writeSession(deckDir, session) {
  const filePath = sessionFilePath(deckDir)
  await mkdir(path.dirname(filePath), { recursive: true })
  await writeFile(filePath, JSON.stringify(session, null, 2), 'utf8')
}

/** Checks whether a process ID still exists without terminating it. */
function isPidRunning(pid) {
  if (!pid || !Number.isInteger(pid)) {
    return false
  }

  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

/** Extracts the port from a session URL. */
function getUrlPort(url) {
  try {
    return Number.parseInt(new URL(url).port, 10)
  } catch {
    return 0
  }
}

/** Chooses the host address the backend should bind to. */
function resolveBindHost(args) {
  return String(args.host || process.env.WORKBENCH_HOST || '127.0.0.1')
}

/** Returns a LAN address suitable for remote-device fallback URLs. */
function getLanAddress() {
  for (const entries of Object.values(networkInterfaces())) {
    for (const entry of entries ?? []) {
      if (entry.family === 'IPv4' && !entry.internal) {
        return entry.address
      }
    }
  }

  return '127.0.0.1'
}

/** Builds the local URL used for health checks regardless of public forwarding. */
function buildLocalUrl(port, host) {
  const probeHost = host === '0.0.0.0' || host === '::' ? '127.0.0.1' : host
  return `http://${probeHost}:${port}`
}

/** Builds the user-facing URL, preferring an explicit Hermes/canvas forwarding URL. */
function buildPublicUrl(args, port, host) {
  const configured = String(args['public-url'] || process.env.WORKBENCH_PUBLIC_URL || '').trim()
  if (configured) {
    return configured.replaceAll('{port}', String(port))
  }

  if (host === '0.0.0.0' || host === '::') {
    return `http://${getLanAddress()}:${port}`
  }

  return buildLocalUrl(port, host)
}

/** Resolves which product surface this launcher exposes. */
function resolveProduct() {
  return 'ppt'
}

/** Resolves the public progress route for the launched workbench. */
function resolveProgressRoute(args) {
  const route = String(args['progress-route'] || process.env.WORKBENCH_PROGRESS_ROUTE || progressRoutePath).trim()
  if (route === progressRoutePath || route === legacyProgressRoutePath) {
    return progressRoutePath
  }
  throw new Error(`--progress-route must be ${progressRoutePath}.`)
}

/** Appends or replaces a canonical workbench route on base or forwarded URLs. */
function withWorkbenchRoute(url, routePath) {
  if (!url) {
    return undefined
  }

  try {
    const parsed = new URL(url)
    const normalizedPath = parsed.pathname.replace(/\/+$/, '')
    for (const knownRoute of workbenchRoutePaths) {
      if (normalizedPath.endsWith(knownRoute)) {
        const basePath = normalizedPath.slice(0, -knownRoute.length).replace(/\/+$/, '')
        parsed.pathname = `${basePath || ''}${routePath}`
        return parsed.toString()
      }
    }

    parsed.pathname = `${normalizedPath || ''}${routePath}`
    return parsed.toString()
  } catch {
    const hashIndex = url.indexOf('#')
    const withoutHash = hashIndex >= 0 ? url.slice(0, hashIndex) : url
    const hash = hashIndex >= 0 ? url.slice(hashIndex) : ''
    const queryIndex = withoutHash.indexOf('?')
    const base = queryIndex >= 0 ? withoutHash.slice(0, queryIndex) : withoutHash
    const query = queryIndex >= 0 ? withoutHash.slice(queryIndex) : ''
    const normalizedBase = base.replace(/\/+$/, '')
    const knownRoute = workbenchRoutePaths.find((candidate) => normalizedBase.endsWith(candidate))
    const routedBase = knownRoute
      ? `${normalizedBase.slice(0, -knownRoute.length).replace(/\/+$/, '')}${routePath}`
      : `${normalizedBase}${routePath}`
    return `${routedBase}${query}${hash}`
  }
}

/** Appends the canonical editor route to base or forwarded workbench URLs. */
function withEditorRoute(url) {
  return withWorkbenchRoute(url, editorRoutePath)
}

/** Appends the canonical generation-progress route to base or forwarded workbench URLs. */
function withProgressRoute(url, routePath = progressRoutePath) {
  const routed = withWorkbenchRoute(url, routePath)
  if (!routed) {
    return routed
  }

  try {
    const parsed = new URL(routed)
    if (parsed.searchParams.get('view') === 'generation') {
      parsed.searchParams.delete('view')
    }
    return parsed.toString()
  } catch {
    return routed
  }
}

/** Ensures launcher responses expose both generation and editor entry URLs. */
function withWorkbenchUrls(session) {
  const product = session.product || 'ppt'
  const progressRoute = session.progressRoute || progressRoutePath
  const baseUrl = session.generationUrl || session.editorUrl || session.url
  const generationUrl = withProgressRoute(baseUrl, progressRoute)
  const url = withEditorRoute(session.editorUrl || session.url)
  return {
    ...session,
    product,
    url: url || session.url,
    editorUrl: url || session.editorUrl,
    progressRoute,
    generationUrl,
  }
}

/** Decides whether an existing workbench session satisfies the requested launch shape. */
function canReuseSession(existing, args) {
  if ((existing.product || 'ppt') !== resolveProduct()) {
    return false
  }

  if ((existing.progressRoute || progressRoutePath) !== resolveProgressRoute(args)) {
    return false
  }

  const existingUrl = existing.localUrl || existing.url
  const existingPort = getUrlPort(existingUrl)
  if (args.port) {
    const requestedPort = Number.parseInt(String(args.port), 10)
    if (requestedPort > 0 && existingPort !== requestedPort) {
      return false
    }
  }

  const requestedHost = args.host ? resolveBindHost(args) : undefined
  const existingHost = existing.bindHost || '127.0.0.1'
  if (requestedHost && existingHost !== requestedHost) {
    return false
  }

  const requestedPublicUrl = String(args['public-url'] || '').trim()
  if (requestedPublicUrl && existing.url !== requestedPublicUrl.replaceAll('{port}', String(existingPort))) {
    return false
  }

  return existingPort >= 10001
}

/** Prevents reusing old servers that still target the source Hermes session directly. */
function isLegacySameSessionBridge(health) {
  const mode = health?.agentBridge?.mode
  return mode === 'webui-session' || mode === 'gateway-session'
}

/** Resolves the requested provider identity from explicit args or compatibility env. */
function resolveAgentProvider(args) {
  return String(
    args['agent-provider']
    || process.env.WORKBENCH_AGENT_PROVIDER
    || args['agent-runtime']
    || process.env.WORKBENCH_AGENT_RUNTIME
    || 'hermes',
  )
}

/** Resolves the requested provider transport from explicit args or env. */
function resolveAgentTransport(args) {
  return String(args['agent-transport'] || process.env.WORKBENCH_AGENT_TRANSPORT || '')
}

/** Normalizes simple provider/transport strings for reuse checks. */
function normalizeAgentShapeValue(value) {
  return String(value || '').trim().toLowerCase().replaceAll('_', '-')
}

/** Prevents reusing a detached server that was started for a different explicit provider shape. */
function isCompatibleAgentShape(existing, health, args) {
  const requestedProvider = resolveAgentProvider(args)
  const requestedTransport = resolveAgentTransport(args)
  const runningBridge = health?.agentBridge
  const runningProvider = existing.agentProvider || runningBridge?.provider || runningBridge?.runtime
  const runningTransport = existing.agentTransport || runningBridge?.transport

  if ((args['agent-provider'] || args['agent-runtime'] || process.env.WORKBENCH_AGENT_PROVIDER) && runningProvider && normalizeAgentShapeValue(runningProvider) !== normalizeAgentShapeValue(requestedProvider)) {
    return false
  }

  if ((args['agent-transport'] || process.env.WORKBENCH_AGENT_TRANSPORT) && runningTransport && normalizeAgentShapeValue(runningTransport) !== normalizeAgentShapeValue(requestedTransport)) {
    return false
  }

  return true
}

/** Picks a port above the product's non-system port floor on the requested bind host. */
async function pickFreePort(host, minPort = 10001) {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, host, () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : 0
      server.close(() => {
        if (port >= minPort) {
          resolve(port)
          return
        }
        pickFreePort(host, minPort).then(resolve, reject)
      })
    })
  })
}

/** Tests whether a specific port can be bound on the requested host. */
async function isPortAvailable(port, host) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.listen(port, host, () => {
      server.close(() => resolve(true))
    })
  })
}

/** Resolves explicit, default, or fallback launch port selection. */
async function resolveLaunchPort(args, host) {
  if (args.port) {
    const requested = Number.parseInt(String(args.port), 10)
    return requested > 0 ? requested : await pickFreePort(host)
  }

  return await isPortAvailable(defaultPort, host) ? defaultPort : await pickFreePort(host)
}

/** Queries the workbench session endpoint to verify process health. */
async function probeWorkbench(url) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 1500)
  try {
    const response = await fetch(`${url.replace(/\/+$/, '')}/api/workbench/session`, {
      signal: controller.signal,
    })
    if (!response.ok) {
      return null
    }

    return await response.json()
  } catch {
    return null
  } finally {
    clearTimeout(timeout)
  }
}

/** Waits until the spawned server reports an active workbench session. */
async function waitForWorkbench(url) {
  const deadline = Date.now() + 20_000
  let last = null
  while (Date.now() < deadline) {
    last = await probeWorkbench(url)
    if (last?.active) {
      return last
    }

    await new Promise((resolve) => setTimeout(resolve, 500))
  }

  throw new Error(`Workbench did not become healthy at ${url}. Check .workbench/server.log.`)
}

/** Ensures the packaged runtime has both browser and server build artifacts. */
function requireRuntimeArtifacts() {
  const requiredArtifacts = [
    path.join(repoRoot, 'dist', 'index.html'),
    path.join(repoRoot, 'dist-server', 'index.mjs'),
  ]
  const missing = requiredArtifacts.filter((artifact) => !existsSync(artifact))
  if (missing.length) {
    throw new Error(`Workbench runtime is incomplete; reinstall or rebuild the release artifact. Missing: ${missing.map((artifact) => path.relative(repoRoot, artifact)).join(', ')}`)
  }

  return {
    serverEntry: requiredArtifacts[1],
  }
}

/** Starts or reuses a detached workbench server for the requested deck. */
async function start(args) {
  const deckDir = requireDeckDir(args)
  const { serverEntry } = requireRuntimeArtifacts()

  const existing = await readSession(deckDir)
  if (existing?.url && isPidRunning(existing.pid)) {
    const health = await probeWorkbench(existing.localUrl || existing.url)
    if (health?.active && canReuseSession(existing, args) && !isLegacySameSessionBridge(health) && isCompatibleAgentShape(existing, health, args)) {
      console.log(JSON.stringify(withWorkbenchUrls({ ...existing, reused: true, health })))
      return
    }
  }

  const bindHost = resolveBindHost(args)
  const product = resolveProduct()
  const progressRoute = resolveProgressRoute(args)
  const port = await resolveLaunchPort(args, bindHost)
  const localUrl = buildLocalUrl(port, bindHost)
  const publicUrl = buildPublicUrl(args, port, bindHost)
  const url = withEditorRoute(publicUrl)
  const instanceId = String(args['instance-id'] || `ppt-${Buffer.from(deckDir).toString('base64url').slice(0, 12)}`)
  const startedAt = new Date().toISOString()
  const sourceSessionId = String(
    args['source-session-id']
    || args['agent-session-id']
    || process.env.WORKBENCH_AGENT_SOURCE_SESSION_ID
    || process.env.HERMES_SESSION_KEY
    || '',
  )
  const agentProvider = resolveAgentProvider(args)
  const agentTransport = resolveAgentTransport(args)
  const agentBaseUrl = String(args['agent-base-url'] || process.env.WORKBENCH_AGENT_BASE_URL || process.env.OPENCLAW_GATEWAY_BASE_URL || process.env.OPENCLAW_BASE_URL || '')
  const agentApiKey = String(args['agent-api-key'] || process.env.WORKBENCH_AGENT_API_KEY || process.env.OPENCLAW_API_KEY || '')
  const acpCommand = String(args['acp-command'] || process.env.WORKBENCH_ACP_COMMAND || process.env.CODEX_ACP_COMMAND || process.env.CLAUDE_ACP_COMMAND || '')
  const gatewayApiKey = String(
    args['gateway-api-key']
    || agentApiKey
    || process.env.WORKBENCH_GATEWAY_API_KEY
    || process.env.API_SERVER_KEY
    || process.env.HERMES_GATEWAY_API_KEY
    || process.env.AI_GATEWAY_API_KEY
    || '',
  )
  const workbenchDir = path.join(deckDir, '.workbench')
  await mkdir(workbenchDir, { recursive: true })

  const logFd = openSync(path.join(workbenchDir, 'server.log'), 'a')
  const child = spawn(process.execPath, [serverEntry], {
    ...hiddenProcessOptions,
    cwd: repoRoot,
    detached: true,
    env: {
      ...process.env,
      PORT: String(port),
      HOST: bindHost,
      WORKBENCH_HOST: bindHost,
      WORKBENCH_DECK_DIR: deckDir,
      WORKBENCH_PUBLIC_URL: url,
      WORKBENCH_PROGRESS_ROUTE: progressRoute,
      WORKBENCH_PRODUCT: product,
      WORKBENCH_INSTANCE_ID: instanceId,
      WORKBENCH_STARTED_AT: startedAt,
      WORKBENCH_AGENT_MANAGED: String(args['agent-managed'] || process.env.WORKBENCH_AGENT_MANAGED || (sourceSessionId ? '1' : '')),
      WORKBENCH_AGENT_PROVIDER: agentProvider,
      WORKBENCH_AGENT_TRANSPORT: agentTransport,
      WORKBENCH_AGENT_BASE_URL: agentBaseUrl,
      WORKBENCH_AGENT_API_KEY: agentApiKey,
      WORKBENCH_ACP_COMMAND: acpCommand,
      WORKBENCH_AGENT_SOURCE_SESSION_ID: sourceSessionId,
      WORKBENCH_AGENT_SESSION_ID: '',
      WORKBENCH_AGENT_RUNTIME: String(args['agent-runtime'] || agentProvider),
      WORKBENCH_WEBUI_BASE_URL: String(args['webui-base-url'] || process.env.HERMES_WEBUI_BASE_URL || ''),
      WORKBENCH_GATEWAY_BASE_URL: String(args['gateway-base-url'] || process.env.HERMES_GATEWAY_BASE_URL || ''),
      WORKBENCH_GATEWAY_API_KEY: gatewayApiKey,
    },
    stdio: ['ignore', logFd, logFd],
  })
  closeSync(logFd)
  child.unref()

  const session = {
    active: true,
    product,
    instanceId,
    deckDir,
    bindHost,
    localUrl,
    url,
    editorUrl: url,
    generationUrl: withProgressRoute(url, progressRoute),
    progressRoute,
    pid: child.pid,
    startedAt,
    sourceSessionId,
    agentProvider,
    agentTransport,
    sessionFile: sessionFilePath(deckDir),
  }
  await writeSession(deckDir, session)
  const health = await waitForWorkbench(localUrl)
  console.log(JSON.stringify(withWorkbenchUrls({ ...session, health })))
}

/** Prints current launcher session status as JSON. */
async function status(args) {
  const deckDir = requireDeckDir(args)
  const session = await readSession(deckDir)
  if (!session) {
    console.log(JSON.stringify({ active: false, deckDir }))
    return
  }

  const health = session.url ? await probeWorkbench(session.localUrl || session.url) : null
  console.log(JSON.stringify(withWorkbenchUrls({
    ...session,
    active: Boolean(health?.active),
    pidRunning: isPidRunning(session.pid),
    health,
  })))
}

/** Stops the launcher-owned server process when it is still running. */
async function stop(args) {
  const deckDir = requireDeckDir(args)
  const session = await readSession(deckDir)
  if (session?.pid && isPidRunning(session.pid)) {
    process.kill(session.pid)
  }

  console.log(JSON.stringify({
    active: false,
    deckDir,
    stoppedPid: session?.pid,
  }))
}

/** Dispatches CLI subcommands and preserves JSON output for automation. */
async function main() {
  const args = parseArgs(process.argv.slice(2))
  if (args.command === 'start') return start(args)
  if (args.command === 'status') return status(args)
  if (args.command === 'stop') return stop(args)
  throw new Error(usage())
}

main().catch((error) => {
  console.error(JSON.stringify({
    ok: false,
    error: error instanceof Error ? error.message : String(error),
  }))
  process.exitCode = 1
})
