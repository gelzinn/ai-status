pragma Singleton
import QtQuick
QtObject {
    property real cornerRadius: 0
    readonly property var font: ({family: "monospace", body: 13, caption: 12, icon: 16})
    readonly property var spacing: ({controlGap: 8})
    function space(value) { return value }
    function duration(value) { return value }
}
