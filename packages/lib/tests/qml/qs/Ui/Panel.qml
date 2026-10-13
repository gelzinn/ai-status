import QtQuick
Item {
    property string moduleName
    property bool manageIpc
    property var bar: null
    property color barForeground: "#eeeeee"
    property bool opened: false
    property bool popoutSwitchClosing: false
    function open() { opened = true }
    function close() { opened = false }
    function toggle() { opened = !opened }
}
