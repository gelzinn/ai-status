import QtQuick
Item {
    property bool running: false
    property var command: []
    property var stdout
    property var stderr
    signal exited(int exitCode, int exitStatus)
    function exec(arguments) { command = arguments; running = true }
}
