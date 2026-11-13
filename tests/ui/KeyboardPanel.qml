// Test-only offscreen window adapter. Production uses Omarchy KeyboardPanel.
import QtQuick
import QtQuick.Window
import Quickshell
import qs.Commons
import qs.Commons as Commons
Window {
  id: root
  property Item anchorItem
  property QtObject bar
  property var owner
  property bool open: false
  property Item focusTarget
  property int contentWidth: 340
  property int contentHeight: 600
  property Component content
  readonly property Item loadedContent: loader.item
  readonly property real loadedContentHeight: loader.item ? loader.item.implicitHeight : 0
  function fittedContentWidth(value) { return value }
  function fittedContentHeight(value, cap) { return Math.min(value + 40, cap || 800) }
  width: contentWidth
  height: contentHeight
  color: Commons.Color.popups.background
  visible: true
  Rectangle { anchors.fill: parent; color: Commons.Color.popups.background }
  Loader { id: loader; LayoutMirroring.enabled: Commons.I18n.rightToLeft; LayoutMirroring.childrenInherit: true; anchors.fill: parent; anchors.margins: 20; sourceComponent: root.content }
  function find(item, key, value) {
    if (item[key] === value) return item
    var kids = item.children || []
    for (var i = 0; i < kids.length; i++) { var found = find(kids[i], key, value); if (found) return found }
    return null
  }
  Timer { running: true; interval: 600; onTriggered: {
    var mode = Quickshell.env("PRAYER_QA_MODE")
    if (mode === "settings") {
      root.owner.settingsOpen = true
      var form = root.find(loader.item, "objectName", "prayerSettings")
      form.section = "calculation"
      root.find(form, "key", "method").expanded = true
      root.owner.persistSetting("highLatitude", "middle")
      root.owner.chooseMethod("mwl")
    } else if (mode === "city") {
      root.owner.choosingCity = true
      root.owner.cityQuery = "Tokyo"
    } else if (mode === "fasting") root.owner.persistSetting("fasting", true)
    else if (mode === "setup-confirm") {
      root.owner.persistMany({ notify:false, hijriSource:"off", city:"Tokyo", latitude:35.68, longitude:139.69, timezone:"Asia/Tokyo", method:"mwl" })
      root.find(loader.item, "objectName", "confirmSetup").clicked()
    }
  } }
  Timer { running: true; interval: 1400; onTriggered: { console.log("SIZE", root.width, root.height, root.visible, root.contentWidth, root.contentHeight, loader.width, loader.height); root.show(); root.contentItem.width = root.width; root.contentItem.height = root.height; root.contentItem.grabToImage(function(result) { result.saveToFile(Quickshell.env("PRAYER_QA_OUTPUT") + "/preview-" + (Quickshell.env("PRAYER_QA_MODE") || "base") + ".png") }) } }
}
