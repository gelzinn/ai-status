import QtQuick
import QtQuick.Window
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
    property bool aboutPage: false
    property bool updatePage: false
    property real settingsScrollPosition: 0
    property var resetProvider: null
    property real usageScrollPosition: 0
    property Item restoredFocusControl: null
    readonly property var resetEntry: resetProvider ? Plugin.Model.snapshot.providers.find(entry => entry.id === resetProvider.id && entry.idx === resetProvider.idx) || null : null
    readonly property string panelFont: bar ? bar.fontFamily : Style.font.family

    component IconButton: Plugin.PanelIconButton {
        bar: root.bar
        foreground: root.barForeground
    }

    function configure() {
        if (!Plugin.Model.snapshot.settings || Plugin.Model.settingsSaving) return
        settings.begin()
        aboutPage = false
        updatePage = false
        resetProvider = null
        configurationPage = true
        open()
    }

    function showUsage() {
        if (Plugin.Model.settingsSaving) return
        configurationPage = false
        aboutPage = false
        const wasUpdate = updatePage
        updatePage = false
        const previous = resetProvider
        resetProvider = null
        if (previous) Qt.callLater(() => {
            restoreScrollPosition(usageScrollPosition)
            const button = usage.resetButton(previous.id, previous.idx)
            if (button && button.visible) restoreFocus(button)
            else keyCatcher.forceActiveFocus()
        })
        else if (wasUpdate) Qt.callLater(() => {
            restoreScrollPosition(usageScrollPosition)
            if (updateLink.visible) restoreFocus(updateLink)
            else keyCatcher.forceActiveFocus()
        })
    }

    function showAbout() {
        settings.closeSelectors()
        settingsScrollPosition = scroller.contentY
        aboutPage = true
        scroller.contentY = 0
        backButton.focusProgrammatically()
    }

    function goBack() {
        if (aboutPage) {
            aboutPage = false
            Qt.callLater(() => {
                restoreScrollPosition(settingsScrollPosition)
                restoredFocusControl = settings.focusAboutControl()
            })
        } else showUsage()
    }

    function showResetCredits(provider, idx) {
        const entry = Plugin.Model.snapshot.providers.find(item => item.id === provider && item.idx === idx)
        if (!entry || !entry.resetCredits || entry.resetCredits.available === 0) return
        usageScrollPosition = scroller.contentY
        resetProvider = {id: provider, idx: idx}
        scroller.contentY = 0
        Qt.callLater(() => backButton.focusProgrammatically())
    }

    function showUpdate() {
        usageScrollPosition = scroller.contentY
        updatePage = true
        scroller.contentY = 0
        Qt.callLater(() => backButton.focusProgrammatically())
    }

    function switchPanel(direction) {
        if (bar && typeof bar.switchPanelFrom === "function")
            return bar.switchPanelFrom(hostWidget || root, direction)
        return false
    }

    function restoreFocus(item) {
        // Returning to a page preserves its saved scroll position. The next
        // keyboard focus change still reveals the newly focused control.
        restoredFocusControl = item
        item.forceActiveFocus()
    }

    function restoreScrollPosition(position) {
        // Recompute the restored page before clamping to its scroll range.
        content.forceLayout()
        scroller.contentY = Math.min(position, Math.max(0, scroller.contentHeight - scroller.height))
    }

    function revealFocusedControl() {
        const window = keyCatcher.Window.window
        const item = window ? window.activeFocusItem : null
        if (item !== restoredFocusControl) restoredFocusControl = null
        if (!opened || !item || item === restoredFocusControl || !item.visible || scroller.height <= 0) return
        let ancestor = item
        while (ancestor && ancestor !== content) ancestor = ancestor.parent
        if (ancestor !== content) return

        const margin = Style.space(4)
        const top = item.mapToItem(scroller, 0, 0).y
        const bottom = top + item.height
        let nextY = scroller.contentY
        if (top < margin || item.height + margin * 2 > scroller.height)
            nextY += top - margin
        else if (bottom > scroller.height - margin)
            nextY += bottom - scroller.height + margin
        nextY = Math.max(0, Math.min(nextY, Math.max(0, scroller.contentHeight - scroller.height)))
        if (nextY !== scroller.contentY) {
            scroller.cancelFlick()
            scroller.contentY = nextY
        }
    }

    onConfigurationPageChanged: scroller.contentY = 0
    onResetEntryChanged: if (resetProvider && !resetEntry) Qt.callLater(() => {
        if (resetProvider && !resetEntry) showUsage()
    })
    onOpenedChanged: if (!opened && !Plugin.Model.settingsSaving) { configurationPage = false; aboutPage = false; updatePage = false; resetProvider = null }

    Connections {
        target: keyCatcher.Window.window
        function onActiveFocusItemChanged() {
            // Wait for the focus chain and any page layout changes to settle.
            Qt.callLater(root.revealFocusedControl)
        }
    }

    Ui.KeyboardPanel {
        id: panel
        objectName: "panel-surface"
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: keyCatcher
        contentWidth: panel.fittedContentWidth(Style.space(380))
        contentHeight: panel.fittedContentHeight(header.height + panel.padding + Style.space(13) + content.implicitHeight + (footer.visible ? footer.height + Style.space(12) : 0), Style.space(680))

        Ui.PanelKeyCatcher {
            id: keyCatcher
            objectName: "panel-key-catcher"
            anchors.fill: parent
            onCloseRequested: {
                if (root.configurationPage || root.resetProvider || root.updatePage) root.goBack()
                else root.close()
            }
            onTabRequested: direction => {
                if (root.aboutPage) backButton.focusFromKeyboard(direction > 0 ? Qt.TabFocusReason : Qt.BacktabFocusReason)
                else if (root.configurationPage) settings.focusFirstControl()
                else if (root.resetProvider) backButton.focusFromKeyboard(direction > 0 ? Qt.TabFocusReason : Qt.BacktabFocusReason)
                else if (root.updatePage) updates.focusFirstControl()
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
                    visible: root.configurationPage || !!root.resetProvider || root.updatePage
                    iconName: "arrow-left"
                    tooltipText: root.aboutPage ? "Back to settings (Esc)" : "Back to usage (Esc)"
                    enabled: !Plugin.Model.settingsSaving
                    onPressed: button => { if (button === Qt.LeftButton) root.goBack() }
                }
                Text {
                    objectName: "panel-title"
                    anchors.left: parent.left
                    anchors.leftMargin: backButton.visible ? backButton.width + Style.space(12) : 0
                    anchors.right: controls.left
                    anchors.rightMargin: Style.space(8)
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.aboutPage ? "About" : root.configurationPage ? "Settings" : root.updatePage ? "Update AI Status" : "AI Status"
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
                        visible: !root.configurationPage && !root.updatePage
                        enabled: !Plugin.Model.snapshot.loading
                        iconName: "refresh-cw"
                        spinning: !!Plugin.Model.snapshot.loading
                        tooltipText: "Refresh usage (R)"
                        onPressed: button => { if (button === Qt.LeftButton) Plugin.Model.action("refresh") }
                    }
                    IconButton {
                        objectName: "panel-settings"
                        visible: !root.configurationPage && !root.resetProvider && !root.updatePage
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
                objectName: "panel-divider"
                anchors.top: header.bottom
                anchors.topMargin: panel.padding
                x: -panel.padding
                width: parent.width + panel.padding * 2
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
                onContentYChanged: settings.closeSelectors()

                Column {
                    id: content
                    width: scroller.width
                    spacing: Style.space(20)
                    Text {
                        width: parent.width
                        visible: text !== ""
                        text: Plugin.Model.errorMessage
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        color: Commons.Color.accent
                        font.family: root.panelFont
                        font.pixelSize: Style.font.caption
                    }
                    Plugin.PanelButton {
                        id: updateLink
                        objectName: "update-available"
                        width: parent.width
                        visible: !root.configurationPage && !root.resetProvider && !root.updatePage && !!Plugin.Model.snapshot.version && !!Plugin.Model.snapshot.version.has_update
                        text: "Update available: v" + (Plugin.Model.snapshot.version ? Plugin.Model.snapshot.version.latest || "" : "")
                        trailingIconName: "arrow-right"
                        alignLeft: true
                        foreground: "#89b4fa"
                        fontFamily: root.panelFont
                        onClicked: root.showUpdate()
                    }
                    Plugin.UsagePage {
                        id: usage
                        width: parent.width
                        visible: !root.configurationPage && !root.resetProvider && !root.updatePage
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                        onResetRequested: (provider, idx) => root.showResetCredits(provider, idx)
                        onSettingsRequested: root.configure()
                    }
                    Plugin.UpdatePage {
                        id: updates
                        objectName: "panel-update-page"
                        width: parent.width
                        visible: root.updatePage
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                    }
                    Plugin.ResetCreditsPage {
                        id: credits
                        width: parent.width
                        visible: !!root.resetProvider && !root.configurationPage
                        provider: root.resetEntry
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                    }
                    Plugin.SettingsPage {
                        id: settings
                        objectName: "panel-settings-page"
                        width: parent.width
                        visible: root.configurationPage && !root.aboutPage
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                        popupParent: keyCatcher
                        onAboutRequested: root.showAbout()
                    }
                    Plugin.AboutPage {
                        width: parent.width
                        visible: root.aboutPage
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
                visible: root.configurationPage && !root.aboutPage
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
