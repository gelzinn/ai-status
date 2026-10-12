pragma Singleton
import QtQuick
QtObject {
    readonly property color urgent: "#d99865"
    readonly property color accent: "#aaaaaa"
    readonly property QtObject popups: QtObject { property color background: "#111111"; property color border: "#282828" }
}
