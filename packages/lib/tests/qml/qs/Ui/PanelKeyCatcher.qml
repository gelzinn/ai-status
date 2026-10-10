import QtQuick
FocusScope {
    signal closeRequested()
    signal tabRequested(int direction)
    signal moveRequested(int dx, int dy)
    signal textKey(string text, int modifiers)
    Keys.onEscapePressed: closeRequested()
    Keys.onTabPressed: tabRequested(1)
    Keys.onBacktabPressed: tabRequested(-1)
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Up || event.key === Qt.Key_Down) {
            moveRequested(0, event.key === Qt.Key_Up ? -1 : 1)
            event.accepted = true
        } else if (event.text) {
            textKey(event.text.toLowerCase(), event.modifiers)
            event.accepted = true
        }
    }
}
