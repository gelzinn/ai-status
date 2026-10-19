import QtQuick
import qs.Commons
import qs.Commons as Commons
import "." as Plugin

Column {
    id: root
    property color foreground: "white"
    property string fontFamily: Style.font.family
    property var order: []
    property var availableProviders: []
    property var rememberedBarItems: ({})
    property var enabledProviders: []
    property var display: ({})
    property string iconMode: "bot"
    property string usageDisplay: "used"
    property bool showTotal: false
    property int refreshIntervalMinutes: 5
    property var selected: ({})
    property var selectedItems: []
    property var alertSettings: ({enabled: true, thresholds: [80,95,100], recovery: true, muted_until: 0, rules: [], quiet_hours: {start: "", end: ""}, work_hours: {start: "", end: ""}, recent_only: false})
    property string alertThresholds: "80,95,100"
    property string alertQuietHours: ""
    property string alertWorkHours: ""
    property var alertRuleTexts: ({})
    property bool alertsAdvanced: false
    property real alertNow: Date.now() / 1000
    readonly property bool alertsPaused: alertSettings.muted_until > alertNow
    readonly property var thresholdValues: validThresholds(alertThresholds) ? parseThresholds(alertThresholds) : []
    property var alertRuleTarget: null
    readonly property var ruleSelection: alertRuleTarget || selected
    readonly property string selectedAlertKey: ruleSelection.provider + "\u001f" + ruleSelection.metric
    readonly property var selectedAlertRule: (alertSettings.rules || []).find(rule => rule.connection_id === ruleSelection.provider && rule.metric === ruleSelection.metric) || null
    readonly property string selectedAlertThresholds: alertRuleTexts[selectedAlertKey] !== undefined ? alertRuleTexts[selectedAlertKey] : selectedAlertRule ? selectedAlertRule.thresholds.join(",") : ""
    readonly property var invalidAlertRules: (alertSettings.rules || []).filter(rule => !validThresholds(alertRuleTexts[rule.connection_id + "\u001f" + rule.metric] !== undefined ? alertRuleTexts[rule.connection_id + "\u001f" + rule.metric] : rule.thresholds.join(",")))
    readonly property string ruleSelectionLabel: ruleLabel(ruleSelection.provider, ruleSelection.metric)
    property Item popupParent: parent
    property Item providerSelector: null
    readonly property bool selectionOpen: iconSelector.popupOpen || usageDisplaySelector.popupOpen || (!!providerSelector && providerSelector.popupOpen)
    property bool saved: false
    property bool inlineValidation: true
    property string section: "general"
    readonly property var sections: [
        {key: "general", label: "General", icon: "settings"},
        {key: "alerts", label: "Alerts", icon: "bell"},
        {key: "providers", label: "Providers", icon: "server"},
        {key: "guide", label: "Guide", icon: "book-open"},
        {key: "about", label: "About", icon: "info"}
    ]
    readonly property string validationSection: enabledProviders.length === 0 ? "providers"
        : !Object.keys(display).some(key => display[key]) || ["used", "remaining"].indexOf(usageDisplay) === -1 || !validRefreshInterval(refreshIntervalMinutes) ? "general"
        : !validItems ? "providers"
        : !valid ? "alerts" : ""
    readonly property string validationMessage: validationSection === "providers" ? enabledProviders.length === 0
            ? "Enable at least one provider in Providers."
            : "Choose at least one bar item from an active provider in Providers."
        : validationSection === "general" ? !validRefreshInterval(refreshIntervalMinutes) ? "Choose a refresh interval from 5 to 60 minutes in General."
            : !Object.keys(display).some(key => display[key]) || ["used", "remaining"].indexOf(usageDisplay) === -1 ? "Choose a usage display and at least one bar text field in General."
            : "Choose at least one bar item from an enabled provider in Providers."
        : validationSection === "alerts" ? "Review alert levels and schedules in Alerts."
        : ""
    readonly property var choices: {
        const items = []
        const providerIds = (Plugin.Model.snapshot.settings || {}).providerIds || {}
        const providers = Plugin.Model.snapshot.providers || []
        const connections = order.filter(name => enabledProviders.indexOf(name) !== -1)
            .concat(enabledProviders.filter(name => order.indexOf(name) === -1))
        // Keep accounts of the same provider together, retaining provider order.
        const families = []
        for (const name of connections) {
            const entry = providers.find(p => p.id === name)
            const family = providerIds[name] || (entry && entry.providerId) || name
            if (families.indexOf(family) === -1) families.push(family)
        }
        let grouped = []
        for (const family of families) {
            grouped = grouped.concat(connections.filter(name => {
                const entry = providers.find(p => p.id === name)
                return (providerIds[name] || (entry && entry.providerId) || name) === family
            }))
        }
        const titles = []
        for (const name of grouped) {
            const entries = providers.filter(p => p.id === name)
            if (entries.length === 0)
                entries.push({idx: 0, name: root.providerName(name), metrics: []})
            for (const entry of entries) {
                titles.push(entry.name)
            }
        }
        const occurrences = {}
        for (const name of grouped) {
            const entries = providers.filter(p => p.id === name)
            if (entries.length === 0)
                entries.push({idx: 0, name: root.providerName(name), metrics: []})
            for (const entry of entries) {
                occurrences[entry.name] = (occurrences[entry.name] || 0) + 1
                const title = entry.name + (titles.filter(value => value === entry.name).length > 1 ? " · Account " + occurrences[entry.name] : "")
                const group = {provider: name, idx: entry.idx, groupKey: name + "/" + entry.idx,
                    groupLabel: title, groupLogoSource: root.providerLogo(name, entry)}
                for (const metric of entry.metrics) {
                    items.push(Object.assign({}, group, {metric: metric.key, label: root.limitLabel(metric)}))
                }
                if (entry.metrics.length === 0)
                    items.push(Object.assign({}, group, {metric: "rolling", label: "Usage"}))
            }
        }
        // Keep unavailable pinned limits editable without silently replacing them.
        for (const pinned of selectedItems) {
            if (!items.some(item => sameItem(item, pinned)))
                items.push(Object.assign({}, pinned, {groupKey: pinned.provider + "/" + pinned.idx,
                    groupLabel: providerName(pinned.provider), groupLogoSource: order.indexOf(pinned.provider) !== -1 ? providerLogo(pinned.provider, null) : "",
                    label: pinned.metric + " (unavailable)"}))
        }
        return items
    }
    readonly property var selectedChoice: choices.find(item => item.provider === selected.provider && item.idx === selected.idx && item.metric === selected.metric) || null
    readonly property string selectedLabel: selectedChoice ? selectedChoice.groupLabel + " · " + selectedChoice.label : "Choose a provider and limit"
    readonly property bool validItems: selectedItems.length > 0 && selectedItems.every(item => enabledProviders.indexOf(item.provider) !== -1 && availableProviders.indexOf(item.provider) !== -1 && choices.some(choice => sameItem(choice, item)))
    readonly property bool valid: enabledProviders.length > 0 && Object.keys(display).some(key => display[key]) && ["used", "remaining"].indexOf(usageDisplay) !== -1 && validRefreshInterval(refreshIntervalMinutes) && validItems && validThresholds(alertThresholds) && validHours(alertQuietHours) && validHours(alertWorkHours) && (alertSettings.rules || []).every(rule => validThresholds(alertRuleTexts[rule.connection_id + "\u001f" + rule.metric] !== undefined ? alertRuleTexts[rule.connection_id + "\u001f" + rule.metric] : rule.thresholds.join(",")))
    spacing: Style.space(16)
    enabled: !Plugin.Model.settingsSaving
    onOrderChanged: saved = false
    onEnabledProvidersChanged: saved = false
    onDisplayChanged: saved = false
    onIconModeChanged: saved = false
    onUsageDisplayChanged: saved = false
    onRefreshIntervalMinutesChanged: saved = false
    onSelectedChanged: {
        saved = false; alertRuleTarget = null
        if (selected.provider && selected.metric && (!selectedItems.length || !sameItem(selectedItems[0], selected))) {
            selectedItems = [itemIdentity(selected)].concat(selectedItems.slice(1).filter(item => !sameItem(item, selected)))
            normalizeBarItems()
        }
    }
    onSelectedItemsChanged: saved = false
    onAlertSettingsChanged: saved = false
    onAlertThresholdsChanged: saved = false
    onAlertRuleTextsChanged: saved = false
    onAlertQuietHoursChanged: saved = false
    onAlertWorkHoursChanged: saved = false
    onVisibleChanged: if (!visible) closeSelectors()
    onSectionChanged: closeSelectors()

    Connections {
        target: Plugin.Model
        function onSettingsSaved() { root.saved = true }
    }
    Timer {
        interval: 1000
        repeat: true
        running: root.visible && root.section === "alerts"
        onTriggered: root.alertNow = Date.now() / 1000
    }

    function providerLogo(name, entry) {
        return entry && entry.logoPath ? "file://" + entry.logoPath : Qt.resolvedUrl("../assets/providers/" + (((Plugin.Model.snapshot.settings || {}).providerIds || {})[name] || name) + ".png")
    }

    function providerName(name) {
        return ((Plugin.Model.snapshot.settings || {}).names || {})[name] || name
    }

    function limitLabel(metric) {
        const shortNames = {"Rolling Usage": "Rolling", "Daily Usage": "Daily", "Weekly Usage": "Weekly", "Monthly Usage": "Monthly",
            "Rolling Remaining": "Rolling", "Daily Remaining": "Daily", "Weekly Remaining": "Weekly", "Monthly Remaining": "Monthly",
            "Cursor Models included quota": "Cursor Models", "Other Models included quota": "Other Models",
            "Cursor Models included quota remaining": "Cursor Models", "Other Models included quota remaining": "Other Models",
            "On-demand spend this billing cycle": "On-demand spend"}
        const label = shortNames[metric.name] || metric.name
        // Key suffixes may be full names or opaque IDs, not display labels.
        // Only legacy period metrics use a suffix as a model qualifier.
        const parts = metric.key.split(":")
        const qualifier = parts.slice(1).join(":")
        const periodName = {rolling: "Rolling Usage", daily: "Daily Usage", weekly: "Weekly Usage", monthly: "Monthly Usage"}[parts[0]]
        const remainingName = periodName ? periodName.replace("Usage", "Remaining") : ""
        return qualifier && (metric.name === periodName || metric.name === remainingName) && qualifier !== metric.name ? label + " · " + qualifier : label
    }

    function closeSelectors() {
        iconSelector.dismiss()
        usageDisplaySelector.dismiss()
        if (providerSelector) providerSelector.dismiss()
        providerSelector = null
    }

    function providerMenuChanged(selector) {
        if (selector.popupOpen) {
            iconSelector.dismiss()
            usageDisplaySelector.dismiss()
            if (providerSelector && providerSelector !== selector) providerSelector.dismiss()
            providerSelector = selector
        } else if (providerSelector === selector) providerSelector = null
    }

    function begin() {
        section = "general"
        const settings = Plugin.Model.snapshot.settings || {}
        availableProviders = (settings.order || []).slice()
        order = availableProviders.concat((settings.items || []).map(item => item.provider)
            .filter((name, index, names) => availableProviders.indexOf(name) === -1 && names.indexOf(name) === index))
        enabledProviders = (settings.enabled || []).slice()
        rememberedBarItems = {}
        display = Object.assign({}, settings.display || {})
        iconMode = settings.iconMode || "bot"
        usageDisplay = settings.usageDisplay === "remaining" ? "remaining" : "used"
        showTotal = settings.showTotal === true
        refreshIntervalMinutes = validRefreshInterval(settings.refreshIntervalMinutes) ? settings.refreshIntervalMinutes : 5
        selectedItems = (settings.items || []).map(itemIdentity)
        selected = selectedItems.length ? Object.assign({}, selectedItems[0]) : Object.assign({}, Plugin.Model.snapshot.selected)
        normalizeBarItems()
        alertSettings = JSON.parse(JSON.stringify(settings.notifications || {enabled: true, thresholds: [80,95,100], recovery: true, muted_until: 0, rules: [], quiet_hours: {start: "", end: ""}, work_hours: {start: "", end: ""}, recent_only: false}))
        alertThresholds = alertSettings.thresholds.join(",")
        alertRuleTexts = {}
        alertRuleTarget = null
        alertQuietHours = hoursText("quiet_hours")
        alertWorkHours = hoursText("work_hours")
        alertsAdvanced = false
        alertNow = Date.now() / 1000
        closeSelectors()
        saved = false
        Plugin.Model.settingsError = ""
    }

    function focusFirstControl() {
        if (section === "about") { aboutContent.focusFirstControl(); return }
        const first = section === "alerts" ? !validThresholds(alertThresholds) ? globalThresholdField.inputItem
                : !validHours(alertQuietHours) ? quietHoursField.inputItem
                : !validHours(alertWorkHours) ? workHoursField.inputItem
                : invalidAlertRules.length ? ruleThresholdField.inputItem : alertEnabled
            : section === "guide" ? null
            : section === "providers" && providerRows.count > 0 ? providerRows.itemAt(0).firstControl
            : !validRefreshInterval(refreshIntervalMinutes) ? refreshIntervalSlider
            : !Object.keys(display).some(key => display[key]) || ["used", "remaining"].indexOf(usageDisplay) === -1 ? usageDisplaySelector
            : refreshIntervalSlider
        if (first) first.forceActiveFocus(Qt.TabFocusReason)
    }

    function selectSection(key) {
        if (Plugin.Model.settingsSaving || !sections.some(item => item.key === key)) return
        closeSelectors()
        section = key
        if (key === "alerts" && !valid) alertsAdvanced = true
        if (key === "alerts" && invalidAlertRules.length) reviewRule(invalidAlertRules[0])
        if (key === "alerts" && validationSection === "alerts") Qt.callLater(() => focusFirstControl())
    }

    function toggleProvider(name) {
        if (Plugin.Model.settingsSaving || availableProviders.indexOf(name) === -1) return
        const activating = enabledProviders.indexOf(name) === -1
        if (!activating) rememberBarChoices(name)
        enabledProviders = activating ? enabledProviders.concat([name]) : enabledProviders.filter(item => item !== name)
        if (!activating) selectedItems = selectedItems.filter(item => item.provider !== name)
        normalizeBarItems()
    }

    function sameItem(left, right) {
        return left.provider === right.provider && left.idx === right.idx && left.metric === right.metric
    }

    function itemIdentity(item) {
        return {provider: item.provider, idx: item.idx, metric: item.metric}
    }

    function toggleItem(choice) {
        if (Plugin.Model.settingsSaving) return
        if (enabledProviders.indexOf(choice.provider) === -1 && !selectedItems.some(item => sameItem(item, choice))) return
        selectedItems = selectedItems.some(item => sameItem(item, choice))
            ? selectedItems.filter(item => !sameItem(item, choice))
            : selectedItems.concat([itemIdentity(choice)])
        normalizeBarItems()
        const remembered = Object.assign({}, rememberedBarItems)
        remembered[choice.provider] = selectedItems.filter(item => item.provider === choice.provider).map(itemIdentity)
        rememberedBarItems = remembered
    }

    function normalizeBarItems() {
        const rank = name => order.indexOf(name) === -1 ? order.length : order.indexOf(name)
        selectedItems = selectedItems.map((item, index) => ({item: item, index: index}))
            .sort((left, right) => rank(left.item.provider) - rank(right.item.provider) || left.index - right.index)
            .map(entry => entry.item)
        selected = selectedItems.length ? Object.assign({}, selectedItems[0]) : {}
    }

    function rememberBarChoices(name) {
        const items = selectedItems.filter(item => item.provider === name).map(itemIdentity)
        if (!items.length) return
        const remembered = Object.assign({}, rememberedBarItems)
        remembered[name] = items
        rememberedBarItems = remembered
    }

    function providerChoices(name) {
        const live = choices.filter(choice => choice.provider === name)
        const missing = (rememberedBarItems[name] || []).filter(item => !live.some(choice => sameItem(item, choice)))
        return live.concat(missing.map(item => Object.assign({}, item, {
            groupLabel: providerName(name), groupLogoSource: providerLogo(name, null),
            label: item.metric + " (unavailable)"
        })))
    }

    function toggleProviderBar(name) {
        if (Plugin.Model.settingsSaving) return
        if (selectedItems.some(item => item.provider === name)) {
            rememberBarChoices(name)
            selectedItems = selectedItems.filter(item => item.provider !== name)
        } else {
            if (enabledProviders.indexOf(name) === -1 || availableProviders.indexOf(name) === -1) return
            const first = choices.find(item => item.provider === name)
            const remembered = rememberedBarItems[name] || []
            const restored = remembered.length ? remembered : (first ? [itemIdentity(first)] : [])
            selectedItems = selectedItems.concat(restored)
        }
        normalizeBarItems()
    }

    function moveProvider(index, direction) {
        if (Plugin.Model.settingsSaving || index < 0 || index >= order.length || (direction !== -1 && direction !== 1)) return
        const next = order.slice()
        const other = index + direction
        if (other < 0 || other >= next.length) return
        closeSelectors()
        const value = next[index]
        next[index] = next[other]
        next[other] = value
        order = next
        normalizeBarItems()
        Qt.callLater(() => {
            if (!root.visible || root.section !== "providers") return
            const row = providerRows.itemAt(other)
            if (row) row.focusMove(direction)
        })
    }

    function save() {
        if (!valid) return
        saved = false
        Plugin.Model.saveSettings({
            enabled: order.filter(name => enabledProviders.indexOf(name) !== -1),
            display: display,
            iconMode: iconMode,
            usageDisplay: usageDisplay,
            showTotal: showTotal,
            refreshIntervalMinutes: refreshIntervalMinutes,
            notifications: Object.assign({}, alertSettings, {
                thresholds: parseThresholds(alertThresholds),
                rules: (alertSettings.rules || []).map(rule => Object.assign({}, rule, {
                    thresholds: alertRuleTexts[rule.connection_id + "\u001f" + rule.metric] !== undefined ? parseThresholds(alertRuleTexts[rule.connection_id + "\u001f" + rule.metric]) : rule.thresholds
                }))
            }),
            selected: {provider: selected.provider, idx: selected.idx, metric: selected.metric},
            items: selectedItems.map(itemIdentity)
        })
    }

    component Label: Text {
        width: parent.width
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        wrapMode: Text.WordWrap
    }
    component SectionHeading: Column {
        id: heading
        property string title: ""
        property string description: ""
        width: parent.width
        spacing: Style.space(4)
        Label {
            text: heading.title
            font.bold: true
        }
        Label {
            visible: text !== ""
            text: heading.description
            opacity: 0.5
            font.pixelSize: Style.font.caption
        }
    }
    component Button: Plugin.PanelButton {
        foreground: root.foreground
        fontFamily: root.fontFamily
    }
    component ProviderCheckbox: Button {
        id: checkbox
        property bool checked: false
        width: Style.space(28)
        Accessible.role: Accessible.CheckBox
        Accessible.checked: checked
        Rectangle {
            objectName: checkbox.objectName + "-indicator"
            anchors.centerIn: parent
            width: Style.space(14)
            height: width
            radius: Style.space(3)
            color: checkbox.checked ? checkbox.foreground : "transparent"
            border.width: checkbox.checked ? 0 : 1
            border.color: Qt.rgba(checkbox.foreground.r, checkbox.foreground.g, checkbox.foreground.b, 0.3)
            Plugin.PanelIcon {
                anchors.fill: parent
                visible: checkbox.checked
                name: "check"
                foreground: Commons.Color.popups.background
            }
        }
    }
    component Field: Rectangle {
        id: field
        property string text: ""
        property string label: ""
        property alias inputItem: input
        signal edited(string value)
        width: parent.width
        height: Style.space(36)
        radius: Style.cornerRadius
        color: "transparent"
        border.width: 1
        border.color: input.activeFocus ? root.foreground : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.25)
        TextInput {
            id: input
            anchors.fill: parent
            anchors.margins: Style.space(8)
            text: field.text
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            selectByMouse: true
            activeFocusOnTab: true
            clip: true
            Accessible.name: field.label
            onTextEdited: field.edited(text)
        }
    }

    function validThresholds(value) {
        if (!value.trim()) return true
        const values = value.split(",")
        return values.length > 0 && values.every(item => /^\d+$/.test(item.trim()) && Number(item) > 0 && Number(item) <= 100) && new Set(values.map(Number)).size === values.length
    }
    function validRefreshInterval(value) {
        return typeof value === "number" && value >= 5 && value <= 60 && value % 5 === 0
    }
    function parseThresholds(value) {
        return value.trim() ? value.split(",").map(Number).sort((a, b) => a - b) : []
    }
    function updateThreshold(index, value) {
        const next = thresholdValues.slice()
        next[index] = Math.max(index > 0 ? next[index - 1] + 1 : 1, Math.min(index + 1 < next.length ? next[index + 1] - 1 : 100, Math.round(value)))
        alertThresholds = next.join(",")
    }
    function addThreshold() {
        const next = thresholdValues.slice()
        let value = 80
        while (next.indexOf(value) !== -1 && value > 1) value--
        if (next.indexOf(value) !== -1) {
            value = 1
            while (next.indexOf(value) !== -1 && value < 100) value++
        }
        if (next.indexOf(value) === -1) alertThresholds = next.concat([value]).sort((a, b) => a - b).join(",")
    }
    function removeThreshold(index) {
        if (!thresholdValues.length) return
        alertThresholds = thresholdValues.filter((value, position) => position !== index).join(",")
        Qt.callLater(() => addLevel.forceActiveFocus(Qt.TabFocusReason))
    }
    function setAlert(key, value) {
        const next = Object.assign({}, alertSettings)
        next[key] = value
        alertSettings = next
    }
    function setRule(key, value) {
        const rules = (alertSettings.rules || []).filter(rule => rule.connection_id !== ruleSelection.provider || rule.metric !== ruleSelection.metric)
        const rule = Object.assign({}, selectedAlertRule || {connection_id: ruleSelection.provider, metric: ruleSelection.metric, thresholds: alertSettings.thresholds, enabled: true})
        rule[key] = value
        setAlert("rules", rules.concat([rule]))
    }
    function setRuleText(value) {
        const texts = Object.assign({}, alertRuleTexts)
        texts[selectedAlertKey] = value
        alertRuleTexts = texts
    }
    function ruleLabel(connection, metric) {
        if (!connection || !metric) return "Choose a provider and limit in Providers."
        const choice = choices.find(item => item.provider === connection && item.metric === metric)
        return choice ? choice.groupLabel + " · " + choice.label : providerName(connection) + " · " + metric
    }
    function reviewRule(rule) {
        alertRuleTarget = {provider: rule.connection_id, metric: rule.metric}
        alertsAdvanced = true
        Qt.callLater(() => {
            if (root.visible && root.section === "alerts") ruleThresholdField.inputItem.forceActiveFocus(Qt.TabFocusReason)
        })
    }
    function hoursText(key) {
        const hours = alertSettings[key] || {start: "", end: ""}
        return hours.start ? hours.start + "-" + hours.end : ""
    }
    function validHours(value) {
        if (!value) return true
        if (!/^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$/.test(value)) return false
        const parts = value.split("-")
        return parts[0] !== parts[1]
    }
    function setHours(key, value) {
        if (key === "quiet_hours") alertQuietHours = value
        else alertWorkHours = value
        const parts = value ? value.split("-") : ["", ""]
        setAlert(key, {start: parts[0], end: parts[1] || ""})
    }

    Column {
        objectName: "settings-refresh-interval"
        visible: root.section === "general"
        width: parent.width
        spacing: Style.space(8)
        SectionHeading {
            title: "Automatic refresh · " + root.refreshIntervalMinutes + " min"
            description: "Automatic usage refresh. Provider cooldowns still apply."
        }
        Plugin.PanelSlider {
            id: refreshIntervalSlider
            objectName: "refresh-interval-slider"
            width: parent.width
            foreground: root.foreground
            from: 5
            to: 60
            stepSize: 5
            value: root.refreshIntervalMinutes
            Accessible.name: "Automatic usage refresh interval"
            Accessible.description: root.refreshIntervalMinutes + " minutes. From 5 to 60 minutes in 5-minute steps."
            onMoved: root.refreshIntervalMinutes = Math.round(value)
        }
        Row {
            width: parent.width
            Label { width: parent.width / 2; text: "5 min"; opacity: 0.5; font.pixelSize: Style.font.caption }
            Label { width: parent.width / 2; text: "60 min"; horizontalAlignment: Text.AlignRight; opacity: 0.5; font.pixelSize: Style.font.caption }
        }
    }
    Column {
        objectName: "settings-usage-display"
        visible: root.section === "general"
        width: parent.width
        spacing: Style.space(8)
        SectionHeading { title: "Usage display" }
        Plugin.PanelSelect {
            id: usageDisplaySelector
            objectName: "usage-display"
            width: parent.width
            text: root.usageDisplay === "remaining" ? "Remaining" : "Used"
            foreground: root.foreground
            fontFamily: root.fontFamily
            popupParent: root.popupParent
            choices: [{value: "used", label: "Used"}, {value: "remaining", label: "Remaining"}]
            currentIndex: ["used", "remaining"].indexOf(root.usageDisplay)
            onPopupOpenChanged: if (popupOpen) iconSelector.dismiss()
            onActivated: index => root.usageDisplay = choices[index].value
        }
        Plugin.PanelSwitch {
            objectName: "show-total"
            width: parent.width
            text: "Show total"
            foreground: root.foreground
            fontFamily: root.fontFamily
            checked: root.showTotal
            onToggled: root.showTotal = checked
        }
    }
    Column {
        visible: root.section === "general"
        width: parent.width
        spacing: Style.space(4)
        SectionHeading { title: "Bar display" }
        Repeater {
            model: [
                {key: "show_provider", label: "Provider name"},
                {key: "show_model", label: "Model / plan"},
                {key: "show_metric", label: "Limit name"},
                {key: "show_pct", label: "Usage value"}
            ]
            delegate: Button {
                required property var modelData
                objectName: "display-" + modelData.key
                width: parent.width
                alignLeft: true
                text: (root.display[modelData.key] ? "[x]  " : "[ ]  ") + modelData.label
                Accessible.role: Accessible.CheckBox
                Accessible.checked: !!root.display[modelData.key]
                onClicked: {
                    const next = Object.assign({}, root.display)
                    next[modelData.key] = !next[modelData.key]
                    root.display = next
                }
            }
        }
        Plugin.PanelSelect {
            id: iconSelector
            objectName: "icon-mode"
            width: parent.width
            text: "Icon: " + ({off: "None", bot: "Bot", logo: "Provider logo"}[root.iconMode])
            foreground: root.foreground
            fontFamily: root.fontFamily
            popupParent: root.popupParent
            choices: [{value: "off", label: "None"}, {value: "bot", label: "Bot"}, {value: "logo", label: "Provider logo"}]
            currentIndex: ["off", "bot", "logo"].indexOf(root.iconMode)
            onPopupOpenChanged: if (popupOpen) usageDisplaySelector.dismiss()
            onActivated: index => root.iconMode = choices[index].value
        }
    }
    Column {
        objectName: "settings-section-alerts"
        visible: root.section === "alerts"
        width: parent.width
        spacing: Style.space(16)
        SectionHeading {
            title: "Quota notifications"
            description: "Get notified as your quota is consumed."
        }
        Plugin.PanelSwitch {
            id: alertEnabled
            objectName: "alerts-enabled"
            width: parent.width
            text: "Desktop quota notifications"
            foreground: root.foreground
            fontFamily: root.fontFamily
            checked: !!root.alertSettings.enabled
            onToggled: root.setAlert("enabled", checked)
        }
        Plugin.PanelSwitch {
            objectName: "alerts-mute"
            width: parent.width
            text: "Pause notifications for 1 hour"
            foreground: root.foreground
            fontFamily: root.fontFamily
            checked: root.alertsPaused
            onToggled: {
                root.alertNow = Date.now() / 1000
                root.setAlert("muted_until", checked ? root.alertNow + 3600 : 0)
            }
        }
        Column {
            width: parent.width
            spacing: Style.space(8)
            SectionHeading {
                title: "Notify at"
                description: root.thresholdValues.length ? "Each level sends one notification when usage reaches it." : "Add a level to receive usage notifications."
            }
            Repeater {
                model: root.thresholdValues.length
                delegate: Row {
                    required property int index
                    width: parent.width
                    spacing: Style.space(8)
                    Label {
                        width: Style.space(42)
                        height: Style.space(30)
                        verticalAlignment: Text.AlignVCenter
                        text: root.thresholdValues[parent.index] + "%"
                    }
                    Plugin.PanelSlider {
                        objectName: "alert-threshold-slider-" + parent.index
                        width: parent.width - Style.space(42 + 30 + 16)
                        value: root.thresholdValues[parent.index]
                        foreground: root.foreground
                        Accessible.name: "Notification level " + (parent.index + 1)
                        onMoved: root.updateThreshold(parent.index, value)
                    }
                    Button {
                        width: Style.space(30)
                        text: "−"
                        objectName: "alert-threshold-remove-" + parent.index
                        Accessible.name: "Remove notification level " + (parent.index + 1)
                        enabled: root.thresholdValues.length > 0
                        outlined: true
                        onClicked: root.removeThreshold(parent.index)
                    }
                }
            }
            Button {
                id: addLevel
                objectName: "alert-threshold-add"
                text: "Add level"
                outlined: true
                enabled: root.thresholdValues.length < 100
                onClicked: root.addThreshold()
            }
            Field {
                id: globalThresholdField
                objectName: "alert-thresholds"
                visible: !root.validThresholds(root.alertThresholds)
                text: root.alertThresholds
                label: "Quota alert percentages"
                onEdited: value => root.alertThresholds = value
            }
            Label { visible: !root.validThresholds(root.alertThresholds); text: "Use distinct whole percentages from 1 to 100."; color: Commons.Color.urgent }
        }
        Button {
            objectName: "alerts-recovery"
            width: parent.width
            alignLeft: true
            multiline: true
            text: (root.alertSettings.recovery ? "[x]  " : "[ ]  ") + "Notify when capacity recovers"
            Accessible.role: Accessible.CheckBox
            Accessible.checked: !!root.alertSettings.recovery
            onClicked: root.setAlert("recovery", !root.alertSettings.recovery)
        }
        Button {
            objectName: "alerts-advanced-toggle"
            width: parent.width
            alignLeft: true
            text: "Advanced"
            trailingIconName: root.alertsAdvanced ? "arrow-up" : "chevron-down"
            outlined: true
            onClicked: root.alertsAdvanced = !root.alertsAdvanced
        }
        Column {
            objectName: "alerts-advanced"
            visible: root.alertsAdvanced
            width: parent.width
            spacing: Style.space(16)
            Button {
                objectName: "alerts-recent_only"
                width: parent.width
                alignLeft: true
                multiline: true
                text: (root.alertSettings.recent_only ? "[x]  " : "[ ]  ") + "Recovery only for accounts active in the last 24h"
                Accessible.role: Accessible.CheckBox
                Accessible.checked: !!root.alertSettings.recent_only
                onClicked: root.setAlert("recent_only", !root.alertSettings.recent_only)
            }
            Column {
                width: parent.width
                spacing: Style.space(8)
                SectionHeading { title: "Quiet hours"; description: "Local time, HH:MM-HH:MM. Leave blank for none." }
                Field { id: quietHoursField; objectName: "alerts-quiet-hours"; text: root.alertQuietHours; label: "Quiet hours"; onEdited: value => root.setHours("quiet_hours", value) }
                Label { visible: !root.validHours(root.alertQuietHours); text: "Enter two different times, for example 22:00-08:00."; color: Commons.Color.urgent }
            }
            Column {
                width: parent.width
                spacing: Style.space(8)
                SectionHeading { title: "Working hours"; description: "Local time, HH:MM-HH:MM. Leave blank for all day." }
                Field { id: workHoursField; objectName: "alerts-work-hours"; text: root.alertWorkHours; label: "Working hours"; onEdited: value => root.setHours("work_hours", value) }
                Label { visible: !root.validHours(root.alertWorkHours); text: "Enter two different times, for example 09:00-18:00."; color: Commons.Color.urgent }
            }
            Column {
                width: parent.width
                spacing: Style.space(8)
                SectionHeading { title: "Per-limit rule"; description: root.ruleSelectionLabel }
                Repeater {
                    model: root.invalidAlertRules.filter(rule => rule.connection_id !== root.ruleSelection.provider || rule.metric !== root.ruleSelection.metric)
                    delegate: Button {
                        required property var modelData
                        width: parent.width
                        text: "Review " + root.ruleLabel(modelData.connection_id, modelData.metric)
                        objectName: "alerts-review-rule-" + modelData.connection_id + "-" + modelData.metric
                        outlined: true
                        multiline: true
                        trailingIconName: "arrow-right"
                        alignLeft: true
                        onClicked: root.reviewRule(modelData)
                    }
                }
                Button {
                    visible: !!root.alertRuleTarget && (root.ruleSelection.provider !== root.selected.provider || root.ruleSelection.metric !== root.selected.metric) && root.invalidAlertRules.length === 0
                    width: parent.width
                    text: "Edit rule for " + root.selectedLabel
                    outlined: true
                    multiline: true
                    trailingIconName: "arrow-right"
                    alignLeft: true
                    onClicked: root.alertRuleTarget = null
                }
                Button {
                    objectName: "alert-rule-customize"
                    width: parent.width
                    alignLeft: true
                    multiline: true
                    text: (root.selectedAlertRule ? "[x]  " : "[ ]  ") + "Use custom levels for this limit"
                    Accessible.role: Accessible.CheckBox
                    Accessible.checked: !!root.selectedAlertRule
                    onClicked: {
                        if (root.selectedAlertRule) {
                            root.setAlert("rules", root.alertSettings.rules.filter(rule => rule !== root.selectedAlertRule))
                            const texts = Object.assign({}, root.alertRuleTexts)
                            delete texts[root.selectedAlertKey]
                            root.alertRuleTexts = texts
                        } else root.setRule("thresholds", root.thresholdValues.length ? root.thresholdValues : [80,95,100])
                    }
                }
                Field {
                    id: ruleThresholdField
                    objectName: "alert-rule-thresholds"
                    visible: !!root.selectedAlertRule
                    text: root.selectedAlertThresholds
                    label: "Selected limit quota alert percentages"
                    onEdited: value => root.setRuleText(value)
                }
                Label { visible: !!root.selectedAlertRule && !root.validThresholds(root.selectedAlertThresholds); text: "Use distinct whole percentages from 1 to 100 for this limit."; color: Commons.Color.urgent }
                Button {
                    visible: !!root.selectedAlertRule
                    width: parent.width
                    alignLeft: true
                    text: (root.selectedAlertRule && root.selectedAlertRule.enabled ? "[x]  " : "[ ]  ") + "Notifications for this limit"
                    Accessible.role: Accessible.CheckBox
                    Accessible.checked: !!root.selectedAlertRule && root.selectedAlertRule.enabled
                    onClicked: root.setRule("enabled", !root.selectedAlertRule.enabled)
                }
            }
        }
    }
    Column {
        objectName: "settings-section-providers"
        visible: root.section === "providers"
        width: parent.width
        spacing: Style.space(6)
        SectionHeading {
            title: "Providers"
            description: "One order for Usage and the bar. Click a provider name to choose limits."
        }
        Row {
            width: parent.width
            spacing: Style.space(4)
            Label { width: parent.width - Style.space(100); text: "Active · Provider"; font.pixelSize: Style.font.caption; opacity: 0.5 }
            Label { width: Style.space(28); text: "Bar"; font.pixelSize: Style.font.caption; horizontalAlignment: Text.AlignHCenter; opacity: 0.5 }
        }
        Repeater {
            id: providerRows
            model: root.order
            delegate: Row {
                id: providerRow
                required property string modelData
                required property int index
                objectName: "provider-row-" + modelData
                width: root.width
                spacing: Style.space(4)
                readonly property Item firstControl: providerButton.enabled ? providerButton
                    : providerBar.enabled ? providerBar : providerUp.enabled ? providerUp : providerDown
                readonly property bool available: root.availableProviders.indexOf(modelData) !== -1
                readonly property bool active: root.enabledProviders.indexOf(modelData) !== -1
                readonly property bool shown: root.selectedItems.some(item => item.provider === modelData)
                function focusMove(direction) {
                    const requested = direction < 0 ? providerUp : providerDown
                    const fallback = direction < 0 ? providerDown : providerUp
                    const control = requested.enabled ? requested : fallback.enabled ? fallback : providerBar
                    control.forceActiveFocus(Qt.TabFocusReason)
                }
                ProviderCheckbox {
                    id: providerButton
                    objectName: "provider-" + providerRow.modelData
                    checked: providerRow.active
                    enabled: providerRow.available
                    Accessible.name: "Active " + root.providerName(providerRow.modelData)
                    Accessible.role: Accessible.CheckBox
                    Accessible.checked: providerRow.active
                    onClicked: root.toggleProvider(providerRow.modelData)
                }
                Plugin.PanelSelect {
                    id: providerLimits
                    objectName: "provider-limits-" + providerRow.modelData
                    width: Math.max(0, parent.width - Style.space(132))
                    text: root.providerName(providerRow.modelData) + (providerRow.available ? "" : " (unavailable)")
                    logoSource: providerRow.available ? root.providerLogo(providerRow.modelData, Plugin.Model.snapshot.providers.find(item => item.id === providerRow.modelData)) : ""
                    popupParent: root.popupParent
                    popupWidth: root.width
                    multiple: true
                    outlined: false
                    foreground: root.foreground
                    fontFamily: root.fontFamily
                    choices: root.providerChoices(providerRow.modelData).map(choice => Object.assign({}, choice, {
                        label: choice.groupLabel + " · " + choice.label,
                        groupKey: "",
                        logoSource: choice.groupLogoSource,
                        objectName: "bar-item-" + choice.provider + "-" + choice.idx + "-" + choice.metric,
                        checked: root.selectedItems.some(item => root.sameItem(item, choice))
                    }))
                    Accessible.name: "Choose bar limits for " + root.providerName(providerRow.modelData)
                    trailingIconName: providerRow.active && providerRow.available ? "chevron-down" : ""
                    onActivated: index => root.toggleItem(choices[index])
                    onPopupOpenChanged: {
                        if (popupOpen && (!providerRow.active || !providerRow.available)) dismiss()
                        root.providerMenuChanged(providerLimits)
                    }
                }
                ProviderCheckbox {
                    id: providerBar
                    objectName: "provider-bar-" + providerRow.modelData
                    checked: providerRow.shown
                    enabled: providerRow.shown || (providerRow.available && providerRow.active)
                    Accessible.name: "Show " + root.providerName(providerRow.modelData) + " in bar"
                    Accessible.role: Accessible.CheckBox
                    Accessible.checked: providerRow.shown
                    onClicked: root.toggleProviderBar(providerRow.modelData)
                }
                Button {
                    id: providerUp
                    objectName: "provider-move-up-" + providerRow.modelData
                    width: Style.space(30)
                    iconName: "arrow-up"
                    enabled: providerRow.index > 0
                    Accessible.name: "Move " + root.providerName(providerRow.modelData) + " up in Usage and the bar"
                    onClicked: root.moveProvider(providerRow.index, -1)
                }
                Button {
                    id: providerDown
                    objectName: "provider-move-down-" + providerRow.modelData
                    width: Style.space(30)
                    iconName: "arrow-down"
                    enabled: providerRow.index < root.order.length - 1
                    Accessible.name: "Move " + root.providerName(providerRow.modelData) + " down in Usage and the bar"
                    onClicked: root.moveProvider(providerRow.index, 1)
                }
            }
        }
    }
    Label {
        visible: root.inlineValidation && text !== ""
        text: Plugin.Model.settingsError || root.validationMessage
        color: Commons.Color.urgent
        font.pixelSize: Style.font.caption
    }
    Button {
        objectName: "settings-review-validation"
        visible: root.inlineValidation && root.validationSection !== "" && (root.validationSection !== root.section || (root.section === "alerts" && !root.alertsAdvanced))
        width: parent.width
        text: root.validationSection ? "Review " + root.sections.find(item => item.key === root.validationSection).label : ""
        outlined: true
        onClicked: root.selectSection(root.validationSection)
    }
    Plugin.GuidePage {
        objectName: "settings-section-guide"
        visible: root.section === "guide"
        width: parent.width
        foreground: root.foreground
        fontFamily: root.fontFamily
    }
    Plugin.AboutPage {
        id: aboutContent
        objectName: "settings-section-about"
        visible: root.section === "about"
        width: parent.width
        foreground: root.foreground
        fontFamily: root.fontFamily
        onGuideRequested: root.selectSection("guide")
    }
}
