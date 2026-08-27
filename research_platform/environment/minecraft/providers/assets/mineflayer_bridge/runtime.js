'use strict'

const { Movements, goals: { GoalNear, GoalFollow } } = require('mineflayer-pathfinder')
const { Vec3 } = require('vec3')

let bot = null
let movements = null

function bindBot (value) {
  bot = value
  movements = null
}

function requireBot () {
  if (!bot || !bot.entity) throw new Error('bot not connected/spawned')
  return bot
}

function getBot () { return requireBot() }
function vec (value) { return value ? { x: Number(value.x), y: Number(value.y), z: Number(value.z) } : null }
function sleep (ms) { return new Promise(resolve => setTimeout(resolve, ms)) }

function stopMotion () {
  if (!bot) return
  try { if (bot.pathfinder && typeof bot.pathfinder.stop === 'function') bot.pathfinder.stop() } catch (_) {}
  try { if (bot.pvp && typeof bot.pvp.stop === 'function') bot.pvp.stop() } catch (_) {}
  try { if (typeof bot.stopDigging === 'function') bot.stopDigging() } catch (_) {}
  try { if (typeof bot.clearControlStates === 'function') bot.clearControlStates() } catch (_) {}
}

function actionTimeoutMs (msg, fallbackMs = 45000) {
  const raw = Number(msg && msg._action_timeout_ms)
  const budget = Number.isFinite(raw) && raw > 0 ? raw : fallbackMs
  return Math.max(500, Math.floor(budget * 0.95))
}

function remainingMs (deadlineMs, capMs) {
  const remaining = deadlineMs - Date.now()
  if (remaining <= 0) throw new Error('ACTION_DEADLINE_EXCEEDED')
  return Math.max(250, Math.min(remaining, capMs))
}

function withTimeout (promise, timeoutMs, label, onTimeout = stopMotion) {
  return new Promise((resolve, reject) => {
    let settled = false
    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      try { if (onTimeout) onTimeout() } catch (_) {}
      const error = new Error(`${label}_TIMEOUT`)
      error.code = `${label}_TIMEOUT`
      reject(error)
    }, Math.max(1, timeoutMs))
    Promise.resolve(promise).then(value => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve(value)
    }, error => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      reject(error)
    })
  })
}

function itemSummary (item) { return item ? { name: item.name, count: item.count, slot: item.slot } : null }

function matchName (name, query) {
  if (!query) return false
  const q = String(query).toLowerCase()
  const n = String(name || '').toLowerCase()
  if (q.startsWith('re:')) return new RegExp(q.slice(3)).test(n)
  return n === q || n.includes(q)
}

function entityMatches (entity, query) {
  return [entity.name, entity.username, entity.displayName, entity.type]
    .some(value => matchName(value, query))
}

function findEntity (query, maxDistance = 32, predicate = null) {
  const activeBot = requireBot()
  const candidates = Object.values(activeBot.entities || {})
    .filter(entity => entity && entity !== activeBot.entity && entity.position && entity.isValid !== false)
    .filter(entity => (!query || entityMatches(entity, query)) && (!predicate || predicate(entity)))
    .map(entity => ({ entity, distance: entity.position.distanceTo(activeBot.entity.position) }))
    .filter(candidate => candidate.distance <= maxDistance)
    .sort((left, right) => left.distance - right.distance)
  return candidates.length > 0 ? candidates[0].entity : null
}

async function waitForInventoryIncrease (name, before, timeoutMs = 2500) {
  const deadline = Date.now() + Math.max(1, timeoutMs)
  while (Date.now() < deadline) {
    const current = inventoryCount(name)
    if (current > before) return current - before
    await sleep(Math.min(100, Math.max(1, deadline - Date.now())))
  }
  return Math.max(0, inventoryCount(name) - before)
}

function inventoryCount (name) {
  const activeBot = requireBot()
  return activeBot.inventory.items()
    .filter(item => item.name === name)
    .reduce((total, item) => total + item.count, 0)
}

function inventoryMap () {
  const activeBot = requireBot()
  const out = {}
  for (const item of activeBot.inventory.items()) out[item.name] = (out[item.name] || 0) + item.count
  return out
}

function inventoryDelta (before, after) {
  const out = {}
  for (const name of new Set([...Object.keys(before), ...Object.keys(after)])) {
    const delta = Number(after[name] || 0) - Number(before[name] || 0)
    if (delta !== 0) out[name] = delta
  }
  return out
}

function isDroppedItemEntity (entity) {
  if (!entity || !entity.position || entity.isValid === false) return false
  if (typeof entity.getDroppedItem === 'function') {
    try { if (entity.getDroppedItem()) return true } catch (_) {}
  }
  const name = String(entity.name || '').toLowerCase()
  return name === 'item' || name === 'item_stack'
}

function findNearbyDroppedItem (position, maxDistance = 6) {
  const activeBot = requireBot()
  const origin = position instanceof Vec3 ? position : new Vec3(Number(position.x), Number(position.y), Number(position.z))
  return Object.values(activeBot.entities || {})
    .filter(entity => entity !== activeBot.entity && isDroppedItemEntity(entity))
    .map(entity => ({ entity, distance: entity.position.distanceTo(origin), botDistance: entity.position.distanceTo(activeBot.entity.position) }))
    .filter(row => row.distance <= maxDistance)
    .sort((a, b) => a.botDistance - b.botDistance)[0]?.entity || null
}

function findInventoryItem (name) {
  return requireBot().inventory.items().find(item => item.name === name) || null
}

async function ensureMovements () {
  const activeBot = requireBot()
  if (!movements) movements = new Movements(activeBot)
  activeBot.pathfinder.setMovements(movements)
}

async function gotoEntity (entity, radius = 0, timeoutMs = 30000) {
  const activeBot = requireBot()
  if (!entity || entity.isValid === false || !entity.position) throw new Error('ENTITY_TARGET_INVALID')
  await ensureMovements()
  const boundedRadius = Math.max(0, Number(radius))
  await withTimeout(
    activeBot.pathfinder.goto(new GoalFollow(entity, boundedRadius)),
    timeoutMs,
    'PATHFINDER_FOLLOW'
  )
  const live = activeBot.entities && activeBot.entities[entity.id] ? activeBot.entities[entity.id] : entity
  return { entity_id: entity.id, position: vec(live.position), valid: live.isValid !== false }
}

function waitForOwnCollection (entity, timeoutMs = 5000) {
  const activeBot = requireBot()
  const targetId = entity && entity.id
  return new Promise(resolve => {
    let settled = false
    let timer = null
    const finish = value => {
      if (settled) return
      settled = true
      if (timer) clearTimeout(timer)
      activeBot.removeListener('playerCollect', onCollect)
      resolve(value)
    }
    const onCollect = (collector, collected) => {
      if (collector && collected && collector.id === activeBot.entity.id && collected.id === targetId) finish(true)
    }
    activeBot.on('playerCollect', onCollect)
    timer = setTimeout(() => finish(false), Math.max(1, timeoutMs))
  })
}

async function gotoPos (position, radius = 1.5, timeoutMs = 30000) {
  const activeBot = requireBot()
  await ensureMovements()
  const target = new Vec3(Number(position.x), Number(position.y), Number(position.z))
  const boundedRadius = Math.max(1, Number(radius))
  await withTimeout(
    activeBot.pathfinder.goto(
      new GoalNear(Math.floor(target.x), Math.floor(target.y), Math.floor(target.z), boundedRadius)
    ),
    timeoutMs,
    'PATHFINDER_GOTO'
  )
  const distance = activeBot.entity.position.distanceTo(target)
  return {
    target: vec(target),
    position: vec(activeBot.entity.position),
    distance,
    within_radius: distance <= Math.max(2.5, boundedRadius + 1)
  }
}

function result (tool, action, status, code, details = {}) {
  if (!['applied', 'partial', 'rejected'].includes(status)) throw new Error(`invalid action status ${status}`)
  return {
    action: { tool, ...action },
    outcome: { status, code, ...details },
    verified: status === 'applied'
  }
}

function applied (tool, action, code, details = {}) { return result(tool, action, 'applied', code, details) }
function partial (tool, action, code, details = {}) { return result(tool, action, 'partial', code, details) }
function rejected (tool, action, code, details = {}) { return result(tool, action, 'rejected', code, details) }

module.exports = {
  actionTimeoutMs,
  applied,
  bindBot,
  ensureMovements,
  entityMatches,
  findEntity,
  findInventoryItem,
  findNearbyDroppedItem,
  getBot,
  gotoEntity,
  gotoPos,
  inventoryCount,
  inventoryDelta,
  inventoryMap,
  isDroppedItemEntity,
  itemSummary,
  waitForInventoryIncrease,
  waitForOwnCollection,
  matchName,
  partial,
  remainingMs,
  rejected,
  requireBot,
  sleep,
  stopMotion,
  vec,
  withTimeout
}
