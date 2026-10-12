import QtQuick
import qs.Commons
import qs.Commons as Commons
import "." as Plugin

Column {
    id: root
    property color foreground: "white"
    property string fontFamily: Style.font.family
    property var order: []
    property var enabledProviders: []
    property var display: ({})
    property string iconMode: "bot"
    property string usageDisplay: "used"
    property var selected: ({})
    property var alertSettings: ({enabled: true, thresholds: [80,95,100], recovery: true, muted_until: 0, rules: [], quiet_hours: {start: "", end: ""}, work_hours: {start: "", end: ""}, recent_only: false})
    property string alertThresholds: "80,95,100"
    property string alertQuietHours: ""
    property string alertWorkHours: ""
    property var alertRuleTexts: ({})
    readonly property string selectedAlertKey: selected.provider + "\u001f" + selected.metric
    readonly property var selectedAlertRule: (alertSettings.rules || []).find(rule => rule.connection_id === selected.provider && rule.metric === selected.metric) || null
    readonly property string selectedAlertThresholds: alertRuleTexts[selectedAlertKey] !== undefined ? alertRuleTexts[selectedAlertKey] : selectedAlertRule ? selectedAlertRule.thresholds.join(",") : ""
    property Item popupParent: parent
    readonly property bool selectionOpen: providerSelector.popupOpen || iconSelector.popupOpen || usageDisplaySelector.popupOpen
    property bool saved: false
    property bool inlineValidation: true
    property string section: "general"
    readonly property var sections: [
        {key: "general", label: "General"},
        {key: "appearance", label: "Appearance"},
        {key: "alerts", label: "Alerts"},
        {key: "providers", label: "Providers"},
        {key: "about", label: "About"}
    ]
    readonly property string validationSection: enabledProviders.length === 0 ? "providers"
        : !Object.keys(display).some(key => display[key]) || ["used", "remaining"].indexOf(usageDisplay) === -1 ? "appearance"
        : !choices.some(item => item.provider === selected.provider && item.idx === selected.idx && item.metric === selected.metric) ? "general"
        : !valid ? "alerts" : ""
    readonly property string validationMessage: validationSection === "providers" ? "Enable at least one provider in Providers."
        : validationSection === "appearance" ? "Choose a usage display and at least one bar text field in Appearance."
        : validationSection === "general" ? "Choose an active provider and limit in General."
        : validationSection === "alerts" ? "Alert thresholds must be whole percentages from 1 to 100. Review Alerts."
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
        return items
    }
    readonly property var selectedChoice: choices.find(item => item.provider === selected.provider && item.idx === selected.idx && item.metric === selected.metric) || null
    readonly property string selectedLabel: selectedChoice ? selectedChoice.groupLabel + " · " + selectedChoice.label : "Choose a provider and limit"
    readonly property bool valid: enabledProviders.length > 0 && Object.keys(display).some(key => display[key]) && ["used", "remaining"].indexOf(usageDisplay) !== -1 && choices.some(item => item.provider === selected.provider && item.idx === selected.idx && item.metric === selected.metric) && validThresholds(alertThresholds) && (alertSettings.rules || []).every(rule => validThresholds(alertRuleTexts[rule.connection_id + "\u001f" + rule.metric] !== undefined ? alertRuleTexts[rule.connection_id + "\u001f" + rule.metric] : rule.thresholds.join(",")))
    spacing: Style.space(16)
    enabled: !Plugin.Model.settingsSaving
    onOrderChanged: saved = false
    onEnabledProvidersChanged: saved = false
    onDisplayChanged: saved = false
    onIconModeChanged: saved = false
    onUsageDisplayChanged: saved = false
    onSelectedChanged: saved = false
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

    function providerLogo(name, entry) {
        return entry && entry.logoPath ? "file://" + entry.logoPath : Qt.resolvedUrl("../assets/providers/" + ((Plugin.Model.snapshot.settings.providerIds || {})[name] || name) + ".png")
    }

    function providerName(name) {
        return (Plugin.Model.snapshot.settings.names || {})[name] || name
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
        providerSelector.dismiss()
        iconSelector.dismiss()
        usageDisplaySelector.dismiss()
    }

    function begin() {
        section = "general"
        const settings = Plugin.Model.snapshot.settings || {}
        order = (settings.order || []).slice()
        enabledProviders = (settings.enabled || []).slice()
        display = Object.assign({}, settings.display || {})
        iconMode = settings.iconMode || "bot"
        usageDisplay = settings.usageDisplay === "remaining" ? "remaining" : "used"
        selected = Object.assign({}, Plugin.Model.snapshot.selected)
        alertSettings = JSON.parse(JSON.stringify(settings.notifications || {enabled: true, thresholds: [80,95,100], recovery: true, muted_until: 0, rules: [], quiet_hours: {start: "", end: ""}, work_hours: {start: "", end: ""}, recent_only: false}))
        alertThresholds = alertSettings.thresholds.join(",")
        alertRuleTexts = {}
        alertQuietHours = hoursText("quiet_hours")
        alertWorkHours = hoursText("work_hours")
        closeSelectors()
        saved = false
        Plugin.Model.settingsError = ""
    }

    function focusFirstControl() {
        if (section === "about") { aboutContent.focusFirstControl(); return }
        const first = section === "appearance" ? usageDisplaySelector
            : section === "alerts" ? alertAccountButton
            : section === "providers" && providerRows.count > 0 ? providerRows.itemAt(0).firstControl : providerSelector
        if (first) first.forceActiveFocus(Qt.TabFocusReason)
    }

    function selectSection(key) {
        if (Plugin.Model.settingsSaving || !sections.some(item => item.key === key)) return
        closeSelectors()
        section = key
    }

    function toggleProvider(name) {
        enabledProviders = enabledProviders.indexOf(name) === -1 ? enabledProviders.concat([name]) : enabledProviders.filter(item => item !== name)
        if (enabledProviders.indexOf(selected.provider) === -1) {
            const first = choices[0]
            selected = first ? {provider: first.provider, idx: first.idx, metric: first.metric} : {}
        }
    }

    function moveProvider(index, direction) {
        const next = order.slice()
        const other = index + direction
        if (other < 0 || other >= next.length) return
        const value = next[index]
        next[index] = next[other]
        next[other] = value
        order = next
    }

    function save() {
        if (!valid) return
        saved = false
        Plugin.Model.saveSettings({
            enabled: order.filter(name => enabledProviders.indexOf(name) !== -1),
            display: display,
            iconMode: iconMode,
            usageDisplay: usageDisplay,
            notifications: Object.assign({}, alertSettings, {
                thresholds: alertThresholds.split(",").map(value => Number(value.trim())),
                rules: (alertSettings.rules || []).map(rule => Object.assign({}, rule, {
                    thresholds: alertRuleTexts[rule.connection_id + "\u001f" + rule.metric] !== undefined ? alertRuleTexts[rule.connection_id + "\u001f" + rule.metric].split(",").map(Number) : rule.thresholds
                }))
            }),
            selected: {provider: selected.provider, idx: selected.idx, metric: selected.metric}
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
    component Field: Rectangle {
        id: field
        property string text: ""
        property string label: ""
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
        const values = value.split(",")
        return values.length > 0 && values.every(item => /^\d+$/.test(item.trim()) && Number(item) > 0 && Number(item) <= 100)
    }
    function setAlert(key, value) {
        const next = Object.assign({}, alertSettings)
        next[key] = value
        alertSettings = next
    }
    function setRule(key, value) {
        const rules = (alertSettings.rules || []).filter(rule => rule.connection_id !== selected.provider || rule.metric !== selected.metric)
        const rule = Object.assign({}, selectedAlertRule || {connection_id: selected.provider, metric: selected.metric, thresholds: alertSettings.thresholds, enabled: true})
        rule[key] = value
        setAlert("rules", rules.concat([rule]))
    }
    function setRuleText(value) {
        const texts = Object.assign({}, alertRuleTexts)
        texts[selectedAlertKey] = value
        alertRuleTexts = texts
    }
    function hoursText(key) {
        const hours = alertSettings[key] || {start: "", end: ""}
        return hours.start ? hours.start + "-" + hours.end : ""
    }
    function setHours(key, value) {
        if (key === "quiet_hours") alertQuietHours = value
        else alertWorkHours = value
        const parts = value ? value.split("-") : ["", ""]
        setAlert(key, {start: parts[0], end: parts[1] || ""})
    }

    Column {
        objectName: "settings-section-general"
        visible: root.section === "general"
        width: parent.width
        spacing: Style.space(8)
        SectionHeading {
            title: "Active provider & limit"
            description: "Choose the account and limit shown in the bar."
        }
        Plugin.PanelSelect {
            id: providerSelector
            objectName: "active-provider"
            width: parent.width
            text: root.selectedLabel
            logoSource: root.selectedChoice ? root.selectedChoice.groupLogoSource : ""
            popupParent: root.popupParent
            foreground: root.foreground
            fontFamily: root.fontFamily
            choices: root.choices.map(item => Object.assign({}, item, {objectName: "active-provider-option-" + item.provider + "-" + item.idx + "-" + item.metric}))
            currentIndex: root.choices.indexOf(root.selectedChoice)
            onPopupOpenChanged: if (popupOpen) { iconSelector.dismiss(); usageDisplaySelector.dismiss() }
            onActivated: index => {
                const choice = root.choices[index]
                root.selected = {provider: choice.provider, idx: choice.idx, metric: choice.metric}
            }
        }
    }
    Column {
        objectName: "settings-section-appearance"
        visible: root.section === "appearance"
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
            onPopupOpenChanged: if (popupOpen) { providerSelector.dismiss(); iconSelector.dismiss() }
            onActivated: index => root.usageDisplay = choices[index].value
        }
    }
    Column {
        visible: root.section === "appearance"
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
            onPopupOpenChanged: if (popupOpen) { providerSelector.dismiss(); usageDisplaySelector.dismiss() }
            onActivated: index => root.iconMode = choices[index].value
        }
    }
    Column {
        objectName: "settings-section-alerts"
        visible: root.section === "alerts"
        width: parent.width
        spacing: Style.space(8)
        SectionHeading {
            title: "Quota alerts"
            description: "Alerts use quota consumed. Recovery requires a successful fresh check of all applicable limits."
        }
        Label { text: "Selected account & limit: " + root.selectedLabel; font.pixelSize: Style.font.caption }
        Button {
            id: alertAccountButton
            objectName: "alerts-change-selection"
            width: parent.width
            text: "Change account & limit"
            alignLeft: true
            trailingIconName: "arrow-right"
            outlined: true
            onClicked: root.selectSection("general")
        }
        Repeater {
            model: [{key: "enabled", label: "Desktop quota alerts"}, {key: "recovery", label: "Notify when capacity recovers"}, {key: "recent_only", label: "Recovery only for accounts active in the last 24h"}]
            delegate: Button {
                required property var modelData
                objectName: "alerts-" + modelData.key
                width: parent.width
                alignLeft: true
                multiline: true
                text: (root.alertSettings[modelData.key] ? "[x]  " : "[ ]  ") + modelData.label
                Accessible.role: Accessible.CheckBox
                Accessible.checked: !!root.alertSettings[modelData.key]
                onClicked: root.setAlert(modelData.key, !root.alertSettings[modelData.key])
            }
        }
        Label { text: "Consumption thresholds (%)" }
        Field { objectName: "alert-thresholds"; text: root.alertThresholds; label: "Quota alert percentages"; onEdited: value => root.alertThresholds = value }
        Label { visible: !root.validThresholds(root.alertThresholds); text: "Enter percentages between 0 and 100, separated by commas."; color: Commons.Color.urgent }
        Button {
            objectName: "alert-rule-customize"
            width: parent.width
            alignLeft: true
            multiline: true
            text: (root.selectedAlertRule ? "[x]  " : "[ ]  ") + "Custom alerts for selected account & limit"
            onClicked: {
                if (root.selectedAlertRule) {
                    root.setAlert("rules", root.alertSettings.rules.filter(rule => rule !== root.selectedAlertRule))
                    const texts = Object.assign({}, root.alertRuleTexts)
                    delete texts[root.selectedAlertKey]
                    root.alertRuleTexts = texts
                } else root.setRule("thresholds", root.validThresholds(root.alertThresholds) ? root.alertThresholds.split(",").map(Number) : [80,95,100])
            }
        }
        Field {
            objectName: "alert-rule-thresholds"
            visible: !!root.selectedAlertRule
            text: root.selectedAlertThresholds
            label: "Selected limit quota alert percentages"
            onEdited: value => root.setRuleText(value)
        }
        Label { visible: !!root.selectedAlertRule && !root.validThresholds(root.selectedAlertThresholds); text: "Enter whole percentages from 1 to 100 for this limit."; color: Commons.Color.urgent }
        Button {
            visible: !!root.selectedAlertRule
            width: parent.width
            alignLeft: true
            text: (root.selectedAlertRule && root.selectedAlertRule.enabled ? "[x]  " : "[ ]  ") + "Alerts for this limit"
            onClicked: root.setRule("enabled", !root.selectedAlertRule.enabled)
        }
        Button {
            objectName: "alerts-mute"
            width: parent.width
            text: root.alertSettings.muted_until > Date.now() / 1000 ? "Resume alerts" : "Silence alerts for 1 hour"
            outlined: true
            onClicked: root.setAlert("muted_until", root.alertSettings.muted_until > Date.now() / 1000 ? 0 : Date.now() / 1000 + 3600)
        }
        Label { text: "Quiet hours (local HH:MM-HH:MM, blank for none)" }
        Field { objectName: "alerts-quiet-hours"; text: root.alertQuietHours; label: "Quiet hours"; onEdited: value => root.setHours("quiet_hours", value) }
        Label { text: "Working hours (local HH:MM-HH:MM, blank for all day)" }
        Field { objectName: "alerts-work-hours"; text: root.alertWorkHours; label: "Working hours"; onEdited: value => root.setHours("work_hours", value) }
    }
    Column {
        objectName: "settings-section-providers"
        visible: root.section === "providers"
        width: parent.width
        spacing: Style.space(6)
        SectionHeading {
            title: "Providers"
            description: "Enable providers and set their order in the usage page."
        }
        Repeater {
            id: providerRows
            model: root.order
            delegate: Row {
                required property string modelData
                required property int index
                width: root.width
                spacing: Style.space(4)
                property alias firstControl: providerButton
                Button {
                    id: providerButton
                    objectName: "provider-" + parent.modelData
                    width: Math.max(0, parent.width - Style.space(68))
                    prefixText: root.enabledProviders.indexOf(parent.modelData) !== -1 ? "[x]" : "[ ]"
                    text: root.providerName(parent.modelData)
                    logoSource: root.providerLogo(parent.modelData, Plugin.Model.snapshot.providers.find(item => item.id === parent.modelData))
                    alignLeft: true
                    Accessible.role: Accessible.CheckBox
                    Accessible.checked: root.enabledProviders.indexOf(parent.modelData) !== -1
                    onClicked: root.toggleProvider(parent.modelData)
                }
                Button {
                    objectName: "provider-move-up-" + parent.modelData
                    width: Style.space(30)
                    iconName: "arrow-up"
                    enabled: parent.index > 0
                    Accessible.name: "Move " + root.providerName(parent.modelData) + " up"
                    onClicked: root.moveProvider(parent.index, -1)
                }
                Button {
                    objectName: "provider-move-down-" + parent.modelData
                    width: Style.space(30)
                    iconName: "arrow-down"
                    enabled: parent.index < root.order.length - 1
                    Accessible.name: "Move " + root.providerName(parent.modelData) + " down"
                    onClicked: root.moveProvider(parent.index, 1)
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
        visible: root.inlineValidation && root.validationSection !== "" && root.validationSection !== root.section
        width: parent.width
        text: root.validationSection ? "Review " + root.sections.find(item => item.key === root.validationSection).label : ""
        outlined: true
        onClicked: root.selectSection(root.validationSection)
    }
    Plugin.AboutPage {
        id: aboutContent
        objectName: "settings-section-about"
        visible: root.section === "about"
        width: parent.width
        foreground: root.foreground
        fontFamily: root.fontFamily
    }
}
