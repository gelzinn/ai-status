import QtQuick
import QtQuick.Templates as T
import qs.Commons

T.Slider {
    id: root
    property color foreground: "white"
    implicitWidth: Style.space(160)
    implicitHeight: Style.space(30)
    from: 1
    to: 100
    stepSize: 1
    snapMode: T.Slider.SnapAlways
    activeFocusOnTab: true
    Accessible.name: "Notification threshold"
    opacity: enabled ? 1 : 0.35
    background: Rectangle {
        x: root.leftPadding
        y: root.topPadding + (root.availableHeight - height) / 2
        width: root.availableWidth
        height: Style.space(4)
        radius: height / 2
        color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.2)
        Rectangle {
            width: root.visualPosition * parent.width
            height: parent.height
            radius: parent.radius
            color: Color.accent
        }
    }
    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + (root.availableHeight - height) / 2
        width: Style.space(16)
        height: width
        radius: width / 2
        color: root.foreground
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus ? Color.accent : Color.popups.background
    }
}
