import QtQuick
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "io.github.hassanaitnacer.prayer-times"
  ipcTarget: "io.github.hassanaitnacer.prayer-times"
  Commons.Translations { id: translations; directory: Qt.resolvedUrl("i18n") }

  readonly property var service: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
  readonly property var view: service ? service.state : ({ rows: [], ready: false })
  readonly property bool setupComplete: setting("setupComplete", false) === true && view.setupComplete === true
  readonly property var next: setupComplete ? view.next || null : null
  readonly property var formatLocale: Qt.locale(Commons.I18n.formatLocale)
  readonly property bool hour24: typeof setting("hour24", null) === "boolean" ? setting("hour24", true) : Model.usesTwentyFourHour(formatLocale.timeFormat(Locale.ShortFormat))
  readonly property bool notify: setupComplete && setting("notify", true) !== false
  readonly property color foreground: bar ? bar.foreground : Commons.Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property string glyph: "󱠧"
  property double nowMs: Date.now()
  property bool settingsOpen: false
  property bool choosingCity: false
  property string cityQuery: ""
  property var pendingCity: null
  property string pendingMethod: "mwl"
  property string localError: ""
  readonly property int dayOffset: view.offset || 0
  readonly property bool labelShown: setting("showLabel", true) && !!next && !(bar && bar.vertical)
  readonly property Item activeButton: labelShown ? labelButton : iconButton
  readonly property real openPanelIndicatorWidth: labelShown ? labelButton.labelWidth : 0
  readonly property var cityMatches: {
    if (!service || !choosingCity) return []
    var query = cityQuery.trim().toLowerCase()
    return service.cities.filter(function(c) { return (c.city + " " + c.timezone).toLowerCase().indexOf(query) >= 0 }).slice(0, 8)
  }

  function safe(value) { return Model.safeShared(value) }
  function sync() {
    if (!service) return
    var s = Object.assign({}, settings, { hour24: hour24 })
    service.configure(s, Commons.I18n.formatLocale)
  }
  function persistMany(entry) {
    if (JSON.stringify(entry) === JSON.stringify(settings)) { localError = ""; return }
    if (!bar || !bar.shell || !bar.shell.updateEntryInline(moduleName, entry)) {
      localError = "save"
      return
    }
    localError = ""
    root.settings = entry
    sync()
  }
  function persistSetting(key, value) {
    var entry = Object.assign({}, settings)
    entry[key] = value
    persistMany(entry)
  }
  function confirmSetup() {
    var entry = Object.assign({}, settings, { setupComplete: true })
    persistMany(entry)
  }
  function chooseMethod(method) {
    var entry = Object.assign({}, settings, { method: method })
    if (method !== "custom") { delete entry.fajrAngle; delete entry.ishaAngle }
    persistMany(entry)
  }
  function suggest(city) {
    pendingCity = city
    var zone = city.timezone
    pendingMethod = zone === "Africa/Casablanca" || zone === "Africa/El_Aaiun" ? "morocco"
      : zone === "Africa/Cairo" ? "egypt" : zone === "Asia/Riyadh" ? "ummalqura"
      : zone === "Asia/Karachi" ? "karachi" : zone.indexOf("America/") === 0 ? "isna" : "mwl"
  }
  function acceptCity() {
    if (!pendingCity) return
    var entry = Object.assign({}, settings, pendingCity, { method: pendingMethod })
    delete entry.fajrAngle; delete entry.ishaAngle
    persistMany(entry)
    pendingCity = null; choosingCity = false; cityQuery = ""
    if (service) service.day(0)
  }
  function timeText(row) {
    if (!row || row.time === null || row.hour === null || row.hour === undefined) return "—"
    // A synthetic local date only formats the already-converted civil hour.
    var d = new Date(2000, 0, 15, row.hour, row.minute)
    return d.toLocaleTimeString(formatLocale, hour24 ? "HH:mm" : "h:mm AP")
  }
  function countdown(seconds) {
    if (seconds === null || seconds === undefined) return "—"
    var left = Model.countdown(seconds * 1000, nowMs)
    if (left.hours === 0 && left.minutes === 0) return translations.t("countdown.now")
    if (left.hours === 0) return translations.t("countdown.minutes").arg(Commons.I18n.formatNumber(left.minutes))
    return translations.t("countdown.hoursMinutes").arg(Commons.I18n.formatNumber(left.hours)).arg(Commons.I18n.formatNumber(left.minutes))
  }
  function shiftDay(delta) { if (service) service.day(Math.max(-366, Math.min(366, dayOffset + delta))) }
  function ensureVisible(item) { if (panel.loadedContent) panel.loadedContent.ensureVisible(item) }
  function dismissLayer() {
    if (pendingCity) pendingCity = null
    else if (choosingCity) choosingCity = false
    else if (settingsOpen) settingsOpen = false
    else if (dayOffset !== 0 && service) service.day(0)
    else root.close()
  }
  onServiceChanged: Qt.callLater(sync)
  onSettingsChanged: Qt.callLater(sync)
  onHour24Changed: Qt.callLater(sync)
  Connections { target: Commons.I18n; function onFormatLocaleChanged() { root.sync() } }
  Component.onCompleted: Qt.callLater(sync)
  onViewChanged: {
    nowMs = Date.now()
    if (view.setupComplete && setting("timezone", null) === null) persistSetting("timezone", view.timezone)
  }
  onOpenedChanged: {
    nowMs = Date.now()
    if (opened && service) service.day(0)
    if (!opened) { choosingCity = false; pendingCity = null; settingsOpen = false }
  }
  Timer {
    running: true; repeat: true; interval: 60000
    Component.onCompleted: interval = Math.max(100, 60000 - Date.now() % 60000)
    onTriggered: { root.nowMs = Date.now(); interval = Math.max(100, 60000 - Date.now() % 60000) }
  }

  implicitWidth: activeButton.implicitWidth
  implicitHeight: activeButton.implicitHeight
  WidgetButton {
    id: labelButton
    anchors.fill: parent
    visible: root.labelShown
    bar: root.bar
    text: root.next ? translations.t("bar.label").arg(translations.t("prayer." + root.next.name)).arg(root.timeText(root.next)) : ""
    horizontalMargin: 8.75; verticalPadding: 8.75
    tooltipText: translations.t("title")
    pressFeedbackButtons: Qt.NoButton
    onPressed: function(b) { if (b === Qt.RightButton) root.persistSetting("showLabel", false); else root.toggle() }
  }
  BarIconButton {
    id: iconButton
    anchors.fill: parent
    visible: !root.labelShown
    bar: root.bar
    text: root.glyph
    tooltipText: translations.t("title")
    onPressed: function(b) { if (b === Qt.RightButton) root.persistSetting("showLabel", true); else root.toggle() }
  }

  component Action: Button {
    focusable: true
    fontSize: Style.font.bodySmall
    onActiveFocusChanged: if (activeFocus) root.ensureVisible(this)
  }
  KeyboardPanel {
    id: panel
    anchorItem: root.activeButton
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: panel.loadedContent
    contentWidth: panel.fittedContentWidth(Style.space(340))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight, Style.space(680))
    content: FocusScope {
      id: content
      anchors.fill: parent
      implicitHeight: column.implicitHeight
      focus: true
      function ensureVisible(item) {
        var p = item.mapToItem(column, 0, 0)
        if (p.y < scroll.contentY) scroll.contentY = p.y
        else if (p.y + item.height > scroll.contentY + scroll.height) scroll.contentY = Math.max(0, p.y + item.height - scroll.height)
      }
      Keys.onEscapePressed: root.dismissLayer()
      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
          if (!root.settingsOpen && !root.choosingCity) {
            var dir = event.key === Qt.Key_Right ? 1 : -1
            root.shiftDay(Commons.I18n.rightToLeft ? -dir : dir); event.accepted = true
          }
        } else if (!root.settingsOpen && !root.choosingCity) {
          var key = event.text.toLowerCase()
          if (key === "n") { root.persistSetting("notify", !root.notify); event.accepted = true }
          else if (key === "f") { root.persistSetting("fasting", !root.setting("fasting", false)); event.accepted = true }
          else if (key === "s") { root.settingsOpen = true; event.accepted = true }
          else if (key === "t") { root.persistSetting("hour24", !root.hour24); event.accepted = true }
        }
      }
      Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        onContentHeightChanged: contentY = Math.min(contentY, Math.max(0, contentHeight - height))
        Column {
          id: column
          width: scroll.width
          spacing: Style.space(10)
          Action {
            width: parent.width
            text: root.safe(root.setting("city", "") || translations.t("city.choose")) + "  ⌄"
            foreground: root.dim
            onClicked: { root.choosingCity = !root.choosingCity; root.pendingCity = null }
          }
          Column {
            visible: !root.setupComplete
            width: parent.width
            spacing: Style.space(6)
            PlainText { width: parent.width; text: translations.t("setup.intro"); wrapMode: Text.WordWrap }
            Action {
              width: parent.width; text: translations.t("setup.review")
              onClicked: { root.settingsOpen = true; settingsForm.section = "location" }
            }
            PlainText {
              width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption
              text: translations.t("setup.summary").arg(root.setting("latitude", "—")).arg(root.setting("longitude", "—")).arg(root.safe(root.setting("timezone", "—"))).arg(translations.t("option." + root.setting("method", "unselected")))
            }
            Action { objectName: "confirmSetup"; width: parent.width; text: translations.t("setup.confirm"); bordered: true; onClicked: root.confirmSetup() }
          }
          Column {
            visible: root.choosingCity
            width: parent.width
            spacing: Style.space(6)
            PlainText { width: parent.width; text: translations.t("city.offline"); font.pixelSize: Style.font.caption; opacity: .65; wrapMode: Text.WordWrap }
            TextField {
              id: search
              width: parent.width
              placeholderText: translations.t("city.search")
              maximumLength: 80
              onTextChanged: root.cityQuery = text
              onVisibleChanged: if (visible) Qt.callLater(function() { search.forceActiveFocus() })
              onAccepted: if (root.cityMatches.length) root.suggest(root.cityMatches[0])
            }
            Column {
              width: parent.width
              visible: !root.pendingCity
              Repeater {
                model: root.cityMatches
                Action {
                  required property var modelData
                  width: parent.width
                  text: root.safe(modelData.city + " · " + modelData.timezone)
                  leftAlign: true
                  onClicked: root.suggest(modelData)
                }
              }
              PlainText { visible: root.cityMatches.length === 0; width: parent.width; text: translations.t("city.noMatch"); wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption }
            }
            Column {
              width: parent.width
              visible: !!root.pendingCity
              spacing: Style.space(6)
              PlainText { width: parent.width; text: root.pendingCity ? root.pendingCity.city + " · " + root.pendingCity.timezone : ""; wrapMode: Text.WordWrap }
              PlainText { width: parent.width; text: translations.t("city.profile"); wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption; opacity: .7 }
              Action {
                width: parent.width
                text: translations.t("option." + root.pendingMethod) + "  ↻"
                onClicked: { var methods = ["morocco", "mwl", "isna", "egypt", "karachi", "ummalqura", "custom"]; root.pendingMethod = methods[(methods.indexOf(root.pendingMethod) + 1) % methods.length] }
              }
              Action { width: parent.width; text: translations.t("city.use"); bordered: true; onClicked: root.acceptCity() }
            }
            Action { width: parent.width; text: translations.t("city.manual"); onClicked: { root.choosingCity = false; root.settingsOpen = true; settingsForm.section = "location" } }
            PanelSeparator { foreground: root.foreground }
          }

          Column {
            visible: root.setupComplete
            width: parent.width
            spacing: Style.space(3)
            PlainText { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: translations.t("next"); font.pixelSize: Style.font.caption; color: root.dim }
            PlainText {
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              text: root.next ? (root.next.estimated ? "≈ " : "") + translations.t("prayer." + root.next.name) + "  " + root.timeText(root.next) : translations.t(root.view.ready ? "unavailable" : "loading")
              font.pixelSize: Style.font.title; font.bold: true
              wrapMode: Text.WordWrap
            }
            PlainText {
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              text: root.next ? root.countdown(root.next.time) + (root.next.date !== root.view.today ? " · " + translations.t("tomorrow") : "") : ""
              color: Commons.Color.accent
              font.pixelSize: Style.font.bodySmall
            }
            PlainText {
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              visible: !!root.view.fajrEnd
              text: root.view.fajrEnd ? translations.t("fajr.ends").arg(root.countdown(root.view.fajrEnd)) : ""
              font.pixelSize: Style.font.caption; color: root.dim
            }
            PlainText {
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              visible: !!root.view.previous && !root.view.fajrEnd
              text: root.view.previous ? translations.t("prayer.started").arg(translations.t("prayer." + root.view.previous.name)).arg(root.timeText(root.view.previous)) : ""
              font.pixelSize: Style.font.caption; color: root.dim
            }
          }
          PlainText {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            visible: root.setupComplete && root.setting("fasting", false)
            text: root.view.fasting ? (root.view.fasting.estimated ? "≈ " : "") + translations.t("fasting." + root.view.fasting.name).arg(root.countdown(root.view.fasting.time)) : translations.t("fasting.unavailable")
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.WordWrap
          }
          PanelSeparator { foreground: root.foreground }
          Row {
            width: parent.width
            Action { width: Style.space(32); text: Commons.I18n.rightToLeft ? "›" : "‹"; tooltipText: translations.t("day.previous"); onClicked: root.shiftDay(-1) }
            Action {
              width: parent.width - Style.space(64)
              text: root.view.date ? new Date(root.view.year, root.view.month - 1, root.view.day).toLocaleDateString(root.formatLocale, "ddd, d MMM") : "—"
              tooltipText: translations.t("day.today")
              onClicked: if (root.service) root.service.day(0)
            }
            Action { width: Style.space(32); text: Commons.I18n.rightToLeft ? "‹" : "›"; tooltipText: translations.t("day.next"); onClicked: root.shiftDay(1) }
          }
          PlainText {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            visible: root.setupComplete && root.setting("hijri", true) && !!root.view.hijri
            text: root.view.hijri ? translations.t("hijri.date").arg(Commons.I18n.formatNumber(root.view.hijri.day)).arg(translations.t("hijri.month." + root.view.hijri.month)).arg(Commons.I18n.formatNumber(root.view.hijri.year)) : ""
            font.pixelSize: Style.font.caption; color: root.dim
            wrapMode: Text.WordWrap
          }
          PlainText {
            visible: root.setupComplete && root.setting("hijri", true)
            width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
            text: translations.t("hijri." + (root.view.hijriSync ? root.view.hijriSync.status : "unverified"))
            font.pixelSize: Style.font.caption; color: root.dim
          }
          Column {
            width: parent.width
            spacing: Style.space(3)
            Repeater {
              model: root.setupComplete ? root.view.rows || [] : []
              Rectangle {
                id: prayerRow
                required property var modelData
                readonly property bool sunrise: modelData.name === "sunrise"
                readonly property bool isNext: !!root.next && modelData.time === root.next.time
                width: parent.width
                height: Style.space(sunrise ? 25 : 38)
                radius: Style.cornerRadius
                color: isNext ? Style.selectedFill : (sunrise ? "transparent" : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, .035))
                PlainText {
                  anchors.left: parent.left; anchors.leftMargin: Style.space(10); anchors.verticalCenter: parent.verticalCenter
                  text: translations.t("prayer." + prayerRow.modelData.name)
                  font.pixelSize: prayerRow.sunrise ? Style.font.caption : Style.font.body
                  font.bold: prayerRow.isNext
                  opacity: prayerRow.sunrise ? .6 : 1
                }
                PlainText {
                  anchors.right: parent.right; anchors.rightMargin: Style.space(10); anchors.verticalCenter: parent.verticalCenter
                  text: (prayerRow.modelData.estimated ? "≈ " : "") + root.timeText(prayerRow.modelData)
                  font.pixelSize: prayerRow.sunrise ? Style.font.caption : Style.font.body
                  font.bold: prayerRow.isNext
                  opacity: prayerRow.sunrise ? .6 : 1
                }
                MouseArea { anchors.fill: parent; onClicked: root.persistSetting("hour24", !root.hour24) }
              }
            }
          }
          PlainText { visible: root.setupComplete && (!!root.view.estimated || !!root.view.unavailable || !!(root.next && root.next.estimated)); width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption; color: root.dim; text: translations.t(root.view.unavailable ? "times.unavailable" : "times.estimated") }
          Row {
            width: parent.width
            Action { enabled: root.setupComplete; width: parent.width / 2; text: translations.t(root.notify ? "notify.on" : "notify.off"); onClicked: root.persistSetting("notify", !root.notify) }
            Action { width: parent.width / 2; text: translations.t("settings.title") + (root.settingsOpen ? " −" : " +"); onClicked: root.settingsOpen = !root.settingsOpen }
          }
          Action { visible: !!root.view.playing; width: parent.width; text: translations.t("audio.stop"); bordered: true; onClicked: if (root.service) root.service.stop() }
          PlainText {
            visible: root.localError !== "" || !!root.view.error
            width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption
            text: translations.t("error." + (root.localError || root.view.error || ""))
          }
          Settings { id: settingsForm; objectName: "prayerSettings"; width: parent.width; visible: root.settingsOpen; host: root; strings: translations }
          PlainText {
            visible: root.setupComplete
            width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
            text: translations.t("source").arg(translations.t("option." + (root.view.method || "morocco"))).arg(root.view.timezone || "Africa/Casablanca")
            font.pixelSize: Style.font.caption; color: root.dim
          }
        }
      }
    }
  }
}
