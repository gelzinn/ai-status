import QtQuick
Item {
    property string moduleName
    property bool manageIpc
    property var bar: null
    property color barForeground: "#eeeeee"
    property bool opened: false
    function open() { opened = true }
    function close() { opened = false }
    function toggle() { opened = !opened }
}
