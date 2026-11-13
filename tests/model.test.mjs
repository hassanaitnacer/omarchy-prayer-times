// Run with: TZ=Africa/Casablanca node --test tests/
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const source = readFileSync(new URL("../Model.js", import.meta.url), "utf8").replace(/^\.pragma library/m, "")
const Model = new Function(source + "; return { countdown, usesTwentyFourHour, safeShared }")()

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
