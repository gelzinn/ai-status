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
    property var creditSelection: null
    property real usageScrollPosition: 0
    property Item restoredFocusControl: null
    readonly property var resetEntry: resetProvider ? Plugin.Model.snapshot.providers.find(entry => entry.id === resetProvider.id && entry.idx === resetProvider.idx) || null : null
    readonly property var creditProvider: creditSelection ? Plugin.Model.snapshot.providers.find(entry => entry.id === creditSelection.id && entry.idx === creditSelection.idx) || null : null
    readonly property var creditEntry: creditSelection && creditProvider ? (creditProvider.monetaryCredits || []).find(entry => entry.id === creditSelection.creditId) || null : null
    readonly property string panelFont: bar ? bar.fontFamily : Style.font.family
    readonly property real settingsTabGap: Style.space(12)

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
        creditSelection = null
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
        const previousCredit = creditSelection
        resetProvider = null
        creditSelection = null
        if (previous) Qt.callLater(() => {
            restoreScrollPosition(usageScrollPosition)
            const button = usage.resetButton(previous.id, previous.idx)
            if (button && button.visible) restoreFocus(button)
            else keyCatcher.forceActiveFocus()
        })
        else if (previousCredit) Qt.callLater(() => {
            restoreScrollPosition(usageScrollPosition)
            const button = usage.creditButton(previousCredit.id, previousCredit.idx, previousCredit.creditId)
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
        creditSelection = null
        resetProvider = {id: provider, idx: idx}
        scroller.contentY = 0
        Qt.callLater(() => backButton.focusProgrammatically())
    }

    function showUsageCredits(provider, idx, creditId) {
        const entry = Plugin.Model.snapshot.providers.find(item => item.id === provider && item.idx === idx)
        if (!entry || !(entry.monetaryCredits || []).some(item => item.id === creditId)) return
        usageScrollPosition = scroller.contentY
        resetProvider = null
        creditSelection = {id: provider, idx: idx, creditId: creditId}
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
    onCreditEntryChanged: if (creditSelection && !creditEntry) Qt.callLater(() => {
        if (creditSelection && !creditEntry) showUsage()
    })
    onOpenedChanged: if (!opened && !Plugin.Model.settingsSaving) { configurationPage = false; aboutPage = false; updatePage = false; resetProvider = null; creditSelection = null }

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
        contentHeight: panel.fittedContentHeight(header.height + panel.padding + Style.space(1) + scroller.contentHeight + (settingsNavigation.visible ? settingsNavigation.height : 0) + (footer.visible ? footer.height : -panel.padding), Style.space(680))

        Ui.PanelKeyCatcher {
            id: keyCatcher
            objectName: "panel-key-catcher"
            anchors.fill: parent
            onCloseRequested: {
                if (root.configurationPage || root.resetProvider || root.creditSelection || root.updatePage) root.goBack()
                else root.close()
            }
            onTabRequested: direction => {
                if (root.aboutPage) backButton.focusFromKeyboard(direction > 0 ? Qt.TabFocusReason : Qt.BacktabFocusReason)
                else if (root.configurationPage) settingsNavigation.focusCurrentControl()
                else if (root.resetProvider || root.creditSelection) backButton.focusFromKeyboard(direction > 0 ? Qt.TabFocusReason : Qt.BacktabFocusReason)
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
                    visible: root.configurationPage || !!root.resetProvider || !!root.creditSelection || root.updatePage
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
                        visible: !root.configurationPage && !root.resetProvider && !root.creditSelection && !root.updatePage
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
                color: Commons.Color.popups.border
            }

            Flickable {
                id: settingsNavigation
                objectName: "settings-navigation"
                anchors.top: divider.bottom
                x: -panel.padding
                width: parent.width + panel.padding * 2
                height: sectionTabs.height + root.settingsTabGap
                contentWidth: sectionTabs.width + panel.padding * 2
                contentHeight: height
                clip: true
                flickableDirection: Flickable.HorizontalFlick
                boundsBehavior: Flickable.StopAtBounds
                visible: root.configurationPage && !root.aboutPage
                enabled: !Plugin.Model.settingsSaving
                function focusCurrentControl() {
                    sectionButtons.itemAt(settings.sections.findIndex(item => item.key === settings.section)).forceActiveFocus(Qt.TabFocusReason)
                }
                function revealTab(button) {
                    if (!button) return
                    let nextX = contentX
                    const left = sectionTabs.x + button.x - panel.padding
                    const right = sectionTabs.x + button.x + button.width + panel.padding
                    if (left < contentX) nextX = left
                    else if (right > contentX + width) nextX = right - width
                    contentX = Math.max(0, Math.min(nextX, Math.max(0, contentWidth - width)))
                }
                function moveFocus(index, offset) {
                    const next = (index + offset + sectionButtons.count) % sectionButtons.count
                    sectionButtons.itemAt(next).forceActiveFocus(Qt.TabFocusReason)
                    settings.selectSection(settings.sections[next].key)
                }
                WheelHandler {
                    target: null
                    onWheel: event => {
                        const delta = event.pixelDelta.x || event.pixelDelta.y || event.angleDelta.x / 3 || event.angleDelta.y / 3
                        settingsNavigation.contentX = Math.max(0, Math.min(settingsNavigation.contentWidth - settingsNavigation.width, settingsNavigation.contentX - delta))
                        event.accepted = true
                    }
                }
                Row {
                    id: sectionTabs
                    x: panel.padding
                    y: root.settingsTabGap
                    spacing: root.settingsTabGap
                    Repeater {
                        id: sectionButtons
                        model: settings.sections
                        delegate: Plugin.PanelButton {
                            required property var modelData
                            required property int index
                            objectName: "settings-nav-" + modelData.key
                            width: implicitWidth + Style.space(12)
                            text: modelData.label
                            fontFamily: root.panelFont
                            foreground: root.barForeground
                            outlined: true
                            color: settings.section === modelData.key ? Qt.rgba(foreground.r, foreground.g, foreground.b, 0.12)
                                : activeFocus ? Qt.rgba(foreground.r, foreground.g, foreground.b, 0.06) : "transparent"
                            Accessible.role: Accessible.PageTab
                            Accessible.selected: settings.section === modelData.key
                            onClicked: settings.selectSection(modelData.key)
                            onActiveFocusChanged: if (activeFocus) settingsNavigation.revealTab(sectionButtons.itemAt(index))
                            Keys.onLeftPressed: settingsNavigation.moveFocus(index, -1)
                            Keys.onRightPressed: settingsNavigation.moveFocus(index, 1)
                        }
                    }
                }
            }

            Flickable {
                id: scroller
                objectName: "panel-scroller"
                anchors.top: settingsNavigation.visible ? settingsNavigation.bottom : divider.bottom
                anchors.bottom: footer.visible ? footer.top : parent.bottom
                anchors.bottomMargin: footer.visible ? 0 : -panel.padding
                x: -panel.padding
                width: parent.width + panel.padding * 2
                contentWidth: width
                contentHeight: content.implicitHeight + Style.space(24)
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                onContentYChanged: settings.closeSelectors()

                Column {
                    id: content
                    x: panel.padding
                    y: Style.space(12)
                    width: scroller.width - panel.padding * 2
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
                        visible: !root.configurationPage && !root.resetProvider && !root.creditSelection && !root.updatePage && !!Plugin.Model.snapshot.version && !!Plugin.Model.snapshot.version.has_update
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
                        visible: !root.configurationPage && !root.resetProvider && !root.creditSelection && !root.updatePage
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                        onResetRequested: (provider, idx) => root.showResetCredits(provider, idx)
                        onCreditRequested: (provider, idx, creditId) => root.showUsageCredits(provider, idx, creditId)
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
                    Plugin.UsageCreditsPage {
                        objectName: "panel-usage-credits-page"
                        width: parent.width
                        visible: !!root.creditSelection && !root.configurationPage
                        provider: root.creditProvider
                        credit: root.creditEntry
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
                        inlineValidation: false
                        onAboutRequested: root.showAbout()
                        onSectionChanged: {
                            scroller.cancelFlick()
                            scroller.contentY = 0
                            Qt.callLater(() => {
                                content.forceLayout()
                                if (!root.configurationPage || root.aboutPage) return
                                settingsNavigation.revealTab(sectionButtons.itemAt(settings.sections.findIndex(item => item.key === settings.section)))
                                const item = keyCatcher.Window.window ? keyCatcher.Window.window.activeFocusItem : null
                                if (item && !item.visible) settingsNavigation.focusCurrentControl()
                            })
                        }
                    }
                    Plugin.AboutPage {
                        width: parent.width
                        visible: root.aboutPage
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                    }
                }
            }
            Item {
                id: footer
                objectName: "settings-footer"
                anchors.bottom: parent.bottom
                width: parent.width
                height: footerDivider.height + Style.space(12) + footerActions.height + (footerFeedback.visible ? footerFeedback.height + Style.space(8) : 0)
                visible: root.configurationPage && !root.aboutPage
                Rectangle {
                    id: footerDivider
                    objectName: "settings-footer-divider"
                    x: -panel.padding
                    width: parent.width + panel.padding * 2
                    height: Style.space(1)
                    color: divider.color
                }
                Column {
                    id: footerFeedback
                    anchors.top: footerDivider.bottom
                    anchors.topMargin: Style.space(12)
                    width: parent.width
                    spacing: Style.space(6)
                    visible: !Plugin.Model.settingsSaving && (Plugin.Model.settingsError !== "" || settings.validationSection !== "")
                    Text {
                        objectName: "settings-validation-message"
                        width: parent.width
                        text: Plugin.Model.settingsError || settings.validationMessage
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        color: Commons.Color.urgent
                        font.family: root.panelFont
                        font.pixelSize: Style.font.caption
                    }
                    Plugin.PanelButton {
                        objectName: "settings-review-section"
                        visible: settings.validationSection !== "" && settings.validationSection !== settings.section
                        text: settings.validationSection ? "Review " + settings.sections.find(item => item.key === settings.validationSection).label : ""
                        fontFamily: root.panelFont
                        foreground: root.barForeground
                        outlined: true
                        onClicked: settings.selectSection(settings.validationSection)
                    }
                }
                Item {
                    id: saveStatus
                    objectName: "settings-status"
                    anchors.left: parent.left
                    anchors.right: footerActions.left
                    anchors.rightMargin: Style.space(12)
                    anchors.verticalCenter: footerActions.verticalCenter
                    height: footerActions.height
                    readonly property bool saving: Plugin.Model.settingsSaving
                    readonly property bool failed: !saving && Plugin.Model.settingsError !== ""
                    visible: saving || failed || settings.saved
                    Plugin.PanelIcon {
                        id: statusIcon
                        objectName: "settings-status-icon"
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: Style.space(14)
                        height: width
                        visible: saveStatus.saving || (!saveStatus.failed && settings.saved)
                        name: saveStatus.saving ? "loader-circle" : "check"
                        foreground: root.barForeground
                        NumberAnimation on rotation {
                            from: 0
                            to: 360
                            duration: 1000
                            loops: Animation.Infinite
                            running: saveStatus.saving && saveStatus.visible && footer.visible
                            onRunningChanged: if (!running) statusIcon.rotation = 0
                        }
                    }
                    Text {
                        objectName: "settings-status-label"
                        anchors.left: parent.left
                        anchors.leftMargin: statusIcon.visible ? statusIcon.width + Style.space(6) : 0
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: saveStatus.saving ? "Saving…" : saveStatus.failed ? "Error" : settings.saved ? "Saved" : ""
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: saveStatus.failed ? Commons.Color.urgent : root.barForeground
                        font.family: root.panelFont
                        font.pixelSize: Style.font.caption
                        Accessible.role: Accessible.StaticText
                        Accessible.name: text
                    }
                }
                Row {
                    id: footerActions
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    spacing: Style.space(8)
                    Plugin.PanelButton {
                        objectName: "settings-cancel"
                        text: "Cancel"
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                        outlined: true
                        enabled: !Plugin.Model.settingsSaving
                        onClicked: root.showUsage()
                    }
                    Plugin.PanelButton {
                        objectName: "settings-save"
                        text: "Save"
                        foreground: Commons.Color.popups.background
                        fontFamily: root.panelFont
                        primary: true
                        enabled: settings.valid && !Plugin.Model.settingsSaving
                        onClicked: settings.save()
                    }
                }
            }
        }
    }
}
