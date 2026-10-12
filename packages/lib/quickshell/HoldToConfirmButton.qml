import QtQuick
import QtQuick.Window
import qs.Commons
import qs.Commons as Commons

Rectangle {
    id: root
    property string text: "Hold to apply · 3s"
    property string fontFamily: Style.font.family
    property color foreground: "white"
    readonly property int holdDuration: 3000
    property real progress: 0
    property string holdSource: ""
    property int holdKey: 0
    property bool completed: false
    readonly property bool holding: holdSource !== ""
    signal confirmed()

    implicitWidth: label.implicitWidth + Style.space(20)
    implicitHeight: Style.space(30)
    radius: Style.cornerRadius
    color: Qt.rgba(Commons.Color.accent.r, Commons.Color.accent.g, Commons.Color.accent.b, 0.12)
    border.width: 1
    border.color: Qt.rgba(Commons.Color.accent.r, Commons.Color.accent.g, Commons.Color.accent.b, activeFocus ? 0.65 : 0.3)
    opacity: enabled ? 1 : 0.35
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.description: "Press and hold the mouse button, Space, or Enter continuously for 3 seconds. Release to cancel."
    // Accessibility activation only focuses the control; it cannot bypass the hold.
    Accessible.onPressAction: if (enabled && visible) forceActiveFocus(Qt.OtherFocusReason)
    onEnabledChanged: if (!enabled) cancelHold()
    onVisibleChanged: if (!visible) cancelHold()
    onActiveFocusChanged: if (!activeFocus) cancelHold()

    function beginHold(source, key) {
        if (!enabled || !visible || !activeFocus || holding || completed
            || (Window.window && !Window.window.active)) return
        holdSource = source
        holdKey = key || 0
        progress = 0
        fillAnimation.start()
    }

    function cancelHold() {
        fillAnimation.stop()
        holdSource = ""
        holdKey = 0
        completed = false
        progress = 0
    }

    Keys.onPressed: event => {
        if (event.key !== Qt.Key_Space && event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter) return
        event.accepted = true
        if (!event.isAutoRepeat) beginHold("keyboard", event.key)
    }
    Keys.onReleased: event => {
        if (event.key !== Qt.Key_Space && event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter) return
        event.accepted = true
        if (!event.isAutoRepeat && holdSource === "keyboard" && event.key === holdKey) cancelHold()
    }
    Keys.onTabPressed: {
        cancelHold()
        nextItemInFocusChain(true).forceActiveFocus(Qt.TabFocusReason)
    }
    Keys.onBacktabPressed: {
        cancelHold()
        nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
    }

    Connections {
        target: root.Window.window
        function onActiveChanged() { if (!root.Window.window.active) root.cancelHold() }
    }
    NumberAnimation {
        id: fillAnimation
        target: root
        property: "progress"
        from: 0
        to: 1
        duration: root.holdDuration
        easing.type: Easing.Linear
        onFinished: {
            if (!root.holding || !root.enabled || !root.visible || !root.activeFocus
                || (root.Window.window && !root.Window.window.active)
                || (root.holdSource === "mouse" && (!mouse.pressed || !mouse.containsMouse))) {
                root.cancelHold()
                return
            }
            root.completed = true
            root.confirmed()
        }
    }
    Item {
        anchors.fill: parent
        clip: true
        // Clip a full rounded background to keep the fill's leading edge straight.
        Item {
            objectName: "hold-confirm-fill"
            width: root.width * root.progress
            height: root.height
            clip: true
            Rectangle {
                width: root.width
                height: root.height
                radius: root.radius
                color: Commons.Color.accent
            }
        }
    }
    Text {
        id: label
        anchors.fill: parent
        anchors.leftMargin: Style.space(10)
        anchors.rightMargin: Style.space(10)
        text: root.text
        textFormat: Text.PlainText
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        color: root.foreground
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    // Render the same label over the filled area with the primary-button text color.
    Item {
        width: root.width * root.progress
        height: root.height
        clip: true
        Text {
            width: root.width
            height: root.height
            leftPadding: Style.space(10)
            rightPadding: Style.space(10)
            text: root.text
            textFormat: Text.PlainText
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            color: Commons.Color.popups.background
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onPressed: {
            root.forceActiveFocus(Qt.MouseFocusReason)
            root.beginHold("mouse", 0)
        }
        onReleased: if (root.holdSource === "mouse") root.cancelHold()
        onCanceled: root.cancelHold()
        onExited: if (root.holdSource === "mouse") root.cancelHold()
    }
}
