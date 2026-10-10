import QtQuick
Rectangle {
    property var anchorItem
    property var owner
    property var bar
    property bool open
    property var focusTarget
    property real contentWidth
    property real contentHeight
    property real padding: 16
    default property alias contentData: holder.data
    width: contentWidth
    height: contentHeight
    color: "#111111"
    radius: 12
    border.color: "#282828"
    function fittedContentWidth(value) { return value }
    function fittedContentHeight(value, cap) { return Math.min(value + 32, cap) }
    onOpenChanged: if (open && focusTarget) focusTarget.forceActiveFocus()
    Item { id: holder; anchors.fill: parent; anchors.margins: padding }
}
