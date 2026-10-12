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
    property bool updatePage: false
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
        updatePage = false
        resetProvider = null
        creditSelection = null
        configurationPage = true
        open()
    }

    function showUsage() {
        if (Plugin.Model.settingsSaving) return
        configurationPage = false
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
        if (Plugin.Model.settingsSaving) return
        if (!configurationPage) configure()
        settings.selectSection("about")
        Qt.callLater(() => settingsNavigation.focusCurrentControl())
    }

    function goBack() {
        if (resetProvider && credits.cancelConfirmation()) return
        showUsage()
    }

    function updateFailureSummary(message) {
        const lower = message.toLowerCase().replace(/\s+/g, " ")
        if (lower.indexOf("checksum") !== -1) {
            if (lower.indexOf("not match") !== -1 || lower.indexOf("mismatch") !== -1) return "Verification failed: checksum mismatch"
            if (lower.indexOf("could not download") !== -1 || lower.indexOf("could not get") !== -1) return "Update failed: checksum unavailable"
            if (lower.indexOf("no valid") !== -1 || lower.indexOf("missing") !== -1 || lower.indexOf("invalid") !== -1) return "Update failed: invalid release checksum"
        }
        if (lower.indexOf("powershell") !== -1 && lower.indexOf("unavailable") !== -1) return "Update failed: PowerShell unavailable"
        if (lower.indexOf("runtime") !== -1 && lower.indexOf("unavailable") !== -1) return "Update failed: updater unavailable"
        if (lower.indexOf("no supported terminal") !== -1 || lower.indexOf("terminal not found") !== -1) return "Update failed: Terminal unavailable"
        if (lower.indexOf("terminal") !== -1 && lower.indexOf("did not respond") !== -1) return "Update failed: Terminal not responding"
        if (lower.indexOf("could not open terminal") !== -1) return "Update failed: could not open Terminal"
        if (lower.indexOf("timed out") !== -1) return "Update failed: updater timed out"
        if (lower.indexOf("download") !== -1) {
            if (lower.indexOf("interrupted") !== -1) return "Download failed: transfer interrupted"
            if (lower.indexOf("failed") !== -1 || lower.indexOf("connection") !== -1) return "Download failed. Check your connection."
        }
        if (lower.indexOf("invalid") !== -1 && (lower.indexOf("progress") !== -1 || lower.indexOf("output") !== -1)) return "Update failed: invalid updater response"
        if (lower.indexOf("without confirmation") !== -1 || lower.indexOf("missing completion") !== -1 || lower.indexOf("before confirming") !== -1) return "Update failed: completion not confirmed"
        return message.split(/\r?\n/).map(line => line.trim()).find(line => line !== "") || "Update failed"
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
        const safeTop = scroller.navigationInset + (root.configurationPage ? root.settingsTabGap : margin)
        const target = item.parent && item.parent.inputItem === item ? item.parent : item
        const top = target.mapToItem(scroller, 0, 0).y
        const bottom = top + target.height
        let nextY = scroller.contentY
        if (top < safeTop || target.height + safeTop + margin > scroller.height)
            nextY += top - safeTop
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
    onOpenedChanged: {
        if (!opened) {
            credits.confirmation = null
            if (!Plugin.Model.settingsSaving) { configurationPage = false; updatePage = false; resetProvider = null; creditSelection = null }
        }
    }

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
        contentHeight: panel.fittedContentHeight(header.height + panel.padding + Style.space(1) + scroller.contentHeight
            + (settingsNavigation.visible && !scroller.supportsMask ? settingsNavigation.height : 0)
            + (footer.visible ? footer.height : updateFooter.visible ? updateFooter.height : -panel.padding), Style.space(680))

        Ui.PanelKeyCatcher {
            id: keyCatcher
            objectName: "panel-key-catcher"
            anchors.fill: parent
            onCloseRequested: {
                if (root.configurationPage || root.resetProvider || root.creditSelection || root.updatePage) root.goBack()
                else root.close()
            }
            onTabRequested: direction => {
                if (root.configurationPage) settingsNavigation.focusCurrentControl()
                else if (root.resetProvider) {
                    if (!credits.focusFirstControl(direction)) backButton.focusFromKeyboard(direction > 0 ? Qt.TabFocusReason : Qt.BacktabFocusReason)
                }
                else if (root.creditSelection) backButton.focusFromKeyboard(direction > 0 ? Qt.TabFocusReason : Qt.BacktabFocusReason)
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
                    tooltipText: "Back to usage (Esc)"
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
                    text: root.configurationPage ? "Settings" : root.updatePage ? "Update AI Status" : "AI Status"
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
                visible: root.configurationPage
                z: 1
                enabled: !Plugin.Model.settingsSaving
                MouseArea {
                    // The fixed strip owns its gaps, even with controls scrolling below.
                    anchors.fill: parent
                    z: -1
                    onClicked: {}
                }
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
                            leadingIconName: modelData.icon
                            alignLeft: true
                            fontFamily: root.panelFont
                            foreground: root.barForeground
                            opacity: 1
                            contentOpacity: enabled ? 1 : 0.35
                            outlined: true
                            // Opaque faces preserve the existing composited theme colors
                            // and keep scrolling text behind each tab's label.
                            color: Qt.tint(Commons.Color.popups.background, settings.section === modelData.key
                                ? Qt.rgba(foreground.r, foreground.g, foreground.b, 0.12)
                                : activeFocus ? Qt.rgba(foreground.r, foreground.g, foreground.b, 0.06) : "transparent")
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
                anchors.top: settingsNavigation.visible && !supportsMask ? settingsNavigation.bottom : divider.bottom
                anchors.bottom: footer.visible ? footer.top : updateFooter.visible ? updateFooter.top : parent.bottom
                anchors.bottomMargin: footer.visible || updateFooter.visible ? 0 : -panel.padding
                x: -panel.padding
                width: parent.width + panel.padding * 2
                contentWidth: width
                readonly property bool supportsMask: GraphicsInfo.api !== GraphicsInfo.Software
                readonly property real navigationInset: settingsNavigation.visible && supportsMask ? settingsNavigation.height : 0
                contentHeight: content.implicitHeight + Style.space(24) + navigationInset
                clip: true
                layer.enabled: navigationInset > 0 && contentY > 0
                layer.effect: ShaderEffect {
                    property var source
                    property real fadeStart: Math.max(0, scroller.navigationInset - root.settingsTabGap) / Math.max(1, scroller.height)
                    property real fadeEnd: (scroller.navigationInset + root.settingsTabGap) / Math.max(1, scroller.height)
                    fragmentShader: Qt.resolvedUrl("scroll-fade.frag.qsb")
                }
                boundsBehavior: Flickable.StopAtBounds
                onContentYChanged: settings.closeSelectors()
                onContentHeightChanged: Qt.callLater(root.revealFocusedControl)

                Column {
                    id: content
                    x: panel.padding
                    y: Style.space(12) + scroller.navigationInset
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
                        actionControl: updateAction
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
                        onBackFocusRequested: backButton.focusProgrammatically()
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
                        visible: root.configurationPage
                        foreground: root.barForeground
                        fontFamily: root.panelFont
                        popupParent: keyCatcher
                        inlineValidation: false
                        onAlertsAdvancedChanged: Qt.callLater(root.revealFocusedControl)
                        onSectionChanged: {
                            scroller.cancelFlick()
                            scroller.contentY = 0
                            Qt.callLater(() => {
                                content.forceLayout()
                                if (!root.configurationPage) return
                                settingsNavigation.revealTab(sectionButtons.itemAt(settings.sections.findIndex(item => item.key === settings.section)))
                                const item = keyCatcher.Window.window ? keyCatcher.Window.window.activeFocusItem : null
                                if (item && !item.visible) settingsNavigation.focusCurrentControl()
                            })
                        }
                    }
                }
            }
            Item {
                id: updateFooter
                objectName: "update-footer"
                anchors.bottom: parent.bottom
                width: parent.width
                height: updateDivider.height + Style.space(12) + updateActions.implicitHeight
                visible: root.updatePage && (!!updates.guide.canUpdate || Plugin.Model.updateRunning || failed || finished)
                readonly property bool failed: !Plugin.Model.updateRunning && Plugin.Model.updateError !== ""
                readonly property bool finished: !Plugin.Model.updateRunning && !failed && Plugin.Model.updateMessage !== ""
                readonly property bool current: finished && Plugin.Model.updateMessage.indexOf("already up to date") !== -1
                Rectangle {
                    id: updateDivider
                    objectName: "update-footer-divider"
                    x: -panel.padding
                    width: parent.width + panel.padding * 2
                    height: Style.space(1)
                    color: divider.color
                }
                Column {
                    id: updateActions
                    y: updateDivider.height + Style.space(12)
                    width: parent.width
                    spacing: Style.space(8)
                    Item {
                        id: updateActionRow
                        objectName: "update-action-row"
                        width: parent.width
                        readonly property bool compact: updateAction.visible && (updateFooter.failed || updateFooter.finished)
                        height: Math.max(updateStatus.visible ? updateStatus.height : 0, updateAction.visible ? updateAction.height : 0)
                        Item {
                            id: updateStatus
                            objectName: "update-status"
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            width: updateActionRow.compact ? Math.max(0, parent.width - updateAction.width - Style.space(8)) : parent.width
                            height: updateFooter.failed ? Math.max(Style.space(16), updateStatusLabel.implicitHeight) : Style.space(16)
                            visible: Plugin.Model.updateRunning || updateFooter.failed || updateFooter.finished
                            Plugin.PanelIcon {
                                id: updateStatusIcon
                                objectName: "update-status-icon"
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                width: Style.space(16)
                                height: width
                                visible: Plugin.Model.updateRunning || updateFooter.failed || updateFooter.finished
                                name: Plugin.Model.updateRunning ? "loader-circle" : updateFooter.failed ? "info" : "check"
                                foreground: updateFooter.failed ? "#f5a3a3" : Commons.Color.accent
                                Accessible.description: updateFooter.failed ? Plugin.Model.updateError : ""
                                NumberAnimation on rotation {
                                    from: 0
                                    to: 360
                                    duration: 1000
                                    loops: Animation.Infinite
                                    running: Plugin.Model.updateRunning && updateFooter.visible
                                    onRunningChanged: if (!running) updateStatusIcon.rotation = 0
                                }
                            }
                            Text {
                                id: updateStatusLabel
                                objectName: "update-status-label"
                                anchors.left: parent.left
                                anchors.leftMargin: updateStatusIcon.visible ? updateStatusIcon.width + Style.space(6) : 0
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                text: Plugin.Model.updateRunning ? (Plugin.Model.updateStage === "checking" ? "Checking for updates…" : "Opening updater…") : updateFooter.failed ? root.updateFailureSummary(Plugin.Model.updateError) : updateFooter.current ? "Up to date" : "Updater opened"
                                textFormat: Text.PlainText
                                wrapMode: updateFooter.failed ? Text.WordWrap : Text.NoWrap
                                elide: updateFooter.failed ? Text.ElideNone : Text.ElideRight
                                color: updateFooter.failed ? "#f5a3a3" : Commons.Color.accent
                                font.family: root.panelFont
                                font.pixelSize: Style.font.body
                                Accessible.role: Accessible.StaticText
                                Accessible.name: text
                                Accessible.description: updateFooter.failed ? Plugin.Model.updateError : ""
                            }
                        }
                        Plugin.PanelButton {
                            id: updateAction
                            objectName: "update-action"
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: updateActionRow.compact ? implicitWidth : parent.width
                            implicitHeight: Style.space(34)
                            visible: !!updates.guide.canUpdate && !Plugin.Model.updateRunning
                            enabled: !Plugin.Model.updateRunning
                            text: updateFooter.finished ? "Done" : updateFooter.failed ? "Retry" : "Update now"
                            foreground: Commons.Color.accent
                            fontFamily: root.panelFont
                            alignLeft: true
                            outlined: true
                            Accessible.name: text
                            onClicked: {
                                if (updateFooter.finished) root.showUsage()
                                else Plugin.Model.startUpdate()
                            }
                        }
                    }
                    Rectangle {
                        id: updateProgress
                        objectName: "update-progress"
                        width: parent.width
                        height: Style.space(3)
                        radius: height / 2
                        visible: Plugin.Model.updateRunning
                        color: Qt.rgba(root.barForeground.r, root.barForeground.g, root.barForeground.b, 0.12)
                        clip: true
                        property real phase: 0
                        readonly property bool animating: progressAnimation.running
                        Accessible.role: Accessible.ProgressBar
                        Accessible.name: Plugin.Model.updateStage === "checking" ? "Checking for updates" : "Opening updater"
                        Rectangle {
                            x: (parent.width + width) * updateProgress.phase - width
                            width: parent.width * 0.3
                            height: parent.height
                            radius: parent.radius
                            color: Commons.Color.accent
                        }
                        NumberAnimation {
                            id: progressAnimation
                            target: updateProgress
                            property: "phase"
                            from: 0
                            to: 1
                            duration: 1200
                            loops: Animation.Infinite
                            running: Plugin.Model.updateRunning && updateFooter.visible
                        }
                    }
                }
            }
            Item {
                id: footer
                objectName: "settings-footer"
                anchors.bottom: parent.bottom
                width: parent.width
                height: footerDivider.height + panel.padding + footerActions.height + (footerFeedback.visible ? footerFeedback.height + Style.space(8) : 0)
                visible: root.configurationPage
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
                    anchors.topMargin: panel.padding
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
                        visible: settings.validationSection !== "" && (settings.validationSection !== settings.section || (settings.section === "alerts" && !settings.alertsAdvanced))
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
