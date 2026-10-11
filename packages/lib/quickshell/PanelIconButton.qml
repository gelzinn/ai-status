import QtQuick
import QtQuick.Templates as T
import qs.Commons
import "." as Plugin

T.Control {
    id: root
    property var bar: null
    property var registeredBar: null
    property string iconName: ""
    property string tooltipText: ""
    property color foreground: "white"
    property bool spinning: false
    property bool focusOutlineSuppressed: false
    readonly property bool interactive: enabled
    readonly property bool tooltipHovered: visible && enabled && mouse.containsMouse
    readonly property bool keyboardFocusVisible: activeFocus && enabled && !focusOutlineSuppressed && (focusReason === Qt.TabFocusReason || focusReason === Qt.BacktabFocusReason)
    readonly property color iconForeground: keyboardFocusVisible ? Qt.lighter(foreground, 1.35) : foreground
    property alias color: backgroundRectangle.color
    property alias radius: backgroundRectangle.radius
    property alias border: backgroundRectangle.border
    signal pressed(int button)

    implicitWidth: Style.space(Plugin.PanelIcons.data.controls.size)
    implicitHeight: implicitWidth
    background: Rectangle {
        id: backgroundRectangle
        radius: Style.space(Plugin.PanelIcons.data.controls.radius)
        color: root.tooltipHovered ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, Plugin.PanelIcons.data.controls.hoverOpacity) : "transparent"
        border.width: root.keyboardFocusVisible ? 1 : 0
        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, Plugin.PanelIcons.data.controls.focusOpacity)
    }
    opacity: enabled ? 1 : 0.35
    activeFocusOnTab: true

    // Preserve the host's tooltip and click-target contract while owning the
    // control's drawing and keyboard behavior.
    function hideOwnTooltip() {
        if (bar && typeof bar.hideTooltip === "function") bar.hideTooltip(root)
    }
    function triggerPress(button) {
        if (!enabled) return
        hideOwnTooltip()
        pressed(button)
    }
    function focusProgrammatically() {
        focusOutlineSuppressed = true
        forceActiveFocus(Qt.OtherFocusReason)
    }
    function focusFromKeyboard(reason) {
        focusOutlineSuppressed = false
        forceActiveFocus(reason)
    }
    function focusNext(forward) {
        const target = nextItemInFocusChain(forward)
        const reason = forward ? Qt.TabFocusReason : Qt.BacktabFocusReason
        if (typeof target.focusFromKeyboard === "function") target.focusFromKeyboard(reason)
        else target.forceActiveFocus(reason)
    }
    function syncClickRegistration() {
        if (registeredBar && typeof registeredBar.unregisterClickTarget === "function")
            registeredBar.unregisterClickTarget(root)
        registeredBar = bar
        if (registeredBar && typeof registeredBar.registerClickTarget === "function")
            registeredBar.registerClickTarget(root)
    }
    onBarChanged: syncClickRegistration()
    onVisibleChanged: if (!visible) hideOwnTooltip()
    onEnabledChanged: if (!enabled) hideOwnTooltip()
    onActiveFocusChanged: if (!activeFocus) focusOutlineSuppressed = false
    Component.onCompleted: syncClickRegistration()
    Component.onDestruction: {
        hideOwnTooltip()
        if (registeredBar && typeof registeredBar.unregisterClickTarget === "function")
            registeredBar.unregisterClickTarget(root)
    }

    Accessible.role: Accessible.Button
    Accessible.name: tooltipText
    Accessible.onPressAction: triggerPress(Qt.LeftButton)
    Keys.onReturnPressed: triggerPress(Qt.LeftButton)
    Keys.onEnterPressed: triggerPress(Qt.LeftButton)
    Keys.onSpacePressed: triggerPress(Qt.LeftButton)
    Keys.onTabPressed: focusNext(true)
    Keys.onBacktabPressed: focusNext(false)

    Plugin.PanelIcon {
        id: icon
        objectName: root.objectName + "-icon"
        anchors.centerIn: parent
        width: Style.space(Plugin.PanelIcons.data.size)
        height: width
        name: root.iconName
        foreground: root.iconForeground
        NumberAnimation on rotation {
            from: 0
            to: 360
            duration: 1000
            loops: Animation.Infinite
            running: root.spinning && root.visible
            onRunningChanged: if (!running) icon.rotation = 0
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        // Qt retains focusReason when an already-focused item is clicked.
        onPressed: root.focusOutlineSuppressed = true
        onEntered: {
            if (root.bar && typeof root.bar.showTooltip === "function")
                root.bar.showTooltip(root, root.tooltipText)
        }
        onExited: root.hideOwnTooltip()
        onClicked: mouse => {
            root.forceActiveFocus(Qt.MouseFocusReason)
            root.triggerPress(mouse.button)
        }
    }
}
