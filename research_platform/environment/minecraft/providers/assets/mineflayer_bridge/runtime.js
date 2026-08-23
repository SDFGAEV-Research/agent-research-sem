'use strict'

const { Movements, goals: { GoalNear } } = require('mineflayer-pathfinder')
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
function itemSummary (item) { return item ? { name: item.name, count: item.count, slot: item.slot } : null }

function matchName (name, query) {
  if (!query) return false
  const q = String(query).toLowerCase()
  const n = String(name || '').toLowerCase()
  if (q.startsWith('re:')) return new RegExp(q.slice(3)).test(n)
  return n === q || n.includes(q)
}

function entityMatches (entity, query) {
  return [entity.name, entity.username, entity.displayName, entity.mobType, entity.type]
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

function findInventoryItem (name) {
  return requireBot().inventory.items().find(item => item.name === name) || null
}

async function ensureMovements () {
  const activeBot = requireBot()
  if (!movements) movements = new Movements(activeBot)
  activeBot.pathfinder.setMovements(movements)
}

async function gotoPos (position, radius = 1.5) {
  const activeBot = requireBot()
  await ensureMovements()
  const target = new Vec3(Number(position.x), Number(position.y), Number(position.z))
  const boundedRadius = Math.max(1, Number(radius))
  await activeBot.pathfinder.goto(
    new GoalNear(Math.floor(target.x), Math.floor(target.y), Math.floor(target.z), boundedRadius)
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
  applied,
  bindBot,
  ensureMovements,
  entityMatches,
  findEntity,
  findInventoryItem,
  getBot,
  gotoPos,
  inventoryCount,
  inventoryDelta,
  inventoryMap,
  itemSummary,
  matchName,
  partial,
  rejected,
  requireBot,
  sleep,
  vec
}
