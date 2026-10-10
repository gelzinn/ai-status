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
    property var resetProvider: null
    property real usageScrollPosition: 0
    readonly property var resetEntry: resetProvider ? Plugin.Model.snapshot.providers.find(entry => entry.id === resetProvider.id && entry.idx === resetProvider.idx) || null : null
    readonly property string panelFont: bar ? bar.fontFamily : Style.font.family

    component IconButton: Ui.WidgetButton {
        id: iconButton
        property string iconName: ""
        bar: root.bar
        fixedWidth: Style.space(28)
        fixedHeight: Style.space(28)
        labelVisible: false
        hasVisualContent: true
        opacity: enabled ? 1 : 0.35
        Accessible.role: Accessible.Button
        Accessible.name: tooltipText
        Accessible.onPressAction: if (enabled) triggerPress(Qt.LeftButton)
        Plugin.PanelIcon {
            anchors.centerIn: parent
            width: Style.space(16)
            height: Style.space(16)
            name: iconButton.iconName
            foreground: iconButton.foreground
        }
    }

    function configure() {
        if (!Plugin.Model.snapshot.settings || Plugin.Model.settingsSaving) return
        settings.begin()
        resetProvider = null
        configurationPage = true
        open()
    }

    function showUsage() {
        if (Plugin.Model.settingsSaving) return
        configurationPage = false
        const previous = resetProvider
        resetProvider = null
        if (previous) Qt.callLater(() => {
            scroller.contentY = Math.min(usageScrollPosition, Math.max(0, scroller.contentHeight - scroller.height))
            const button = usage.resetButton(previous.id, previous.idx)
            if (button && button.visible) button.forceActiveFocus()
            else keyCatcher.forceActiveFocus()
        })
    }

    function showResetCredits(provider, idx) {
        const entry = Plugin.Model.snapshot.providers.find(item => item.id === provider && item.idx === idx)
        if (!entry || !entry.resetCredits || entry.resetCredits.available === 0) return
        usageScrollPosition = scroller.contentY
        resetProvider = {id: provider, idx: idx}
        scroller.contentY = 0
        Qt.callLater(credits.focusBack)
    }

    function switchPanel(direction) {
        if (bar && typeof bar.switchPanelFrom === "function")
            return bar.switchPanelFrom(hostWidget || root, direction)
        return false
    }

    onConfigurationPageChanged: scroller.contentY = 0
    onResetEntryChanged: if (resetProvider && !resetEntry) Qt.callLater(() => {
        if (resetProvider && !resetEntry) showUsage()
    })
    onOpenedChanged: if (!opened && !Plugin.Model.settingsSaving) { configurationPage = false; resetProvider = null }

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
                if (root.configurationPage || root.resetProvider) root.showUsage()
                else root.close()
            }
            onTabRequested: direction => {
                if (root.configurationPage) settings.focusFirstControl()
                else if (root.resetProvider) credits.focusBack()
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
                IconButton {
                    id: backButton
                    objectName: "panel-back"
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.configurationPage
                    iconName: "arrow-left"
                    tooltipText: "Back to usage (Esc)"
                    enabled: !Plugin.Model.settingsSaving
                    onPressed: button => { if (button === Qt.LeftButton) root.showUsage() }
                }
                Text {
                    objectName: "panel-title"
                    anchors.left: parent.left
                    anchors.leftMargin: backButton.visible ? backButton.width + Style.space(8) : 0
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
                    IconButton {
                        objectName: "panel-refresh"
                        visible: !root.configurationPage
                        enabled: !Plugin.Model.snapshot.loading
                        iconName: "refresh-cw"
                        tooltipText: "Refresh usage (R)"
                        onPressed: button => { if (button === Qt.LeftButton) Plugin.Model.action("refresh") }
                    }
                    IconButton {
                        objectName: "panel-settings"
                        visible: !root.configurationPage && !root.resetProvider
                        iconName: "settings"
                        tooltipText: "Configure (C)"
                        enabled: !Plugin.Model.settingsSaving && !!Plugin.Model.snapshot.settings
                        onPressed: button => {
                            if (button === Qt.LeftButton) {
                                root.configure()
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
                objectName: "panel-scroller"
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
                        id: usage
                        width: parent.width
                        visible: !root.configurationPage && !root.resetProvider
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                        onResetRequested: (provider, idx) => root.showResetCredits(provider, idx)
                        onSettingsRequested: root.configure()
                    }
                    Plugin.ResetCreditsPage {
                        id: credits
                        width: parent.width
                        visible: !!root.resetProvider && !root.configurationPage
                        provider: root.resetEntry
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                        onBackRequested: root.showUsage()
                    }
                    Plugin.SettingsPage {
                        id: settings
                        objectName: "panel-settings-page"
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
                Text {
                    visible: settings.saved
                    text: "Saved"
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.barForeground
                    font.family: root.panelFont
                    font.pixelSize: Style.font.caption
                }
                Plugin.PanelButton {
                    objectName: "settings-cancel"
                    text: "Cancel"
                    foreground: root.barForeground
                    fontFamily: root.panelFont
                    enabled: !Plugin.Model.settingsSaving
                    onClicked: root.showUsage()
                }
                Plugin.PanelButton {
                    objectName: "settings-save"
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
