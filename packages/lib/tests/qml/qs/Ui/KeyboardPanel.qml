import QtQuick
import qs.Commons
Rectangle {
    property var anchorItem
    property var owner
    property var bar
    property bool open
    property var focusTarget
    property real contentWidth
    property real contentHeight
    property real padding: 16
    // Match Omarchy: panel content accepts visual items only.
    default property alias contentItem: holder.children
    width: contentWidth
    height: contentHeight
    color: "#111111"
    radius: Style.cornerRadius
    border.color: Color.popups.border
    function fittedContentWidth(value) { return value }
    function fittedContentHeight(value, cap) { return Math.min(value + 32, cap) }
    onOpenChanged: if (open && focusTarget) focusTarget.forceActiveFocus()
    Item { id: holder; anchors.fill: parent; anchors.margins: padding }
}
