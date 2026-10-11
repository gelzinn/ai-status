import QtQuick
import qs.Commons
import "." as Plugin

Rectangle {
    id: root
    property var bar: null
    property var registeredBar: null
    property string iconName: ""
    property string tooltipText: ""
    property color foreground: "white"
    property bool spinning: false
    readonly property bool interactive: enabled
    readonly property bool tooltipHovered: visible && enabled && mouse.containsMouse
    signal pressed(int button)

    implicitWidth: Style.space(Plugin.PanelIcons.data.controls.size)
    implicitHeight: implicitWidth
    radius: Style.space(Plugin.PanelIcons.data.controls.radius)
    color: tooltipHovered ? Qt.rgba(foreground.r, foreground.g, foreground.b, Plugin.PanelIcons.data.controls.hoverOpacity) : "transparent"
    border.width: activeFocus && enabled ? 1 : 0
    border.color: Qt.rgba(foreground.r, foreground.g, foreground.b, Plugin.PanelIcons.data.controls.focusOpacity)
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
    Keys.onTabPressed: nextItemInFocusChain(true).forceActiveFocus(Qt.TabFocusReason)
    Keys.onBacktabPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)

    Plugin.PanelIcon {
        id: icon
        objectName: root.objectName + "-icon"
        anchors.centerIn: parent
        width: Style.space(Plugin.PanelIcons.data.size)
        height: width
        name: root.iconName
        foreground: root.foreground
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
