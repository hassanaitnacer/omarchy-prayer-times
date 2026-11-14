.pragma library

// Small display helpers; calculations and civil time live in engine.py.
// Whole minutes left, rounded up so "in 1m" holds until the time itself.
function countdown(targetMs, nowMs) {
  var minutes = Math.max(0, Math.ceil((targetMs - nowMs) / 60000))
  return { hours: Math.floor(minutes / 60), minutes: minutes % 60 }
}

function usesTwentyFourHour(format) {
  return !/[aA]/.test(String(format || "").replace(/'[^']*'/g, ""))
}

// Omarchy-owned tooltips/buttons may accept rich text. Neutralize markup.
function safeShared(value) {
  return String(value || "").replace(/&/g, "＆").replace(/</g, "‹").replace(/>/g, "›")
}

// Prayer times move by seconds per kilometre, so settings keep roughly 1 km
// of location precision (two decimals) instead of an exact position.
function coarseCoordinate(value) {
  if (value === null || value === undefined || typeof value === "boolean" || String(value).trim() === "") return value
  var n = Number(value)
  return isFinite(n) ? Math.round(n * 100) / 100 + 0 : value  // "+ 0" turns -0 into 0
}

function coarseLocation(entry) {
  var out = Object.assign({}, entry)
  if ("latitude" in out) out.latitude = coarseCoordinate(out.latitude)
  if ("longitude" in out) out.longitude = coarseCoordinate(out.longitude)
  return out
}
