import QtQuick
import QtQuick.Shapes
import qs.Commons
import qs.Commons as Commons
import "." as Plugin
import "StableList.js" as StableList

Column {
    id: root
    property var provider: null
    property color foreground: "white"
    property string fontFamily: Style.font.family
    readonly property var inventory: provider && provider.resetCredits ? provider.resetCredits : ({available: 0, rows: [], undetailed: 0})
    readonly property bool canApply: !!provider && !!provider.resetAction && !provider.cached && !provider.loading && !Plugin.Model.updateRunning
        && !Plugin.Model.resetAttempted(provider.id, provider.idx, provider.resetAction.fingerprint)
    readonly property bool ownReset: !!provider && !!Plugin.Model.resetTarget && provider.id === Plugin.Model.resetTarget.provider && provider.idx === Plugin.Model.resetTarget.idx
    property var confirmation: null
    signal backFocusRequested()
    spacing: Style.space(18)
    onInventoryChanged: syncRows()
    onProviderChanged: validateConfirmation()
    onCanApplyChanged: validateConfirmation()
    onVisibleChanged: if (!visible) confirmation = null
    Keys.onEscapePressed: event => { event.accepted = cancelConfirmation() }
    Component.onCompleted: syncRows()

    function syncRows() {
        StableList.sync(rows, inventory.rows, entry => entry.actionId || entry.title + ":" + entry.expires + ":" + entry.count)
        validateConfirmation()
    }

    function validateConfirmation() {
        if (!confirmation) return
        if (!canApply || provider.id !== confirmation.provider || provider.idx !== confirmation.idx
            || provider.resetAction.fingerprint !== confirmation.fingerprint
            || !(inventory.rows || []).some(row => row.actionId === confirmation.credit)) {
            confirmation = null
            if (visible) Qt.callLater(() => { if (!root.focusFirstControl()) root.backFocusRequested() })
        }
    }

    function focusFirstControl(direction) {
        const reason = direction < 0 ? Qt.BacktabFocusReason : Qt.TabFocusReason
        for (let offset = 0; offset < rowRepeater.count; offset++) {
            const index = direction < 0 ? rowRepeater.count - offset - 1 : offset
            const item = rowRepeater.itemAt(index)
            if (item && item.confirming && item.cancelControl.visible && item.cancelControl.enabled) {
                item.cancelControl.forceActiveFocus(reason)
                return true
            }
            if (item && item.applyControl.visible && item.applyControl.enabled) {
                item.applyControl.forceActiveFocus(reason)
                return true
            }
        }
        return false
    }

    function requestReset(row) {
        if (!visible || !canApply || !row.actionId || Plugin.Model.resetApplying) return
        confirmation = {
            provider: provider.id, idx: provider.idx, fingerprint: provider.resetAction.fingerprint,
            credit: row.actionId, title: row.title, name: provider.name
        }
        // Give the safe choice focus; Enter never accepts a newly opened confirmation.
        Qt.callLater(() => { if (root.confirmation) root.focusFirstControl() })
    }

    function cancelConfirmation() {
        if (!confirmation) return false
        const credit = confirmation.credit
        confirmation = null
        Qt.callLater(() => {
            for (let index = 0; index < rowRepeater.count; index++) {
                const item = rowRepeater.itemAt(index)
                if (item && item.entry.actionId === credit && item.applyControl.visible && item.applyControl.enabled) {
                    item.applyControl.forceActiveFocus(Qt.TabFocusReason)
                    return
                }
            }
            root.backFocusRequested()
        })
        return true
    }

    function confirmReset(control) {
        validateConfirmation()
        if (!visible || !confirmation || !control || !control.completed || Plugin.Model.resetApplying) return
        let selectedControl = null
        for (let index = 0; index < rowRepeater.count; index++) {
            const item = rowRepeater.itemAt(index)
            if (item && item.confirming) selectedControl = item.holdControl
        }
        if (control !== selectedControl) return
        const request = {
            provider: confirmation.provider, idx: confirmation.idx, fingerprint: confirmation.fingerprint,
            credit: confirmation.credit, confirmed: true
        }
        confirmation = null
        Plugin.Model.applyReset(request)
        root.backFocusRequested()
    }

    ListModel { id: rows; dynamicRoles: true }
    component Label: Text {
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        wrapMode: Text.WordWrap
    }
    component Secondary: Label {
        opacity: 0.5
        font.pixelSize: Style.font.caption
    }
    Item {
        objectName: "reset-provider-heading"
        width: parent.width
        height: Math.max(Style.space(24), providerLabel.implicitHeight)
        Image {
            objectName: "reset-provider-logo"
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Style.space(16)
            height: width
            source: root.provider ? root.provider.logoPath ? "file://" + root.provider.logoPath : Qt.resolvedUrl("../assets/providers/" + root.provider.id + ".png") : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }
        Label {
            id: providerLabel
            x: Style.space(24)
            width: Math.max(0, parent.width - x)
            anchors.verticalCenter: parent.verticalCenter
            text: root.provider ? root.provider.name : ""
        }
    }
    Secondary { width: parent.width; text: "Cached data"; visible: !!root.provider && root.provider.cached }
    Column {
        width: parent.width
        spacing: Style.space(8)
        Label { objectName: "reset-section-title"; text: "Usage limit resets"; font.bold: true }
        Label {
            objectName: "reset-explanation"
            width: parent.width
            opacity: 0.55
            text: root.provider && (root.provider.providerId || root.provider.id) === "codex"
                ? "Restore your 5-hour or weekly limit,\nor both, depending on the reset type."
                : "Restore eligible usage limits.\nCredits expire on the dates below."
        }
    }
    Rectangle {
        id: resetTable
        objectName: "reset-table"
        width: parent.width
        implicitHeight: table.implicitHeight + 2
        color: "transparent"
        border.width: 1
        radius: Style.cornerRadius
        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.15)
        visible: root.inventory.available > 0
        readonly property real cellPadding: Style.space(12)
        readonly property real columnGap: Style.space(8)
        readonly property real actionWidth: Style.space(60)
        readonly property real detailWidth: Math.max(0, (table.width - cellPadding * 2 - columnGap * 2 - actionWidth) / 2)
        Column {
            id: table
            x: 1
            y: 1
            width: parent.width - 2
            Item {
                id: columnHeader
                objectName: "reset-column-header"
                width: parent.width
                height: columnHeadings.implicitHeight + Style.space(18)
                readonly property color color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
                readonly property real radius: Math.max(0, resetTable.radius - 1)
                Shape {
                    anchors.fill: parent
                    antialiasing: true
                    layer.enabled: visible
                    layer.samples: 4
                    layer.smooth: true
                    ShapePath {
                        strokeColor: "transparent"
                        fillColor: columnHeader.color
                        startX: 0
                        startY: columnHeader.radius
                        PathLine { x: 0; y: columnHeader.height }
                        PathLine { x: columnHeader.width; y: columnHeader.height }
                        PathLine { x: columnHeader.width; y: columnHeader.radius }
                        PathQuad { x: columnHeader.width - columnHeader.radius; y: 0; controlX: columnHeader.width; controlY: 0 }
                        PathLine { x: columnHeader.radius; y: 0 }
                        PathQuad { x: 0; y: columnHeader.radius; controlX: 0; controlY: 0 }
                    }
                }
                Row {
                    id: columnHeadings
                    x: Style.space(12)
                    y: Style.space(10)
                    width: parent.width - x * 2
                    spacing: resetTable.columnGap
                    Secondary { objectName: "reset-type-header"; width: resetTable.detailWidth; text: "Reset type" }
                    Secondary { objectName: "reset-expires-header"; width: resetTable.detailWidth; text: "Expires" }
                    Secondary { objectName: "reset-action-header"; width: resetTable.actionWidth; Accessible.name: "Actions" }
                }
            }
            Repeater {
                id: rowRepeater
                model: rows
                delegate: Item {
                    id: creditRow
                    required property var entry
                    property alias applyControl: applyReset
                    property alias cancelControl: cancelReset
                    property alias holdControl: holdReset
                    readonly property bool confirming: !!root.confirmation && root.confirmation.credit === entry.actionId
                    objectName: "reset-row"
                    width: table.width
                    implicitHeight: (confirming ? confirmationContent.implicitHeight : Math.max(typeCell.implicitHeight, expiryCell.implicitHeight, applyReset.implicitHeight)) + Style.space(24)
                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.09)
                    }
                    Column {
                        id: typeCell
                        x: Style.space(12)
                        y: Style.space(12)
                        width: resetTable.detailWidth
                        visible: !creditRow.confirming
                        spacing: Style.space(5)
                        Label { width: parent.width; text: entry.title }
                        Secondary { width: parent.width; text: entry.count + (entry.count === 1 ? " credit" : " credits") }
                    }
                    Column {
                        id: expiryCell
                        x: typeCell.x + typeCell.width + resetTable.columnGap
                        y: typeCell.y
                        width: typeCell.width
                        visible: !creditRow.confirming
                        spacing: Style.space(5)
                        Label { width: parent.width; text: entry.expires }
                        Secondary { objectName: "reset-remaining"; width: parent.width; text: entry.remaining }
                    }
                    Plugin.PanelButton {
                        id: applyReset
                        objectName: "reset-apply"
                        x: expiryCell.x + expiryCell.width + resetTable.columnGap
                        anchors.verticalCenter: parent.verticalCenter
                        width: resetTable.actionWidth
                        visible: !creditRow.confirming && !!entry.actionId && root.canApply
                        enabled: !Plugin.Model.resetApplying && !root.confirmation
                        text: "Apply"
                        outlined: true
                        foreground: root.foreground
                        fontFamily: root.fontFamily
                        Accessible.name: "Apply " + entry.title + " for " + (root.provider ? root.provider.name : "") + ". Review confirmation."
                        onClicked: root.requestReset(entry)
                    }
                    Rectangle {
                        objectName: creditRow.confirming ? "reset-confirmation" : ""
                        anchors.fill: parent
                        anchors.topMargin: 1
                        visible: creditRow.confirming
                        color: Qt.rgba(Commons.Color.accent.r, Commons.Color.accent.g, Commons.Color.accent.b, 0.04)
                        Column {
                            id: confirmationContent
                            x: resetTable.cellPadding
                            y: Style.space(12)
                            width: parent.width - x * 2
                            spacing: Style.space(12)
                            Label {
                                objectName: creditRow.confirming ? "reset-confirmation-details" : ""
                                width: parent.width
                                text: creditRow.confirming ? root.confirmation.name + "\n" + root.confirmation.title + " · Consumes 1 reset credit" : ""
                                Accessible.role: Accessible.StaticText
                                Accessible.name: text
                            }
                            Row {
                                width: parent.width
                                spacing: Style.space(8)
                                Plugin.PanelButton {
                                    id: cancelReset
                                    objectName: creditRow.confirming ? "reset-cancel" : ""
                                    width: Style.space(76)
                                    text: "Cancel"
                                    outlined: true
                                    foreground: root.foreground
                                    fontFamily: root.fontFamily
                                    onClicked: root.cancelConfirmation()
                                }
                                Plugin.HoldToConfirmButton {
                                    id: holdReset
                                    objectName: creditRow.confirming ? "reset-confirm" : ""
                                    width: Math.max(0, parent.width - cancelReset.width - parent.spacing)
                                    foreground: root.foreground
                                    fontFamily: root.fontFamily
                                    enabled: creditRow.confirming && root.canApply && !Plugin.Model.resetApplying
                                    Accessible.name: "Hold to apply " + (creditRow.confirming ? root.confirmation.title + " for " + root.confirmation.name : "reset") + " for 3 seconds. Consume 1 reset credit."
                                    onConfirmed: root.confirmReset(holdReset)
                                }
                            }
                        }
                    }
                }
            }
            Item {
                id: tableFooter
                objectName: "reset-table-footer"
                width: table.width
                implicitHeight: Math.max(availableLabel.implicitHeight, availableValue.implicitHeight) + Style.space(24) + 1
                readonly property color color: columnHeader.color
                readonly property real radius: columnHeader.radius
                Shape {
                    id: footerBackground
                    y: 1
                    width: parent.width
                    height: parent.height - 1
                    antialiasing: true
                    layer.enabled: visible
                    layer.samples: 4
                    layer.smooth: true
                    ShapePath {
                        strokeColor: "transparent"
                        fillColor: tableFooter.color
                        startX: 0
                        startY: 0
                        PathLine { x: footerBackground.width; y: 0 }
                        PathLine { x: footerBackground.width; y: footerBackground.height - tableFooter.radius }
                        PathQuad { x: footerBackground.width - tableFooter.radius; y: footerBackground.height; controlX: footerBackground.width; controlY: footerBackground.height }
                        PathLine { x: tableFooter.radius; y: footerBackground.height }
                        PathQuad { x: 0; y: footerBackground.height - tableFooter.radius; controlX: 0; controlY: footerBackground.height }
                        PathLine { x: 0; y: 0 }
                    }
                }
                Rectangle {
                    width: parent.width
                    height: 1
                    color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.09)
                }
                Row {
                    x: Style.space(12)
                    y: Style.space(12) + 1
                    width: parent.width - x * 2
                    spacing: Style.space(12)
                    Label {
                        id: availableLabel
                        objectName: "reset-available-label"
                        width: Math.max(0, parent.width - availableValue.implicitWidth - parent.spacing)
                        text: "Available resets"
                        opacity: 0.55
                    }
                    Label {
                        id: availableValue
                        objectName: "reset-available"
                        text: String(root.inventory.available)
                        font.weight: Font.Medium
                    }
                }
            }
        }
    }
    Label {
        objectName: "reset-status"
        width: parent.width
        visible: root.ownReset && text !== ""
        text: Plugin.Model.resetApplying ? "Applying reset…" : Plugin.Model.resetError || Plugin.Model.resetMessage
        color: Plugin.Model.resetError ? Commons.Color.urgent : root.foreground
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }
    Secondary {
        objectName: "reset-timezone"
        width: parent.width
        text: root.inventory.timezone || ""
        visible: text.length > 0 && root.inventory.available > 0
    }
    Label { width: parent.width; text: "No reset credits available."; visible: root.inventory.available === 0 }
    Secondary { width: parent.width; text: "Some reset details haven't been provided yet."; visible: root.inventory.undetailed > 0 }
}
