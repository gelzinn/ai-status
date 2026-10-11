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
    property var selected: ({})
    property Item popupParent: parent
    readonly property bool selectionOpen: providerSelector.popupOpen
    property bool saved: false
    signal aboutRequested()
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
    readonly property bool valid: enabledProviders.length > 0 && Object.keys(display).some(key => display[key]) && choices.some(item => item.provider === selected.provider && item.idx === selected.idx && item.metric === selected.metric)
    spacing: Style.space(22)
    enabled: !Plugin.Model.settingsSaving
    onOrderChanged: saved = false
    onEnabledProvidersChanged: saved = false
    onDisplayChanged: saved = false
    onIconModeChanged: saved = false
    onSelectedChanged: saved = false
    onVisibleChanged: if (!visible) closeSelectors()

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
            "Cursor Models included quota": "Cursor Models", "Other Models included quota": "Other Models",
            "On-demand spend this billing cycle": "On-demand spend"}
        const label = shortNames[metric.name] || metric.name
        // Key suffixes may be full names or opaque IDs, not display labels.
        // Only legacy period metrics use a suffix as a model qualifier.
        const parts = metric.key.split(":")
        const qualifier = parts.slice(1).join(":")
        const periodName = {rolling: "Rolling Usage", daily: "Daily Usage", weekly: "Weekly Usage", monthly: "Monthly Usage"}[parts[0]]
        return qualifier && metric.name === periodName && qualifier !== metric.name ? label + " · " + qualifier : label
    }

    function closeSelectors() {
        providerSelector.dismiss()
        iconSelector.dismiss()
    }

    function begin() {
        const settings = Plugin.Model.snapshot.settings || {}
        order = (settings.order || []).slice()
        enabledProviders = (settings.enabled || []).slice()
        display = Object.assign({}, settings.display || {})
        iconMode = settings.iconMode || "bot"
        selected = Object.assign({}, Plugin.Model.snapshot.selected)
        closeSelectors()
        saved = false
        Plugin.Model.settingsError = ""
    }

    function focusFirstControl() {
        providerSelector.forceActiveFocus(Qt.TabFocusReason)
    }
    function focusAboutControl() { aboutButton.forceActiveFocus() }

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
    component Button: Plugin.PanelButton {
        foreground: root.foreground
        fontFamily: root.fontFamily
    }

    Column {
        width: parent.width
        spacing: Style.space(8)
        Label { text: "Active provider & limit"; font.bold: true }
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
            onPopupOpenChanged: if (popupOpen) iconSelector.dismiss()
            onActivated: index => {
                const choice = root.choices[index]
                root.selected = {provider: choice.provider, idx: choice.idx, metric: choice.metric}
            }
        }
    }
    Column {
        width: parent.width
        spacing: Style.space(4)
        Label { text: "Bar display"; font.bold: true }
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
            onPopupOpenChanged: if (popupOpen) providerSelector.dismiss()
            onActivated: index => root.iconMode = choices[index].value
        }
    }
    Column {
        width: parent.width
        spacing: Style.space(6)
        Label { text: "Providers"; font.bold: true }
        Label {
            text: "Enable providers and set their order in the usage page."
            opacity: 0.5
            font.pixelSize: Style.font.caption
        }
        Repeater {
            model: root.order
            delegate: Row {
                required property string modelData
                required property int index
                width: root.width
                spacing: Style.space(4)
                Button {
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
                    width: Style.space(30)
                    iconName: "arrow-up"
                    enabled: parent.index > 0
                    Accessible.name: "Move " + root.providerName(parent.modelData) + " up"
                    onClicked: root.moveProvider(parent.index, -1)
                }
                Button {
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
        visible: text !== ""
        text: Plugin.Model.settingsError || (!root.valid ? "Enable a provider and at least one bar text field, then choose a limit." : "")
        color: Commons.Color.urgent
        font.pixelSize: Style.font.caption
    }
    Button {
        id: aboutButton
        objectName: "settings-about"
        width: parent.width
        text: "About AI Status"
        alignLeft: true
        trailingIconName: "arrow-right"
        outlined: true
        onClicked: root.aboutRequested()
    }
}
