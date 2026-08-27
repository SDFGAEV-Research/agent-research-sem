'use strict'

const { goals: { GoalNear } } = require('mineflayer-pathfinder')
const { Vec3 } = require('vec3')
const runtime = require('./runtime')

function findBlock (query, maxDistance) {
  const activeBot = runtime.getBot()
  return activeBot.findBlock({
    matching: block => block && runtime.matchName(block.name, query),
    maxDistance
  })
}

async function collectBlock (msg) {
  const activeBot = runtime.getBot()
  await runtime.ensureMovements()
  const action = {
    block: String(msg.block || msg.query || ''),
    count: Number(msg.count || 1),
    max_distance: Number(msg.max_distance || 48)
  }
  const deadline = Date.now() + runtime.actionTimeoutMs(msg)
  const before = runtime.inventoryMap()
  const broken = []
  const errors = []
  for (let index = 0; index < action.count; index++) {
    const block = findBlock(action.block, action.max_distance)
    if (!block) break
    const position = block.position.clone()
    const distance = activeBot.entity.position.distanceTo(position)
    if (distance > 4.0) {
      try {
        await runtime.gotoPos(position, 3, runtime.remainingMs(deadline, 30000))
      } catch (error) {
        errors.push({ phase: 'approach', message: String(error.message || error), position: runtime.vec(position) })
        break
      }
    }
    const live = activeBot.blockAt(position)
    if (!live || live.name === 'air') continue
    const blockName = live.name
    const itemBefore = runtime.inventoryCount(blockName)
    try {
      await runtime.withTimeout(
        activeBot.lookAt(live.position.offset(0.5, 0.5, 0.5), true),
        runtime.remainingMs(deadline, 5000),
        'LOOK_AT_BLOCK'
      )
      await runtime.withTimeout(
        activeBot.dig(live, true),
        runtime.remainingMs(deadline, 15000),
        'DIG_BLOCK'
      )
    } catch (error) {
      errors.push({ phase: 'dig', message: String(error.message || error), position: runtime.vec(position) })
      break
    }
    const afterDig = activeBot.blockAt(position)
    if (!afterDig || afterDig.name !== blockName) broken.push({ name: blockName, position: runtime.vec(position) })
    let gainedForBlock = await runtime.waitForInventoryIncrease(
      blockName, itemBefore, runtime.remainingMs(deadline, 2500)
    )
    if (gainedForBlock <= 0) {
      const dropped = runtime.findNearbyDroppedItem(position, 6)
      if (dropped && dropped.position) {
        try {
          const pickupWaitMs = runtime.remainingMs(deadline, 10000)
          const ownCollection = runtime.waitForOwnCollection(dropped, pickupWaitMs)
          let navigationError = null
          try {
            await runtime.gotoEntity(dropped, 0, pickupWaitMs)
          } catch (error) {
            navigationError = error
          }
          const collectedByBot = await ownCollection
          gainedForBlock = await runtime.waitForInventoryIncrease(
            blockName, itemBefore, runtime.remainingMs(deadline, 2500)
          )
          if (!collectedByBot && gainedForBlock <= 0 && navigationError) throw navigationError
          if (!collectedByBot && gainedForBlock <= 0) throw new Error('PLAYER_COLLECT_NOT_OBSERVED')
        } catch (error) {
          errors.push({ phase: 'pickup', message: String(error.message || error), position: runtime.vec(dropped.position) })
        }
      } else {
        await runtime.sleep(Math.min(500, runtime.remainingMs(deadline, 500)))
      }
    }
  }
  const after = runtime.inventoryMap()
  const delta = runtime.inventoryDelta(before, after)
  const collectedCount = Object.values(delta).filter(value => value > 0).reduce((sum, value) => sum + value, 0)
  const details = {
    requested_count: action.count,
    broken,
    errors,
    inventory_before: before,
    inventory_after: after,
    inventory_delta: delta,
    collected_count: collectedCount
  }
  if (broken.length === 0) return runtime.rejected('collect_block', action, errors.length ? 'COLLECTION_FAILED' : 'BLOCK_NOT_FOUND', details)
  if (broken.length >= action.count && collectedCount >= action.count) {
    return runtime.applied('collect_block', action, 'BLOCKS_COLLECTED', details)
  }
  return runtime.partial('collect_block', action, 'COLLECTION_INCOMPLETE', details)
}

async function craftItem (msg) {
  const activeBot = runtime.getBot()
  const action = { item: String(msg.item || ''), count: Number(msg.count || 1) }
  const item = activeBot.registry.itemsByName[action.item]
  if (!item) return runtime.rejected('craft_item', action, 'UNKNOWN_ITEM')
  const before = runtime.inventoryCount(action.item)
  let table = null
  let recipes = activeBot.recipesFor(item.id, null, 1, null)
  if (!recipes || recipes.length === 0) {
    let tableBlock = activeBot.findBlock({
      matching: block => block && block.name === 'crafting_table',
      maxDistance: 32
    })
    if (!tableBlock) {
      const carriedTable = runtime.findInventoryItem('crafting_table')
      const tableRecipes = activeBot.recipesFor(item.id, null, 1, true)
      if (!carriedTable || !tableRecipes || tableRecipes.length === 0) {
        return runtime.rejected('craft_item', action, 'NO_RECIPE_OR_CRAFTING_TABLE', { before })
      }
      const origin = activeBot.entity.position.floored()
      let placement = null
      for (let radius = 1; radius <= 3 && !placement; radius++) {
        for (let x = -radius; x <= radius && !placement; x++) {
          for (let z = -radius; z <= radius && !placement; z++) {
            const candidate = origin.offset(x, 0, z)
            const targetBlock = activeBot.blockAt(candidate)
            const below = activeBot.blockAt(candidate.offset(0, -1, 0))
            if (targetBlock && targetBlock.name === 'air' && below && below.name !== 'air') placement = candidate
          }
        }
      }
      if (!placement) return runtime.rejected('craft_item', action, 'NO_TABLE_PLACEMENT_SPACE', { before })
      const placed = await placeBlock({ item: 'crafting_table', position: runtime.vec(placement) })
      if (!placed.verified) return runtime.rejected('craft_item', action, 'CRAFTING_TABLE_PLACEMENT_FAILED', { before, placement: placed.outcome })
      tableBlock = activeBot.blockAt(placement)
    }
    await runtime.ensureMovements()
    await activeBot.pathfinder.goto(new GoalNear(tableBlock.position.x, tableBlock.position.y, tableBlock.position.z, 3))
    table = activeBot.blockAt(tableBlock.position)
    recipes = activeBot.recipesFor(item.id, null, 1, table)
  }
  if (!recipes || recipes.length === 0) {
    return runtime.rejected('craft_item', action, 'NO_RECIPE_OR_MATERIALS', { before, used_table: Boolean(table) })
  }
  const recipe = recipes[0]
  const outputPerCraft = Math.max(1, Number(recipe.result && recipe.result.count ? recipe.result.count : 1))
  const executions = Math.ceil(action.count / outputPerCraft)
  await activeBot.craft(recipe, executions, table)
  await runtime.sleep(250)
  const after = runtime.inventoryCount(action.item)
  const crafted = Math.max(0, after - before)
  const details = { before, after, crafted, executions, output_per_craft: outputPerCraft, used_table: Boolean(table) }
  if (crafted >= action.count) return runtime.applied('craft_item', action, 'ITEM_CRAFTED', details)
  if (crafted > 0) return runtime.partial('craft_item', action, 'CRAFT_COUNT_INCOMPLETE', details)
  return runtime.rejected('craft_item', action, 'CRAFT_EFFECT_NOT_OBSERVED', details)
}

function selectFuel (requested) {
  if (requested) return runtime.findInventoryItem(requested)
  const preferred = [
    'coal', 'charcoal', 'coal_block', 'blaze_rod', 'dried_kelp_block',
    'oak_planks', 'spruce_planks', 'birch_planks', 'jungle_planks',
    'acacia_planks', 'dark_oak_planks', 'mangrove_planks', 'cherry_planks'
  ]
  for (const name of preferred) {
    const item = runtime.findInventoryItem(name)
    if (item) return item
  }
  return null
}

function fuelCapacity (name) {
  if (name === 'coal_block') return 80
  if (['coal', 'charcoal'].includes(name)) return 8
  if (name === 'blaze_rod') return 12
  if (name === 'dried_kelp_block') return 20
  return 1.5
}

async function smeltItem (msg) {
  const activeBot = runtime.getBot()
  await runtime.ensureMovements()
  const action = {
    item: String(msg.item || ''),
    count: Number(msg.count || 1),
    fuel: msg.fuel ? String(msg.fuel) : null,
    max_distance: Number(msg.max_distance || 32),
    max_wait_s: Number(msg.max_wait_s || 90)
  }
  const input = runtime.findInventoryItem(action.item)
  if (!input || input.count < action.count) {
    return runtime.rejected('smelt_item', action, 'INPUT_NOT_AVAILABLE', { available: input ? input.count : 0 })
  }
  const fuel = selectFuel(action.fuel)
  if (!fuel) return runtime.rejected('smelt_item', action, 'FUEL_NOT_AVAILABLE')
  const block = activeBot.findBlock({
    matching: candidate => candidate && ['furnace', 'blast_furnace', 'smoker'].includes(candidate.name),
    maxDistance: action.max_distance
  })
  if (!block) return runtime.rejected('smelt_item', action, 'FURNACE_NOT_FOUND')
  await activeBot.pathfinder.goto(new GoalNear(block.position.x, block.position.y, block.position.z, 3))
  const before = runtime.inventoryMap()
  let furnace = null
  let outputObserved = null
  try {
    furnace = await activeBot.openFurnace(activeBot.blockAt(block.position))
    const existingOutput = furnace.outputItem()
    if (existingOutput) {
      return runtime.rejected('smelt_item', action, 'FURNACE_OUTPUT_NOT_EMPTY', {
        furnace: runtime.vec(block.position),
        output: runtime.itemSummary(existingOutput)
      })
    }
    const existingInput = furnace.inputItem()
    if (existingInput && existingInput.type !== input.type) {
      return runtime.rejected('smelt_item', action, 'FURNACE_INPUT_CONFLICT', {
        furnace: runtime.vec(block.position),
        input: runtime.itemSummary(existingInput)
      })
    }
    const existingInputCount = existingInput ? existingInput.count : 0
    const inputNeeded = Math.max(0, action.count - existingInputCount)
    const existingFuel = furnace.fuelItem()
    const fuelNeeded = existingFuel ? 0 : Math.ceil(action.count / fuelCapacity(fuel.name))
    if (fuel.count < fuelNeeded) {
      return runtime.rejected('smelt_item', action, 'FUEL_COUNT_NOT_AVAILABLE', {
        available: fuel.count,
        required: fuelNeeded,
        fuel: fuel.name
      })
    }
    if (fuelNeeded > 0) await furnace.putFuel(fuel.type, null, fuelNeeded)
    if (inputNeeded > 0) await furnace.putInput(input.type, null, inputNeeded)
    const deadline = Date.now() + action.max_wait_s * 1000
    while (Date.now() < deadline) {
      const output = furnace.outputItem()
      if (output && output.count >= action.count) {
        outputObserved = runtime.itemSummary(output)
        break
      }
      await runtime.sleep(500)
    }
    if (furnace.outputItem()) await furnace.takeOutput()
  } finally {
    if (furnace) furnace.close()
  }
  const after = runtime.inventoryMap()
  const delta = runtime.inventoryDelta(before, after)
  const produced = Object.entries(delta)
    .filter(([name, value]) => name !== action.item && value > 0)
    .reduce((sum, [, value]) => sum + value, 0)
  const details = { furnace: runtime.vec(block.position), output: outputObserved, inventory_delta: delta, produced }
  if (produced >= action.count) return runtime.applied('smelt_item', action, 'ITEM_SMELTED', details)
  return runtime.partial('smelt_item', action, 'SMELT_INCOMPLETE', details)
}

async function clearFurnace (msg) {
  const activeBot = runtime.getBot()
  await runtime.ensureMovements()
  const action = { max_distance: Number(msg.max_distance || 32) }
  const block = activeBot.findBlock({
    matching: candidate => candidate && ['furnace', 'blast_furnace', 'smoker'].includes(candidate.name),
    maxDistance: action.max_distance
  })
  if (!block) return runtime.rejected('clear_furnace', action, 'FURNACE_NOT_FOUND')
  await activeBot.pathfinder.goto(new GoalNear(block.position.x, block.position.y, block.position.z, 3))
  const before = runtime.inventoryMap()
  let furnace = null
  try {
    furnace = await activeBot.openFurnace(activeBot.blockAt(block.position))
    if (furnace.outputItem()) await furnace.takeOutput()
    if (furnace.inputItem()) await furnace.takeInput()
    if (furnace.fuelItem()) await furnace.takeFuel()
  } finally {
    if (furnace) furnace.close()
  }
  const after = runtime.inventoryMap()
  return runtime.applied('clear_furnace', action, 'FURNACE_CLEARED', {
    furnace: runtime.vec(block.position),
    inventory_delta: runtime.inventoryDelta(before, after)
  })
}

async function placeBlock (msg) {
  const activeBot = runtime.getBot()
  await runtime.ensureMovements()
  const action = { item: String(msg.item || ''), position: msg.position || null }
  const item = runtime.findInventoryItem(action.item)
  if (!item) return runtime.rejected('place_block', action, 'ITEM_NOT_AVAILABLE')
  const position = action.position || runtime.vec(activeBot.entity.position.floored().offset(1, 0, 0))
  const target = new Vec3(Math.floor(Number(position.x)), Math.floor(Number(position.y)), Math.floor(Number(position.z)))
  await runtime.gotoPos(target, 3)
  await activeBot.equip(item, 'hand')
  const faces = [
    new Vec3(0, -1, 0), new Vec3(0, 1, 0), new Vec3(-1, 0, 0),
    new Vec3(1, 0, 0), new Vec3(0, 0, -1), new Vec3(0, 0, 1)
  ]
  let lastError = null
  for (const face of faces) {
    const reference = activeBot.blockAt(target.minus(face))
    if (!reference || reference.name === 'air') continue
    try {
      await activeBot.placeBlock(reference, face)
      const placed = activeBot.blockAt(target)
      const details = { position: runtime.vec(target), placed: placed ? placed.name : null }
      if (placed && placed.name !== 'air') return runtime.applied('place_block', action, 'BLOCK_PLACED', details)
    } catch (error) {
      lastError = error
    }
  }
  return runtime.rejected('place_block', action, 'NO_VALID_PLACEMENT_FACE', {
    position: runtime.vec(target),
    error: lastError ? lastError.message : null
  })
}

module.exports = {
  clear_furnace: clearFurnace,
  collect_block: collectBlock,
  craft_item: craftItem,
  place_block: placeBlock,
  smelt_item: smeltItem
}
