import QtQuick
import QtQuick.Shapes
import qs.Commons
import "." as Plugin
import "StableList.js" as StableList

Column {
    id: root
    property var provider: null
    property color foreground: "white"
    property string fontFamily: Style.font.family
    readonly property var inventory: provider && provider.resetCredits ? provider.resetCredits : ({available: 0, rows: [], undetailed: 0})
    spacing: Style.space(18)
    onInventoryChanged: StableList.sync(rows, inventory.rows, entry => entry.title + ":" + entry.expires + ":" + entry.count)
    Component.onCompleted: StableList.sync(rows, inventory.rows, entry => entry.title + ":" + entry.expires + ":" + entry.count)
    ListModel { id: rows; dynamicRoles: true }
    component Label: Text {
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        wrapMode: Text.WordWrap
    }
    component Secondary: Label {
        opacity: 0.5
        font.pixelSize: Style.font.caption
    }
    Item {
        objectName: "reset-provider-heading"
        width: parent.width
        height: Math.max(Style.space(24), providerLabel.implicitHeight)
        Image {
            objectName: "reset-provider-logo"
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Style.space(16)
            height: width
            source: root.provider ? root.provider.logoPath ? "file://" + root.provider.logoPath : Qt.resolvedUrl("../assets/providers/" + root.provider.id + ".png") : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }
        Label {
            id: providerLabel
            x: Style.space(24)
            width: Math.max(0, parent.width - x)
            anchors.verticalCenter: parent.verticalCenter
            text: root.provider ? root.provider.name : ""
        }
    }
    Secondary { width: parent.width; text: "Cached data"; visible: !!root.provider && root.provider.cached }
    Column {
        width: parent.width
        spacing: Style.space(8)
        Label { objectName: "reset-section-title"; text: "Usage limit resets"; font.bold: true }
        Label {
            objectName: "reset-explanation"
            width: parent.width
            opacity: 0.55
            text: root.provider && root.provider.id === "codex"
                ? "Restore your 5-hour or weekly limit,\nor both, depending on the reset type."
                : "Restore eligible usage limits.\nCredits expire on the dates below."
        }
    }
    Rectangle {
        id: resetTable
        objectName: "reset-table"
        width: parent.width
        implicitHeight: table.implicitHeight + 2
        color: "transparent"
        border.width: 1
        radius: Style.cornerRadius
        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.15)
        visible: root.inventory.available > 0
        Column {
            id: table
            x: 1
            y: 1
            width: parent.width - 2
            Item {
                id: columnHeader
                objectName: "reset-column-header"
                width: parent.width
                height: columnHeadings.implicitHeight + Style.space(18)
                readonly property color color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
                readonly property real radius: Math.max(0, resetTable.radius - 1)
                Shape {
                    anchors.fill: parent
                    antialiasing: true
                    layer.enabled: visible
                    layer.samples: 4
                    layer.smooth: true
                    ShapePath {
                        strokeColor: "transparent"
                        fillColor: columnHeader.color
                        startX: 0
                        startY: columnHeader.radius
                        PathLine { x: 0; y: columnHeader.height }
                        PathLine { x: columnHeader.width; y: columnHeader.height }
                        PathLine { x: columnHeader.width; y: columnHeader.radius }
                        PathQuad { x: columnHeader.width - columnHeader.radius; y: 0; controlX: columnHeader.width; controlY: 0 }
                        PathLine { x: columnHeader.radius; y: 0 }
                        PathQuad { x: 0; y: columnHeader.radius; controlX: 0; controlY: 0 }
                    }
                }
                Row {
                    id: columnHeadings
                    x: Style.space(12)
                    y: Style.space(10)
                    width: parent.width - x * 2
                    spacing: Style.space(12)
                    Secondary { objectName: "reset-type-header"; width: (parent.width - parent.spacing) / 2; text: "Reset type" }
                    Secondary { objectName: "reset-expires-header"; width: (parent.width - parent.spacing) / 2; text: "Expires" }
                }
            }
            Repeater {
                model: rows
                delegate: Item {
                    required property var entry
                    width: table.width
                    implicitHeight: Math.max(typeCell.implicitHeight, expiryCell.implicitHeight) + Style.space(24)
                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.09)
                    }
                    Column {
                        id: typeCell
                        x: Style.space(12)
                        y: Style.space(12)
                        width: (parent.width - Style.space(36)) / 2
                        spacing: Style.space(5)
                        Label { width: parent.width; text: entry.title }
                        Secondary { width: parent.width; text: entry.count + (entry.count === 1 ? " credit" : " credits") }
                    }
                    Column {
                        id: expiryCell
                        x: typeCell.x + typeCell.width + Style.space(12)
                        y: typeCell.y
                        width: typeCell.width
                        spacing: Style.space(5)
                        Label { width: parent.width; text: entry.expires }
                        Secondary { objectName: "reset-remaining"; width: parent.width; text: entry.remaining }
                    }
                }
            }
            Item {
                id: tableFooter
                objectName: "reset-table-footer"
                width: table.width
                implicitHeight: Math.max(availableLabel.implicitHeight, availableValue.implicitHeight) + Style.space(24) + 1
                readonly property color color: columnHeader.color
                readonly property real radius: columnHeader.radius
                Shape {
                    id: footerBackground
                    y: 1
                    width: parent.width
                    height: parent.height - 1
                    antialiasing: true
                    layer.enabled: visible
                    layer.samples: 4
                    layer.smooth: true
                    ShapePath {
                        strokeColor: "transparent"
                        fillColor: tableFooter.color
                        startX: 0
                        startY: 0
                        PathLine { x: footerBackground.width; y: 0 }
                        PathLine { x: footerBackground.width; y: footerBackground.height - tableFooter.radius }
                        PathQuad { x: footerBackground.width - tableFooter.radius; y: footerBackground.height; controlX: footerBackground.width; controlY: footerBackground.height }
                        PathLine { x: tableFooter.radius; y: footerBackground.height }
                        PathQuad { x: 0; y: footerBackground.height - tableFooter.radius; controlX: 0; controlY: footerBackground.height }
                        PathLine { x: 0; y: 0 }
                    }
                }
                Rectangle {
                    width: parent.width
                    height: 1
                    color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.09)
                }
                Row {
                    x: Style.space(12)
                    y: Style.space(12) + 1
                    width: parent.width - x * 2
                    spacing: Style.space(12)
                    Label {
                        id: availableLabel
                        objectName: "reset-available-label"
                        width: Math.max(0, parent.width - availableValue.implicitWidth - parent.spacing)
                        text: "Available resets"
                        opacity: 0.55
                    }
                    Label {
                        id: availableValue
                        objectName: "reset-available"
                        text: String(root.inventory.available)
                        font.weight: Font.Medium
                    }
                }
            }
        }
    }
    Secondary {
        objectName: "reset-timezone"
        width: parent.width
        text: root.inventory.timezone || ""
        visible: text.length > 0 && root.inventory.available > 0
    }
    Label { width: parent.width; text: "No reset credits available."; visible: root.inventory.available === 0 }
    Secondary { width: parent.width; text: "Some reset details haven't been provided yet."; visible: root.inventory.undetailed > 0 }
}
