// Run with: TZ=Africa/Casablanca node --test tests/
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const source = readFileSync(new URL("../Model.js", import.meta.url), "utf8").replace(/^\.pragma library/m, "")
const Model = new Function(source + "; return { countdown, usesTwentyFourHour, safeShared, coarseCoordinate, coarseLocation }")()

test("countdown rounds up to whole minutes", () => {
  assert.deepEqual(Model.countdown(3 * 3600000 + 61000, 0), { hours: 3, minutes: 2 })
  assert.deepEqual(Model.countdown(1, 0), { hours: 0, minutes: 1 })
  assert.deepEqual(Model.countdown(0, 5), { hours: 0, minutes: 0 })
})
test("12- and 24-hour locale formats", () => {
  assert.equal(Model.usesTwentyFourHour("HH:mm"), true)
  assert.equal(Model.usesTwentyFourHour("h:mm AP"), false)
  assert.equal(Model.usesTwentyFourHour("H 'a' mm"), true)
})
test("shared button and tooltip text cannot contain markup", () => {
  const text = Model.safeShared('<img src="https://example.invalid/tracker"> & text')
  assert.ok(!/[<>&]/.test(text))
  assert.equal(Model.safeShared(null), "")
})
test("saved coordinates keep about one kilometre of precision", () => {
  assert.equal(Model.coarseCoordinate(33.5731), 33.57)
  assert.equal(Model.coarseCoordinate(-7.5898), -7.59)
  assert.equal(Model.coarseCoordinate("55.983226"), 55.98)
  assert.equal(Model.coarseCoordinate(-0.004), 0)
  assert.equal(Model.coarseCoordinate(35.68), 35.68)
  assert.equal(Model.coarseCoordinate(999.999), 1000) // range is validated elsewhere
  for (const untouched of [null, undefined, "", "  ", "north", true]) assert.equal(Model.coarseCoordinate(untouched), untouched)
  assert.ok(Number.isNaN(Model.coarseCoordinate(NaN)))
})
test("only the location of an entry is coarsened, without mutating it", () => {
  const entry = { city: "Edinburgh", latitude: 55.983226, longitude: -3.216649, volume: 33.333 }
  assert.deepEqual(Model.coarseLocation(entry), { city: "Edinburgh", latitude: 55.98, longitude: -3.22, volume: 33.333 })
  assert.equal(entry.latitude, 55.983226)
  assert.deepEqual(Model.coarseLocation({ notify: false }), { notify: false })
  assert.deepEqual(Model.coarseLocation(Model.coarseLocation(entry)), Model.coarseLocation(entry))
})
