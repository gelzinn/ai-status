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
    property bool selectionOpen: false
    readonly property var choices: {
        const items = []
        for (const name of enabledProviders) {
            const entries = Plugin.Model.snapshot.providers.filter(p => p.id === name)
            if (entries.length === 0)
                items.push({provider: name, idx: 0, metric: "rolling", label: name})
            for (const entry of entries) {
                for (const metric of entry.metrics) {
                    const detail = metric.key.indexOf(":") === -1 ? "" : " (" + metric.key.split(":").slice(1).join(":") + ")"
                    items.push({provider: name, idx: entry.idx, metric: metric.key, label: entry.name + " · " + metric.name + detail})
                }
                if (entry.metrics.length === 0)
                    items.push({provider: name, idx: entry.idx, metric: "rolling", label: entry.name})
            }
        }
        return items
    }
    readonly property string selectedLabel: {
        const choice = choices.find(item => item.provider === selected.provider && item.idx === selected.idx && item.metric === selected.metric)
        return choice ? choice.label : "Choose a provider and limit"
    }
    readonly property bool valid: enabledProviders.length > 0 && Object.keys(display).some(key => display[key]) && choices.some(item => item.provider === selected.provider && item.idx === selected.idx && item.metric === selected.metric)
    spacing: Style.space(22)
    enabled: !Plugin.Model.settingsSaving

    function begin() {
        const settings = Plugin.Model.snapshot.settings || {}
        order = (settings.order || []).slice()
        enabledProviders = (settings.enabled || []).slice()
        display = Object.assign({}, settings.display || {})
        iconMode = settings.iconMode || "bot"
        selected = Object.assign({}, Plugin.Model.snapshot.selected)
        selectionOpen = false
        Plugin.Model.settingsError = ""
    }

    function focusFirstControl() {
        providerSelector.forceActiveFocus(Qt.TabFocusReason)
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
        Button {
            id: providerSelector
            objectName: "active-provider"
            width: parent.width
            text: root.selectedLabel + "  ▾"
            multiline: true
            alignLeft: true
            outlined: true
            onClicked: root.selectionOpen = !root.selectionOpen
        }
        Column {
            visible: root.selectionOpen
            width: parent.width
            Repeater {
                model: root.choices
                delegate: Button {
                    required property var modelData
                    width: parent.width
                    text: modelData.label
                    multiline: true
                    alignLeft: true
                    onClicked: {
                        root.selected = {provider: modelData.provider, idx: modelData.idx, metric: modelData.metric}
                        root.selectionOpen = false
                    }
                }
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
                {key: "show_pct", label: "Percentage"}
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
        Button {
            width: parent.width
            alignLeft: true
            text: "Icon: " + ({off: "None", bot: "Bot", logo: "Provider logo"}[root.iconMode]) + "  ›"
            outlined: true
            onClicked: {
                const modes = ["off", "bot", "logo"]
                root.iconMode = modes[(modes.indexOf(root.iconMode) + 1) % modes.length]
            }
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
                    text: (root.enabledProviders.indexOf(parent.modelData) !== -1 ? "[x]  " : "[ ]  ") + parent.modelData
                    alignLeft: true
                    Accessible.role: Accessible.CheckBox
                    Accessible.checked: root.enabledProviders.indexOf(parent.modelData) !== -1
                    onClicked: root.toggleProvider(parent.modelData)
                }
                Button {
                    width: Style.space(30)
                    text: "↑"
                    enabled: parent.index > 0
                    Accessible.name: "Move " + parent.modelData + " up"
                    onClicked: root.moveProvider(parent.index, -1)
                }
                Button {
                    width: Style.space(30)
                    text: "↓"
                    enabled: parent.index < root.order.length - 1
                    Accessible.name: "Move " + parent.modelData + " down"
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
}
