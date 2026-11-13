import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons

Item {
  id: root
  property var shell: null
  property var state: ({ rows: [], error: "", ready: false })
  property var cities: []
  property var currentSettings: ({})
  property string language: "en"
  property bool configured: false
  readonly property bool running: worker.running
  readonly property string backendPath: Qt.resolvedUrl("backend.py").toString().replace(/^file:\/\//, "")

  function send(message) {
    if (worker.running) worker.write(JSON.stringify(message) + "\n")
  }
  function configure(settings, locale) {
    var changed = JSON.stringify(currentSettings) !== JSON.stringify(settings) || language !== locale
    currentSettings = settings
    language = locale
    if (!configured || changed) {
      configured = true
      send({ command: "configure", settings: currentSettings, language: language })
    }
  }
  function day(offset) { send({ command: "day", offset: offset }) }
  function preview() { send({ command: "preview" }) }
  function stop() { send({ command: "stop" }) }

  Process {
    id: worker
    command: ["python3", "-u", decodeURIComponent(root.backendPath)]
    stdinEnabled: true
    running: true
    onStarted: if (root.configured) root.send({ command: "configure", settings: root.currentSettings, language: root.language })
    stdout: SplitParser {
      onRead: function(line) {
        try {
          var message = JSON.parse(line)
          if (message.type === "cities") root.cities = message.cities
          else if (message.type === "state") root.state = message.state
        } catch (e) { console.warn("Prayer Times: invalid worker response") }
      }
    }
    stderr: SplitParser { onRead: function(line) { console.warn("Prayer Times: " + line) } }
    onExited: {
      root.state = Object.assign({}, root.state, { ready: false, error: "backend" })
      retry.restart()
    }
  }
  Timer { id: retry; interval: 5000; onTriggered: worker.running = true }
  ShellIpc {
    target: "io.github.hassanaitnacer.prayer-times.audio"
    function stop(): string { root.stop(); return "ok" }
  }
}
