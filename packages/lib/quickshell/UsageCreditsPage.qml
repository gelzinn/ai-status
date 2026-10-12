import QtQuick
import QtQuick.Shapes
import qs.Commons

Column {
    id: root
    property var provider: null
    property var credit: null
    property color foreground: "white"
    property string fontFamily: Style.font.family
    readonly property var rows: {
        if (!credit) return []
        const status = credit.status || "unavailable"
        const entries = [
            {id: "status", title: "Status", value: status.charAt(0).toUpperCase() + status.slice(1)},
            {id: "limit", title: "Allowance", value: credit.limit_value || "Not reported"},
            {id: "used", title: "Used", value: credit.used_value || "Not reported"},
            {id: "expires", title: "Expires", value: credit.expires || "Not reported"},
            {id: "remaining", title: "Time left", value: credit.remaining || "Not reported"}
        ]
        if (credit.stale || status === "unavailable" || status === "expired") {
            entries.push({id: "observed-balance", title: "Last observed balance", value: credit.observed_value || "Not reported"})
            entries.push({id: "observed", title: "Last observed", value: credit.observed || "Not reported"})
        }
        return entries
    }
    spacing: Style.space(18)

    component Label: Text {
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        wrapMode: Text.WordWrap
    }
    component Secondary: Label {
        opacity: 0.55
        font.pixelSize: Style.font.caption
    }
    Item {
        width: parent.width
        height: Math.max(Style.space(24), providerLabel.implicitHeight)
        Image {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Style.space(16)
            height: width
            source: root.provider && root.provider.logoPath ? "file://" + root.provider.logoPath : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }
        Label {
            id: providerLabel
            objectName: "usage-credits-provider"
            x: Style.space(24)
            width: Math.max(0, parent.width - x)
            anchors.verticalCenter: parent.verticalCenter
            text: root.credit && root.credit.heading ? root.credit.heading : root.provider
                ? root.provider.name + (root.credit ? " · " + root.credit.title : "") : ""
        }
    }
    Column {
        objectName: "usage-credits-balance-summary"
        width: parent.width
        spacing: Style.space(4)
        Label {
            objectName: "usage-credits-balance-label"
            width: parent.width
            text: root.credit && (root.credit.status === "expired" || root.credit.status === "unavailable") ? "Current balance" : "Available balance"
            opacity: 0.55
        }
        Label {
            objectName: "usage-credits-balance"
            width: parent.width
            text: root.credit ? root.credit.value : "Unavailable"
            font.pixelSize: 24
            font.weight: Font.Medium
        }
    }
    Column {
        width: parent.width
        spacing: Style.space(8)
        Secondary {
            objectName: "usage-credits-explanation"
            width: parent.width
            text: "For cloud sessions. This balance is separate from your usage limits and reset credits."
        }
        Secondary {
            objectName: "usage-credits-unavailable"
            width: parent.width
            visible: !!root.credit && (root.credit.stale || root.credit.status === "unavailable")
            text: root.credit && root.credit.status_note ? root.credit.status_note : "The current balance could not be confirmed. Refresh to check again."
        }
    }
    Rectangle {
        id: creditTable
        objectName: "usage-credits-table"
        width: parent.width
        implicitHeight: table.implicitHeight + 2
        color: "transparent"
        border.width: 1
        radius: Style.cornerRadius
        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.15)
        readonly property real labelColumnWidth: Style.space(18) + (table.width - Style.space(36)) * 0.42
        Shape {
            id: labelBackground
            objectName: "usage-credits-label-background"
            x: table.x
            y: table.y
            width: creditTable.labelColumnWidth
            height: table.height
            readonly property color color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
            readonly property real radius: Math.max(0, creditTable.radius - 1)
            antialiasing: true
            layer.enabled: visible
            layer.samples: 4
            layer.smooth: true
            ShapePath {
                strokeColor: "transparent"
                fillColor: labelBackground.color
                startX: labelBackground.width
                startY: 0
                PathLine { x: labelBackground.radius; y: 0 }
                PathQuad { x: 0; y: labelBackground.radius; controlX: 0; controlY: 0 }
                PathLine { x: 0; y: labelBackground.height - labelBackground.radius }
                PathQuad { x: labelBackground.radius; y: labelBackground.height; controlX: 0; controlY: labelBackground.height }
                PathLine { x: labelBackground.width; y: labelBackground.height }
                PathLine { x: labelBackground.width; y: 0 }
            }
        }
        Rectangle {
            objectName: "usage-credits-column-divider"
            x: table.x + creditTable.labelColumnWidth
            y: table.y
            width: 1
            height: table.height
            color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.09)
        }
        Column {
            id: table
            x: 1
            y: 1
            width: parent.width - 2
            Repeater {
                model: root.rows
                delegate: Item {
                    required property var modelData
                    required property int index
                    width: table.width
                    implicitHeight: Math.max(rowTitle.implicitHeight, rowValue.implicitHeight) + Style.space(24)
                    Rectangle {
                        width: parent.width
                        height: 1
                        visible: parent.index > 0
                        color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.09)
                    }
                    Label {
                        id: rowTitle
                        x: Style.space(12)
                        y: Style.space(12)
                        width: creditTable.labelColumnWidth - Style.space(18)
                        text: parent.modelData.title
                        opacity: 0.55
                    }
                    Label {
                        id: rowValue
                        objectName: "usage-credits-" + parent.modelData.id
                        x: rowTitle.x + rowTitle.width + Style.space(12)
                        y: rowTitle.y
                        width: parent.width - x - Style.space(12)
                        text: parent.modelData.value
                    }
                }
            }
        }
    }
    Secondary {
        objectName: "usage-credits-timezone"
        width: parent.width
        text: root.credit && root.credit.timezone ? "Local time · " + root.credit.timezone : ""
        visible: text.length > 0
    }
}
