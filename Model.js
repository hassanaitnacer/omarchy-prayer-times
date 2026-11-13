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
