import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Column {
  id: form
  required property var host
  required property var strings
  property string section: ""
  spacing: Style.space(6)
  function t(key) { return strings.t(key) }
  function save(key, value) { host.persistSetting(key, value) }
  function value(key, fallback) { return host.setting(key, fallback) }
  function safe(text) { return String(text).replace(/&/g, "＆").replace(/</g, "‹").replace(/>/g, "›") }
  function adjust(name, value) {
    var values = Object.assign({}, host.setting("adjust", {}))
    values[name] = value
    save("adjust", values)
  }

  component Action: Button {
    width: parent.width
    focusable: true
    leftAlign: true
    fontSize: Style.font.bodySmall
    onActiveFocusChanged: if (activeFocus) form.host.ensureVisible(this)
  }
  component Group: Action {
    property string key
    text: form.t("settings." + key) + (form.section === key ? "  −" : "  +")
    selected: form.section === key
    onClicked: form.section = form.section === key ? "" : key
  }
  component Toggle: Action {
    property string key
    property bool fallback: false
    text: form.t("settings." + key) + "  ·  " + form.t(form.value(key, fallback) ? "on" : "off")
    onClicked: form.save(key, !form.value(key, fallback))
  }
  component Field: Column {
    property string key
    property string label: form.t("settings." + key)
    property string fallback: ""
    property bool numeric: false
    property real low: -1e9
    property real high: 1e9
    property bool valid: true
    property var initialValue: form.value(key, fallback)
    signal committed(var value)
    width: parent.width
    spacing: Style.space(3)
    PlainText { text: parent.label; width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption; opacity: .7 }
    TextField {
      id: input
      width: parent.width
      text: String(parent.initialValue)
      maximumLength: parent.key === "audioFile" ? 1024 : 80
      selectByMouse: true
      onActiveFocusChanged: if (activeFocus) form.host.ensureVisible(parent)
      onEditingFinished: {
        var val = parent.numeric ? Number(text) : text.trim()
        parent.valid = !parent.numeric || (text.trim() !== "" && isFinite(val) && val >= parent.low && val <= parent.high)
        if (parent.valid) {
          if (parent.key) form.save(parent.key, val)
          parent.committed(val)
        }
      }
    }
    PlainText { visible: !parent.valid; text: form.t("settings.invalid"); font.pixelSize: Style.font.caption; width: parent.width; wrapMode: Text.WordWrap }
  }
  component Choice: Column {
    property string key
    property var choices: []
    property string fallback: ""
    property bool expanded: false
    width: parent.width
    Action {
      text: form.t("settings." + parent.key) + " · " + form.t("option." + form.value(parent.key, parent.fallback))
      onClicked: parent.expanded = !parent.expanded
    }
    Column {
      width: parent.width
      visible: parent.expanded
      Repeater {
        model: parent.parent.choices
        Action {
          required property var modelData
          text: "  " + form.t("option." + modelData)
          selected: String(form.value(parent.parent.key, parent.parent.fallback)) === String(modelData)
          onClicked: {
            var choice = parent.parent
            if (choice.key === "method") form.host.chooseMethod(modelData)
            else form.save(choice.key, modelData)
            choice.expanded = false
          }
        }
      }
    }
  }

  Group { key: "location" }
  Column {
    width: parent.width
    visible: form.section === "location"
    spacing: Style.space(8)
    Action { text: form.t("city.choose"); onClicked: form.host.choosingCity = true }
    PlainText { width: parent.width; text: form.t("settings.manual"); wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption; opacity: .7 }
    Field { key: "city" }
    Field { key: "latitude"; numeric: true; low: -90; high: 90 }
    Field { key: "longitude"; numeric: true; low: -180; high: 180 }
    Field { key: "timezone" }
  }
  Group { key: "calculation" }
  Column {
    width: parent.width
    visible: form.section === "calculation"
    spacing: Style.space(8)
    Choice { key: "method"; fallback: "unselected"; choices: ["morocco", "mwl", "isna", "egypt", "karachi", "ummalqura", "custom"] }
    Choice { key: "asrFactor"; fallback: "1"; choices: ["1", "2"] }
    Choice { key: "highLatitude"; fallback: "none"; choices: ["none", "middle", "seventh", "angle"] }
    Column {
      width: parent.width
      spacing: Style.space(6)
      visible: form.value("method", form.host.view.method || "morocco") === "custom"
      Field { key: "fajrAngle"; fallback: "19"; numeric: true; low: 5; high: 25 }
      Field { key: "ishaAngle"; fallback: "17"; numeric: true; low: 5; high: 25 }
    }
    PlainText { width: parent.width; text: form.t("settings.adjust"); wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption; opacity: .7 }
    Repeater {
      model: ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]
      Field {
        required property string modelData
        key: ""
        label: form.t("prayer." + modelData)
        initialValue: form.value("adjust", {})[modelData] || 0
        numeric: true; low: -60; high: 60
        onCommitted: function(value) { form.adjust(modelData, Math.round(value)) }
      }
    }
    PlainText { width: parent.width; text: form.t("settings.computed"); wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption; opacity: .7 }
  }
  Group { key: "reminders" }
  Column {
    width: parent.width
    visible: form.section === "reminders"
    spacing: Style.space(6)
    Toggle { key: "notify"; fallback: true }
    Toggle { key: "advance" }
    Field { visible: form.value("advance", false); key: "advanceMinutes"; fallback: "10"; numeric: true; low: 1; high: 60 }
    Repeater {
      model: ["fajr", "dhuhr", "asr", "maghrib", "isha"]
      Action {
        required property string modelData
        readonly property bool muted: form.value("muted", []).indexOf(modelData) >= 0
        text: form.t("prayer." + modelData) + " · " + form.t(muted ? "off" : "on")
        onClicked: {
          var list = form.value("muted", []).slice()
          if (muted) list.splice(list.indexOf(modelData), 1)
          else list.push(modelData)
          form.save("muted", list)
        }
      }
    }
    PlainText { width: parent.width; text: form.t("settings.quiet"); wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption; opacity: .7 }
  }
  Group { key: "audio" }
  Column {
    width: parent.width
    visible: form.section === "audio"
    spacing: Style.space(6)
    Choice { key: "sound"; fallback: "off"; choices: ["off", "chime", "file"] }
    Field { visible: form.value("sound", "off") === "file"; key: "audioFile" }
    Field { visible: form.value("sound", "off") !== "off"; key: "volume"; fallback: "50"; numeric: true; low: 0; high: 100 }
    Action { visible: form.value("sound", "off") !== "off"; text: form.t(form.host.view.playing ? "audio.stop" : "audio.preview"); onClicked: if (form.host.service) { if (form.host.view.playing) form.host.service.stop(); else form.host.service.preview() } }
  }
  Group { key: "display" }
  Column {
    width: parent.width
    visible: form.section === "display"
    spacing: Style.space(6)
    Toggle { key: "showLabel"; fallback: true }
    Action { text: form.t("settings.hour24") + " · " + form.t(form.host.hour24 ? "on" : "off"); onClicked: form.save("hour24", !form.host.hour24) }
    Toggle { key: "fasting" }
    Toggle { key: "hijri"; fallback: true }
    Choice { visible: form.value("hijri", true); key: "hijriSource"; fallback: "auto"; choices: ["auto", "habous", "off"] }
    PlainText { width: parent.width; text: form.t("settings.hijriNote"); wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption; opacity: .7 }
  }
}
