import QtQuick
import qs.Commons
import "." as Plugin
import "StableList.js" as StableList

Column {
    id: root
    property color foreground: "white"
    property string fontFamily: Style.font.family
    signal resetRequested(string provider, int idx)
    signal settingsRequested()
    spacing: Style.space(20)

    function syncProviders() {
        StableList.sync(providers, Plugin.Model.snapshot.providers, entry => entry.id + ":" + entry.idx)
    }
    function resetButton(id, idx) {
        for (let index = 0; index < providerRepeater.count; index++) {
            const item = providerRepeater.itemAt(index)
            if (item.modelData.id === id && item.modelData.idx === idx) return item.resetLink
        }
        return null
    }
    Component.onCompleted: syncProviders()
    Connections {
        target: Plugin.Model
        function onSnapshotChanged() { root.syncProviders() }
    }
    ListModel { id: providers; dynamicRoles: true }
    component Label: Text {
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
    }
    Column {
        width: parent.width
        visible: providers.count === 0
        spacing: Style.space(10)
        Label {
            objectName: "empty-usage"
            width: parent.width
            text: Plugin.Model.snapshot.loading ? "Checking your connected providers…"
                : Plugin.Model.snapshot.settings && Plugin.Model.snapshot.settings.enabled.length === 0
                  ? "No providers enabled. Choose them in Settings."
                  : "No usage available. Connect a provider and refresh."
            wrapMode: Text.WordWrap
        }
        Plugin.PanelButton {
            text: "Settings"
            foreground: root.foreground
            fontFamily: root.fontFamily
            onClicked: root.settingsRequested()
        }
    }
    Repeater {
        id: providerRepeater
        model: providers
        delegate: Column {
            id: provider
            required property var entry
            required property int index
            property alias resetLink: creditsLink
            readonly property var modelData: entry
            readonly property bool selected: modelData.id === Plugin.Model.snapshot.selected.provider && modelData.idx === Plugin.Model.snapshot.selected.idx
            width: root.width
            spacing: Style.space(10)
            function choose(key) { Plugin.Model.selectMetric(modelData.id, modelData.idx, key) }
            function syncMetrics() { StableList.sync(metrics, modelData.metrics, entry => entry.key) }
            onModelDataChanged: syncMetrics()
            Component.onCompleted: syncMetrics()
            ListModel { id: metrics; dynamicRoles: true }

            Item {
                width: parent.width
                height: heading.implicitHeight + Style.space(8)
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: provider.modelData.name
                Keys.onReturnPressed: provider.choose(provider.modelData.metrics[0].key)
                Keys.onSpacePressed: provider.choose(provider.modelData.metrics[0].key)
                Row {
                    id: heading
                    y: Style.space(4)
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
                        Label { anchors.centerIn: parent; visible: logo.status !== Image.Ready; text: "◇" }
                    }
                    Label {
                        objectName: "usage-provider-name-" + provider.modelData.id + "-" + provider.modelData.idx
                        width: Math.max(0, parent.width - Style.space(48))
                        text: provider.modelData.name
                        font.bold: provider.selected
                        wrapMode: Text.WordWrap
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { parent.forceActiveFocus(); provider.choose(provider.modelData.metrics[0].key) }
                }
            }
            Label {
                x: Style.space(48)
                width: Math.max(0, parent.width - x)
                visible: provider.modelData.cached
                text: "Cached data"
                opacity: 0.4
                font.pixelSize: Style.font.caption
            }
            Column {
                width: parent.width
                spacing: Style.space(10)
                Repeater {
                    model: metrics
                    delegate: Item {
                        id: metric
                        objectName: "usage-metric-" + provider.modelData.id + "-" + provider.modelData.idx + "-" + modelData.key
                        required property var entry
                        readonly property var modelData: entry
                        readonly property bool selected: provider.selected && modelData.key === Plugin.Model.snapshot.selected.metric
                        readonly property bool inlineAmount: modelData.isAmount === true
                        width: provider.width
                        implicitHeight: block.implicitHeight
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: provider.modelData.name + " " + modelData.name + " " + (modelData.value || Math.round(modelData.percentage) + "%")
                        Keys.onReturnPressed: provider.choose(modelData.key)
                        Keys.onSpacePressed: provider.choose(modelData.key)
                        Label { width: Style.space(16); text: metric.selected ? "•" : "" }
                        Column {
                            id: block
                            x: Style.space(48)
                            width: Math.max(0, parent.width - x)
                            spacing: Style.space(4)
                            Item {
                                id: metricHeader
                                width: parent.width
                                height: Math.max(metricTitle.implicitHeight, metricValue.implicitHeight)
                                Label {
                                    id: metricTitle
                                    objectName: "usage-title-" + provider.modelData.id + "-" + provider.modelData.idx + "-" + metric.modelData.key
                                    width: metric.inlineAmount ? Math.min(implicitWidth, Math.max(0, parent.width - metricValue.width - Style.space(6))) : Math.max(0, parent.width - metricValue.width - Style.space(12))
                                    text: (metric.modelData.title || metric.modelData.name) + (metric.inlineAmount ? ":" : "")
                                    opacity: metric.selected ? 1 : 0.55
                                    wrapMode: Text.WordWrap
                                }
                                TextMetrics {
                                    id: valueMetrics
                                    font: metricValue.font
                                    text: metric.modelData.value || Math.round(metric.modelData.percentage) + "%"
                                }
                                Label {
                                    id: metricValue
                                    objectName: "usage-value-" + provider.modelData.id + "-" + provider.modelData.idx + "-" + metric.modelData.key
                                    anchors.right: metric.inlineAmount ? undefined : parent.right
                                    x: metric.inlineAmount ? metricTitle.width + Style.space(6) : 0
                                    width: Math.min(parent.width * 0.6, Math.max(Style.space(40), Math.ceil(valueMetrics.advanceWidth)))
                                    horizontalAlignment: metric.inlineAmount ? Text.AlignLeft : Text.AlignRight
                                    wrapMode: Text.WordWrap
                                    text: provider.modelData.loading ? Plugin.Model.spinner : (metric.modelData.value || Math.round(metric.modelData.percentage) + "%")
                                    opacity: metric.selected ? 1 : 0.55
                                }
                            }
                            Row {
                                width: parent.width
                                visible: metric.modelData.hasPercentage !== false
                                spacing: Style.space(4)
                                Label { id: leftBracket; objectName: "usage-bracket-" + provider.modelData.id + "-" + provider.modelData.idx + "-" + metric.modelData.key; text: "["; opacity: metric.selected ? 1 : 0.55 }
                                Plugin.UsageBar {
                                    visible: metric.modelData.hasPercentage !== false
                                    objectName: "usage-bar-" + provider.modelData.id + "-" + provider.modelData.idx + "-" + metric.modelData.key
                                    width: Math.max(0, parent.width - leftBracket.width - rightBracket.width - parent.spacing * 2)
                                    height: implicitHeight
                                    anchors.verticalCenter: parent.verticalCenter
                                    percentage: metric.modelData.percentage || 0
                                    active: metric.selected
                                    loading: provider.modelData.loading
                                    groupIndex: provider.index
                                    foreground: root.foreground
                                }
                                Label { id: rightBracket; text: "]"; opacity: metric.selected ? 1 : 0.55 }
                            }
                            Label {
                                width: parent.width
                                objectName: "usage-detail-" + provider.modelData.id + "-" + provider.modelData.idx + "-" + metric.modelData.key
                                visible: text !== ""
                                text: metric.modelData.detail
                                opacity: 0.4
                                font.pixelSize: Style.font.caption
                                wrapMode: Text.WordWrap
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { metric.forceActiveFocus(); provider.choose(metric.modelData.key) }
                        }
                    }
                }
            }
            Plugin.PanelButton {
                id: creditsLink
                objectName: "reset-credits-" + provider.modelData.id + "-" + provider.modelData.idx
                x: Style.space(38)
                width: Math.max(0, parent.width - x)
                visible: !!provider.modelData.resetCredits && provider.modelData.resetCredits.available > 0
                text: "Reset credits: " + (provider.modelData.resetCredits ? provider.modelData.resetCredits.available : 0) + " available"
                trailingIconName: "arrow-right"
                alignLeft: true
                foreground: root.foreground
                fontFamily: root.fontFamily
                onClicked: root.resetRequested(provider.modelData.id, provider.modelData.idx)
            }
        }
    }
}
