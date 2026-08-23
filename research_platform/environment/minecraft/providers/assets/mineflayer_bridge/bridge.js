'use strict'

const readline = require('readline')
const mineflayer = require('mineflayer')
const { pathfinder, Movements, goals: { GoalNear } } = require('mineflayer-pathfinder')
const { Vec3 } = require('vec3')

const PROTOCOL_VERSION = 'minecraft-jsonl-v1'
let seq = 0
let bot = null
let movements = null

function emit (kind, payload = {}, requestId = null) {
  const value = { type: 'event', protocol_version: PROTOCOL_VERSION, kind, source: 'mineflayer', seq: ++seq, ts_ms: Date.now(), payload }
  if (requestId) value.request_id = String(requestId)
  process.stdout.write(JSON.stringify(value) + '\n')
}
function ack (cmd, payload = {}, requestId = null) {
  const value = { type: 'ack', protocol_version: PROTOCOL_VERSION, cmd, ...payload }
  if (requestId) value.request_id = String(requestId)
  process.stdout.write(JSON.stringify(value) + '\n')
}
function vec (v) { return v ? { x: Number(v.x), y: Number(v.y), z: Number(v.z) } : null }
function itemSummary (item) { return item ? { name: item.name, count: item.count, slot: item.slot } : null }
function sleep (ms) { return new Promise(resolve => setTimeout(resolve, ms)) }
function inventoryCount (name) {
  if (!bot || !bot.inventory) return 0
  return bot.inventory.items().filter(i => i.name === name).reduce((a, b) => a + b.count, 0)
}
function inventoryMap () {
  const out = {}
  if (!bot || !bot.inventory) return out
  for (const item of bot.inventory.items()) out[item.name] = (out[item.name] || 0) + item.count
  return out
}
function selfSnapshot (requestId = null) {
  requireBot()
  emit('self_snapshot', {
    username: bot.username, position: vec(bot.entity.position), yaw: bot.entity.yaw, pitch: bot.entity.pitch,
    health: bot.health, food: bot.food, held_item: itemSummary(bot.heldItem),
    inventory: bot.inventory ? bot.inventory.items().map(itemSummary) : [], dimension: bot.game ? bot.game.dimension : null
  }, requestId)
}
function observeEntities (maxDistance = 16, limit = 32, requestId = null) {
  requireBot()
  const origin = bot.entity.position
  const entities = Object.values(bot.entities || {}).filter(e => e && e !== bot.entity && e.position && e.isValid !== false)
    .map(e => ({ entity: e, distance: e.position.distanceTo(origin) })).filter(x => x.distance <= maxDistance)
    .sort((a, b) => a.distance - b.distance).slice(0, limit)
  for (const { entity, distance } of entities) emit('entity_observation', {
    id: entity.id, uuid: entity.uuid || null, name: entity.name || null, username: entity.username || null,
    display_name: entity.displayName || null, type: entity.type || null, mob_type: entity.mobType || null,
    position: vec(entity.position), distance, is_valid: entity.isValid !== false
  }, requestId)
  return entities.length
}
function requireBot () { if (!bot || !bot.entity) throw new Error('bot not connected/spawned') }
function matchName (name, query) {
  if (!query) return false
  const q = String(query).toLowerCase()
  const n = String(name || '').toLowerCase()
  if (q.startsWith('re:')) return new RegExp(q.slice(3)).test(n)
  return n === q || n.includes(q)
}
function findBlockByQuery (query, maxDistance = 48) {
  requireBot()
  return bot.findBlock({ matching: block => block && matchName(block.name, query), maxDistance })
}
async function ensureMovements () {
  requireBot()
  if (!movements) movements = new Movements(bot)
  bot.pathfinder.setMovements(movements)
}
async function gotoPos (position, radius = 1.5) {
  requireBot(); await ensureMovements()
  const target = new Vec3(Number(position.x), Number(position.y), Number(position.z))
  await bot.pathfinder.goto(new GoalNear(Math.floor(target.x), Math.floor(target.y), Math.floor(target.z), Math.max(1, Number(radius))))
  const distance = bot.entity.position.distanceTo(target)
  return { distance, position: vec(bot.entity.position), verified: distance <= Math.max(2.5, Number(radius) + 1.0) }
}
async function actionGoto (msg) {
  const result = await gotoPos(msg.position || {}, Number(msg.radius || 1.5))
  return { action: { tool: 'goto', position: msg.position, radius: Number(msg.radius || 1.5) }, outcome: result, verified: result.verified }
}
async function actionCollect (msg) {
  requireBot(); await ensureMovements()
  const query = String(msg.block || msg.query || '')
  const count = Math.max(1, Math.min(64, Number(msg.count || 1)))
  const maxDistance = Math.max(4, Math.min(128, Number(msg.max_distance || 48)))
  const before = inventoryMap(); const dug = []; const missing = []
  for (let i = 0; i < count; i++) {
    const block = findBlockByQuery(query, maxDistance)
    if (!block) { missing.push(query); break }
    const bpos = block.position.clone()
    await bot.pathfinder.goto(new GoalNear(bpos.x, bpos.y, bpos.z, 3))
    const live = bot.blockAt(bpos)
    if (!live || live.name === 'air') continue
    await bot.lookAt(live.position.offset(0.5, 0.5, 0.5), true)
    await bot.dig(live, true)
    dug.push({ name: live.name, position: vec(bpos) })
    await sleep(350)
    try { await bot.pathfinder.goto(new GoalNear(bpos.x, bpos.y, bpos.z, 1)) } catch (_) {}
    await sleep(250)
  }
  const after = inventoryMap()
  const verified = dug.length >= count
  return { action: { tool: 'collect_block', block: query, count }, outcome: { dug, missing, inventory_before: before, inventory_after: after }, verified }
}
async function actionCraft (msg) {
  requireBot(); await ensureMovements()
  const name = String(msg.item || '')
  const count = Math.max(1, Math.min(64, Number(msg.count || 1)))
  const item = bot.registry.itemsByName[name]
  if (!item) return { action: { tool: 'craft_item', item: name, count }, outcome: { error: 'unknown_item' }, verified: false }
  const before = inventoryCount(name)
  let table = null
  let recipes = bot.recipesFor(item.id, null, count, null)
  if (!recipes || recipes.length === 0) {
    const block = bot.findBlock({ matching: b => b && b.name === 'crafting_table', maxDistance: 32 })
    if (block) {
      await bot.pathfinder.goto(new GoalNear(block.position.x, block.position.y, block.position.z, 3))
      table = bot.blockAt(block.position)
      recipes = bot.recipesFor(item.id, null, count, table)
    }
  }
  if (!recipes || recipes.length === 0) return { action: { tool: 'craft_item', item: name, count }, outcome: { error: 'no_recipe_or_materials' }, verified: false }
  await bot.craft(recipes[0], count, table)
  await sleep(200)
  const after = inventoryCount(name)
  return { action: { tool: 'craft_item', item: name, count }, outcome: { before, after }, verified: after > before }
}
async function actionPlace (msg) {
  requireBot(); await ensureMovements()
  const name = String(msg.item || '')
  const item = bot.inventory.items().find(i => i.name === name)
  if (!item) return { action: { tool: 'place_block', item: name }, outcome: { error: 'item_not_in_inventory' }, verified: false }
  const p = msg.position || vec(bot.entity.position.floored().offset(1, 0, 0))
  const target = new Vec3(Math.floor(Number(p.x)), Math.floor(Number(p.y)), Math.floor(Number(p.z)))
  await gotoPos(target, 3)
  await bot.equip(item, 'hand')
  const faces = [new Vec3(0, -1, 0), new Vec3(0, 1, 0), new Vec3(-1, 0, 0), new Vec3(1, 0, 0), new Vec3(0, 0, -1), new Vec3(0, 0, 1)]
  let placed = null
  for (const face of faces) {
    const refPos = target.minus(face)
    const ref = bot.blockAt(refPos)
    if (!ref || ref.name === 'air') continue
    try { await bot.placeBlock(ref, face); placed = bot.blockAt(target); break } catch (_) {}
  }
  return { action: { tool: 'place_block', item: name, position: vec(target) }, outcome: { placed: placed ? placed.name : null, position: vec(target) }, verified: Boolean(placed && placed.name !== 'air') }
}
async function actionAttack (msg) {
  requireBot(); await ensureMovements()
  const query = String(msg.entity || msg.query || '').toLowerCase()
  const maxDistance = Number(msg.max_distance || 32)
  const candidates = Object.values(bot.entities || {}).filter(e => e && e !== bot.entity && e.position && e.isValid !== false)
    .filter(e => !query || [e.name, e.username, e.displayName, e.mobType, e.type].some(x => String(x || '').toLowerCase().includes(query)))
    .map(e => ({ e, d: e.position.distanceTo(bot.entity.position) })).filter(x => x.d <= maxDistance).sort((a, b) => a.d - b.d)
  if (!candidates.length) return { action: { tool: 'attack_nearest', entity: query }, outcome: { error: 'no_matching_entity' }, verified: false }
  const target = candidates[0].e
  await bot.pathfinder.goto(new GoalNear(Math.floor(target.position.x), Math.floor(target.position.y), Math.floor(target.position.z), 2))
  const maxHits = Math.max(1, Math.min(20, Number(msg.max_hits || 8)))
  for (let i = 0; i < maxHits && target.isValid !== false; i++) { bot.attack(target); await sleep(450) }
  return { action: { tool: 'attack_nearest', entity: query }, outcome: { target_id: target.id, target_valid_after: target.isValid !== false }, verified: target.isValid === false }
}
async function actionWait (msg) {
  const ms = Math.max(0, Math.min(10000, Number(msg.ms || 500)))
  await sleep(ms)
  return { action: { tool: 'wait', ms }, outcome: { waited_ms: ms }, verified: true }
}
function registrySearch (msg) {
  requireBot(); const q = String(msg.query || '').toLowerCase(); const limit = Math.max(1, Math.min(100, Number(msg.limit || 20)))
  const items = Object.values(bot.registry.items || {}).filter(x => x && String(x.name).includes(q)).slice(0, limit).map(x => x.name)
  const blocks = Object.values(bot.registry.blocks || {}).filter(x => x && String(x.name).includes(q)).slice(0, limit).map(x => x.name)
  return { items, blocks }
}
function connect (options) {
  if (bot) throw new Error('bot already exists')
  const requestId = options.request_id || null
  bot = mineflayer.createBot({ host: options.host || '127.0.0.1', port: Number(options.port || 25565), username: options.username || 'ResearchBot', auth: options.auth || 'offline', version: options.version || false, checkTimeoutInterval: Number(options.checkTimeoutInterval || 30000) })
  bot.loadPlugin(pathfinder)
  bot.once('spawn', () => { movements = new Movements(bot); bot.pathfinder.setMovements(movements); emit('bridge_status', { status: 'spawned', username: bot.username, version: bot.version }, requestId); selfSnapshot(requestId) })
  bot.on('health', () => emit('health', { health: bot.health, food: bot.food }))
  bot.on('death', () => emit('death', { username: bot.username }))
  bot.on('kicked', (reason, loggedIn) => emit('kicked', { reason: String(reason), logged_in: Boolean(loggedIn) }))
  bot.on('error', err => emit('error', { message: String(err && err.message ? err.message : err) }))
  bot.on('end', reason => emit('end', { reason: String(reason || '') }))
}
async function runAction (cmd, msg) {
  let result
  if (cmd === 'goto') result = await actionGoto(msg)
  else if (cmd === 'collect_block') result = await actionCollect(msg)
  else if (cmd === 'craft_item') result = await actionCraft(msg)
  else if (cmd === 'place_block') result = await actionPlace(msg)
  else if (cmd === 'attack_nearest') result = await actionAttack(msg)
  else if (cmd === 'wait') result = await actionWait(msg)
  else throw new Error(`unknown action command ${cmd}`)
  emit('action_result', { action_id: msg.action_id || null, task_id: msg.task_id || null, task_lineage: msg.task_lineage || null, task: msg.task || '', context: msg.context || '', action: result.action, outcome: result.outcome, anchors: Array.isArray(msg.anchors) ? msg.anchors : [], verified: Boolean(result.verified) }, msg.request_id || msg.action_id || null)
  selfSnapshot(msg.request_id || msg.action_id || null)
  ack(cmd, { verified: Boolean(result.verified) }, msg.request_id || msg.action_id || null)
}
function emitLookupResult (cmd, msg, outcome, verified = true) {
  emit('action_result', {
    action_id: msg.action_id || null,
    task_id: msg.task_id || null,
    task_lineage: msg.task_lineage || null,
    task: msg.task || '',
    context: msg.context || '',
    action: { tool: cmd, ...msg },
    outcome,
    anchors: Array.isArray(msg.anchors) ? msg.anchors : [],
    verified
  }, msg.request_id || msg.action_id || null)
}
async function command (msg) {
  const cmd = String(msg.cmd || '')
  const requestId = msg.request_id || null
  if (cmd === 'connect') { connect(msg); ack(cmd, {}, requestId); return }
  if (cmd === 'snapshot') { selfSnapshot(requestId); ack(cmd, {}, requestId); return }
  if (cmd === 'observe_entities') {
    const count = observeEntities(Number(msg.max_distance || 16), Number(msg.limit || 32), requestId)
    emitLookupResult(cmd, msg, { observed_count: count }, true)
    ack(cmd, { verified: true }, requestId)
    return
  }
  if (cmd === 'registry_search') {
    const result = registrySearch(msg)
    emitLookupResult(cmd, msg, result, true)
    ack(cmd, { ...result, verified: true }, requestId)
    return
  }
  if (cmd === 'task_event') {
    requireBot()
    emit('task_event', {
      task_id: msg.task_id || null,
      task: msg.task || msg.goal || '',
      goal: msg.goal || msg.task || '',
      context: msg.context || '',
      task_lineage: msg.task_lineage || msg.task_id || null,
      anchors: Array.isArray(msg.anchors) ? msg.anchors : [],
      status: msg.status || 'OBSERVED'
    }, requestId)
    ack(cmd, {}, requestId)
    return
  }
  if (['goto', 'collect_block', 'craft_item', 'place_block', 'attack_nearest', 'wait'].includes(cmd)) { await runAction(cmd, msg); return }
  if (cmd === 'chat') {
    requireBot()
    const message = String(msg.message || '')
    bot.chat(message)
    emitLookupResult(cmd, msg, { message }, true)
    ack(cmd, { verified: true }, requestId)
    return
  }
  if (cmd === 'quit') { ack(cmd, {}, requestId); if (bot) bot.quit('Research Platform bridge shutdown'); setTimeout(() => process.exit(0), 20); return }
  throw new Error(`unknown command: ${cmd}`)
}
const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity })
rl.on('line', line => {
  let msg
  try { msg = JSON.parse(line) } catch (err) { emit('error', { message: `invalid json command: ${err.message}` }); return }
  Promise.resolve(command(msg)).catch(err => {
    emit('error', { message: String(err.message || err), cmd: msg.cmd || null }, msg.request_id || null)
    ack(String(msg.cmd || ''), { verified: false, error: String(err.message || err) }, msg.request_id || null)
  })
})
