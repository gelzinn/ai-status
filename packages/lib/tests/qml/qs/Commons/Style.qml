pragma Singleton
import QtQuick
QtObject {
    readonly property var font: ({family: "monospace", body: 13, caption: 12})
    function space(value) { return value }
    function duration(value) { return value }
}
