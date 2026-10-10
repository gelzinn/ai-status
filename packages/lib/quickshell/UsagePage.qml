import QtQuick
import qs.Commons
import qs.Commons as Commons
import "." as Plugin

Column {
    id: root
    property color foreground: "white"
    property string fontFamily: Style.font.family
    spacing: Style.space(32)

    component Label: Text {
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
    }

    Repeater {
        model: Plugin.Model.snapshot.providers
        delegate: Column {
            id: provider
            required property var modelData
            readonly property bool selected: modelData.id === Plugin.Model.snapshot.selected.provider && modelData.idx === Plugin.Model.snapshot.selected.idx
            width: root.width
            spacing: Style.space(18)

            Row {
                width: parent.width
                spacing: Style.space(8)
                opacity: provider.selected ? 1 : 0.6
                Label {
                    width: Style.space(16)
                    text: provider.selected ? "→" : ""
                    anchors.verticalCenter: parent.verticalCenter
                }
                Item {
                    width: Style.space(16)
                    height: width
                    anchors.verticalCenter: parent.verticalCenter
                    Image {
                        id: logo
                        anchors.fill: parent
                        source: provider.modelData.logoPath ? "file://" + provider.modelData.logoPath : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }
                    Label {
                        anchors.centerIn: parent
                        visible: logo.status !== Image.Ready
                        text: "◇"
                    }
                }
                Label {
                    width: Math.max(0, parent.width - Style.space(48))
                    text: provider.modelData.name + (provider.modelData.loading ? "  " + Plugin.Model.spinner : "") + (provider.modelData.cached ? "  (cached)" : "")
                    font.bold: provider.selected
                    wrapMode: Text.WordWrap
                }
            }
            Label {
                x: Style.space(24)
                width: Math.max(0, parent.width - x)
                visible: text !== ""
                text: provider.modelData.error
                color: Commons.Color.urgent
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
            }
            Column {
                width: parent.width
                spacing: Style.space(24)
                Repeater {
                    model: provider.modelData.metrics
                    delegate: Item {
                        id: metric
                        required property var modelData
                        readonly property bool selected: provider.selected && modelData.key === Plugin.Model.snapshot.selected.metric
                        width: provider.width
                        implicitHeight: block.implicitHeight
                        Label {
                            width: Style.space(16)
                            text: metric.selected ? "•" : ""
                        }
                        Column {
                            id: block
                            x: Style.space(24)
                            width: Math.max(0, parent.width - x)
                            spacing: Style.space(5)
                            Label {
                                width: parent.width
                                text: metric.modelData.name + ":"
                                opacity: metric.selected ? 1 : 0.55
                                wrapMode: Text.WordWrap
                            }
                            Row {
                                width: parent.width
                                spacing: Style.space(5)
                                opacity: metric.selected ? 1 : 0.55
                                Label { id: leftBracket; text: "[" }
                                Rectangle {
                                    width: Math.max(0, parent.width - leftBracket.width - rightBracket.width - percentage.width - parent.spacing * 3)
                                    height: Style.space(14)
                                    anchors.verticalCenter: parent.verticalCenter
                                    radius: Style.space(1)
                                    color: "transparent"
                                    border.width: 1
                                    border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.15)
                                    clip: true
                                    Rectangle {
                                        width: parent.width * Math.max(0, Math.min(100, metric.modelData.percentage)) / 100
                                        height: parent.height
                                        color: root.foreground
                                        opacity: provider.modelData.loading ? 0.25 : (metric.selected ? 0.8 : 0.5)
                                        Behavior on width { NumberAnimation { duration: Style.duration(180) } }
                                    }
                                }
                                Label { id: rightBracket; text: "]" }
                                Label {
                                    id: percentage
                                    width: Style.space(40)
                                    horizontalAlignment: Text.AlignRight
                                    text: provider.modelData.loading ? Plugin.Model.spinner : Math.round(metric.modelData.percentage) + "%"
                                }
                            }
                            Label {
                                width: parent.width
                                visible: text !== ""
                                text: metric.modelData.detail
                                opacity: 0.4
                                font.pixelSize: Style.font.caption
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }
        }
    }
}
