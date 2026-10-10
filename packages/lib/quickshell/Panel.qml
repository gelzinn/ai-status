import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui as Ui
import "." as Plugin

Ui.Panel {
    id: root
    moduleName: "io.github.gelzinn.ai-status"
    manageIpc: false
    property var anchorItem: null
    property var hostWidget: null

    function switchPanel(direction) {
        if (bar && typeof bar.switchPanelFrom === "function")
            return bar.switchPanelFrom(hostWidget || root, direction)
        return false
    }

    Ui.KeyboardPanel {
        id: panel
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: keyCatcher
        contentWidth: panel.fittedContentWidth(Style.space(380))
        contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(640))

        Ui.PanelKeyCatcher {
            id: keyCatcher
            anchors.fill: parent
            onCloseRequested: root.close()
            onTabRequested: direction => root.switchPanel(direction)
            onMoveRequested: (dx, dy) => {
                if (dy !== 0) scroller.contentY = Math.max(0, Math.min(scroller.contentHeight - scroller.height, scroller.contentY + dy * Style.space(40)))
            }
            onTextKey: (text, modifiers) => {
                if (text === "r") Plugin.Model.action("refresh")
                else if (text === "c") Plugin.Model.action("config")
            }

            Flickable {
                id: scroller
                anchors.fill: parent
                contentWidth: width
                contentHeight: content.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: content
                    width: scroller.width
                    spacing: Style.spacing.panelGap

                    Text {
                        width: parent.width
                        text: "AI Status" + (Plugin.Model.snapshot.version ? "  v" + Plugin.Model.snapshot.version.current : "")
                        textFormat: Text.PlainText
                        color: root.barForeground
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Style.font.title
                        font.bold: true
                    }
                    Row {
                        spacing: Style.spacing.controlGap
                        Ui.WidgetButton {
                            bar: root.bar
                            text: "↻ Refresh"
                            onPressed: button => { if (button === Qt.LeftButton) Plugin.Model.action("refresh") }
                        }
                        Ui.WidgetButton {
                            bar: root.bar
                            text: "Configure"
                            onPressed: button => { if (button === Qt.LeftButton) Plugin.Model.action("config") }
                        }
                    }
                    Text {
                        width: parent.width
                        visible: text !== ""
                        text: Plugin.Model.errorMessage || (Plugin.Model.snapshot.version && Plugin.Model.snapshot.version.has_update ? "Update available: v" + Plugin.Model.snapshot.version.latest : "")
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        color: Commons.Color.accent
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Style.font.body
                    }

                    Repeater {
                        model: Plugin.Model.snapshot.providers
                        delegate: Column {
                            id: provider
                            required property var modelData
                            readonly property bool selected: modelData.id === Plugin.Model.snapshot.selected.provider && modelData.idx === Plugin.Model.snapshot.selected.idx
                            width: content.width
                            spacing: Style.spacing.rowGap

                            Text {
                                width: parent.width
                                text: (provider.selected ? "→ " : "") + provider.modelData.name + (provider.modelData.loading ? "  " + Plugin.Model.spinner : "") + (provider.modelData.cached ? "  (cached)" : "")
                                textFormat: Text.PlainText
                                color: root.barForeground
                                opacity: provider.selected ? 1 : 0.65
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.subtitle
                                font.bold: true
                                wrapMode: Text.WordWrap
                            }
                            Text {
                                width: parent.width
                                visible: text !== ""
                                text: provider.modelData.error
                                textFormat: Text.PlainText
                                color: Commons.Color.urgent
                                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                font.pixelSize: Style.font.bodySmall
                                wrapMode: Text.WordWrap
                            }
                            Repeater {
                                model: provider.modelData.metrics
                                delegate: Column {
                                    id: metric
                                    required property var modelData
                                    readonly property bool selected: provider.selected && modelData.key === Plugin.Model.snapshot.selected.metric
                                    width: provider.width
                                    spacing: Style.spacing.labelGap
                                    opacity: metric.selected ? 1 : 0.65
                                    Text {
                                        width: parent.width
                                        text: (metric.selected ? "• " : "") + metric.modelData.name + "  " + (provider.modelData.loading ? Plugin.Model.spinner : Math.round(metric.modelData.percentage) + "%")
                                        textFormat: Text.PlainText
                                        color: root.barForeground
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.body
                                        wrapMode: Text.WordWrap
                                    }
                                    Rectangle {
                                        width: parent.width
                                        height: Style.space(5)
                                        radius: height / 2
                                        color: Qt.rgba(root.barForeground.r, root.barForeground.g, root.barForeground.b, 0.15)
                                        clip: true
                                        Rectangle {
                                            width: parent.width * Math.max(0, Math.min(100, metric.modelData.percentage)) / 100
                                            height: parent.height
                                            radius: parent.radius
                                            color: Commons.Color.accent
                                            opacity: provider.modelData.loading ? 0.4 : 1
                                            Behavior on width { NumberAnimation { duration: Style.duration(140) } }
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        text: metric.modelData.detail
                                        textFormat: Text.PlainText
                                        color: root.barForeground
                                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                                        font.pixelSize: Style.font.caption
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }
                    Text {
                        width: parent.width
                        text: "Scroll the bar to switch provider · middle-click to switch limit"
                        textFormat: Text.PlainText
                        color: root.barForeground
                        opacity: 0.6
                        font.family: root.bar ? root.bar.fontFamily : Style.font.family
                        font.pixelSize: Style.font.caption
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
