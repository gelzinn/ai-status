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
    property bool configurationPage: false
    readonly property string panelFont: bar ? bar.fontFamily : Style.font.family

    function configure() {
        if (!Plugin.Model.snapshot.settings || Plugin.Model.settingsSaving) return
        settings.begin()
        configurationPage = true
        open()
    }

    function showUsage() {
        if (!Plugin.Model.settingsSaving) configurationPage = false
    }

    function switchPanel(direction) {
        if (bar && typeof bar.switchPanelFrom === "function")
            return bar.switchPanelFrom(hostWidget || root, direction)
        return false
    }

    onConfigurationPageChanged: scroller.contentY = 0
    onOpenedChanged: if (!opened && !Plugin.Model.settingsSaving) configurationPage = false

    Connections {
        target: Plugin.Model
        function onSettingsSaved() { root.configurationPage = false }
    }

    Ui.KeyboardPanel {
        id: panel
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: keyCatcher
        contentWidth: panel.fittedContentWidth(Style.space(380))
        contentHeight: panel.fittedContentHeight(header.height + Style.space(21) + content.implicitHeight + (footer.visible ? footer.height + Style.space(12) : 0), Style.space(680))

        Ui.PanelKeyCatcher {
            id: keyCatcher
            anchors.fill: parent
            onCloseRequested: {
                if (root.configurationPage) root.showUsage()
                else root.close()
            }
            onTabRequested: direction => {
                if (root.configurationPage) settings.focusFirstControl()
                else root.switchPanel(direction)
            }
            onMoveRequested: (dx, dy) => {
                if (dy !== 0) scroller.contentY = Math.max(0, Math.min(scroller.contentHeight - scroller.height, scroller.contentY + dy * Style.space(40)))
            }
            onTextKey: (text, modifiers) => {
                if (text === "r" && !root.configurationPage) Plugin.Model.action("refresh")
                else if (text === "c" && !root.configurationPage) root.configure()
            }

            Item {
                id: header
                width: parent.width
                height: Style.space(32)
                Text {
                    anchors.left: parent.left
                    anchors.right: controls.left
                    anchors.rightMargin: Style.space(8)
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.configurationPage ? "Settings" : "AI Status"
                    textFormat: Text.PlainText
                    color: root.barForeground
                    font.family: root.panelFont
                    font.pixelSize: Style.font.body
                    font.bold: true
                    elide: Text.ElideRight
                }
                Row {
                    id: controls
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Style.space(4)
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Plugin.Model.snapshot.version ? "v" + Plugin.Model.snapshot.version.current : ""
                        textFormat: Text.PlainText
                        color: root.barForeground
                        opacity: 0.5
                        font.family: root.panelFont
                        font.pixelSize: Style.font.caption
                        rightPadding: Style.space(8)
                    }
                    Ui.WidgetButton {
                        bar: root.bar
                        visible: !root.configurationPage
                        fixedWidth: Style.space(28)
                        fixedHeight: Style.space(28)
                        text: "↻"
                        tooltipText: "Refresh usage (R)"
                        onPressed: button => { if (button === Qt.LeftButton) Plugin.Model.action("refresh") }
                    }
                    Ui.WidgetButton {
                        bar: root.bar
                        fixedWidth: Style.space(28)
                        fixedHeight: Style.space(28)
                        text: root.configurationPage ? "←" : "⚙"
                        tooltipText: root.configurationPage ? "Back to usage (Esc)" : "Configure (C)"
                        enabled: !Plugin.Model.settingsSaving && !!Plugin.Model.snapshot.settings
                        onPressed: button => {
                            if (button === Qt.LeftButton) {
                                if (root.configurationPage) root.showUsage()
                                else root.configure()
                            }
                        }
                    }
                }
            }
            Rectangle {
                id: divider
                anchors.top: header.bottom
                anchors.topMargin: Style.space(8)
                width: parent.width
                height: Style.space(1)
                color: Qt.rgba(root.barForeground.r, root.barForeground.g, root.barForeground.b, 0.12)
            }

            Flickable {
                id: scroller
                anchors.top: divider.bottom
                anchors.topMargin: Style.space(12)
                anchors.bottom: footer.visible ? footer.top : parent.bottom
                anchors.bottomMargin: footer.visible ? Style.space(12) : 0
                width: parent.width
                contentWidth: width
                contentHeight: content.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: content
                    width: scroller.width
                    spacing: Style.space(20)
                    Text {
                        width: parent.width
                        visible: text !== ""
                        text: Plugin.Model.errorMessage || (Plugin.Model.snapshot.version && Plugin.Model.snapshot.version.has_update ? "Update available: v" + Plugin.Model.snapshot.version.latest : "")
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        color: Commons.Color.accent
                        font.family: root.panelFont
                        font.pixelSize: Style.font.caption
                    }
                    Plugin.UsagePage {
                        width: parent.width
                        visible: !root.configurationPage
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                    }
                    Plugin.SettingsPage {
                        id: settings
                        width: parent.width
                        visible: root.configurationPage
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                    }
                }
            }
            Row {
                id: footer
                anchors.bottom: parent.bottom
                anchors.right: parent.right
                spacing: Style.space(8)
                visible: root.configurationPage
                Plugin.PanelButton {
                    text: "Cancel"
                    foreground: root.barForeground
                    fontFamily: root.panelFont
                    enabled: !Plugin.Model.settingsSaving
                    onClicked: root.showUsage()
                }
                Plugin.PanelButton {
                    text: Plugin.Model.settingsSaving ? "Saving…" : "Save"
                    foreground: root.barForeground
                    fontFamily: root.panelFont
                    outlined: true
                    enabled: settings.valid && !Plugin.Model.settingsSaving
                    onClicked: settings.save()
                }
            }
        }
    }
}
