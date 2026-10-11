import QtQuick
import qs.Commons
import qs.Commons as Commons
import "." as Plugin

Column {
    id: root
    property color foreground: "white"
    property string fontFamily: Style.font.family
    readonly property color linkColor: "#89b4fa"
    readonly property var guide: Plugin.Model.snapshot.update || {}
    readonly property var version: Plugin.Model.snapshot.version || {}
    spacing: Style.space(16)

    function focusFirstControl() {
        if (updateAction.visible && updateAction.enabled) updateAction.forceActiveFocus()
        else releaseNotes.forceActiveFocus()
    }

    component Label: Text {
        width: parent.width
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
    }

    Column {
        width: parent.width
        spacing: Style.space(10)
        Label { text: root.guide.title || "A new version is available"; font.bold: true }
        Label {
            objectName: "update-versions"
            text: "Installed: v" + (root.version.current || "—") + "\nAvailable: v" + (root.version.latest || "—")
            opacity: 0.7
        }
        Label { text: root.guide.description || "Open the update guide for your installation." }
    }

    Column {
        width: parent.width
        spacing: Style.space(10)
        Repeater {
            model: root.guide.steps || []
            delegate: Label {
                required property int index
                required property string modelData
                text: (index + 1) + ". " + modelData
            }
        }
    }

    Column {
        width: parent.width
        spacing: Style.space(6)
        visible: !!root.guide.command
        Label { text: "Or run this command in a terminal:"; opacity: 0.7 }
        Rectangle {
            width: parent.width
            implicitHeight: command.implicitHeight + Style.space(20)
            radius: Style.space(3)
            color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
            border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)
            TextEdit {
                id: command
                objectName: "update-command"
                x: Style.space(10)
                y: Style.space(10)
                width: parent.width - Style.space(20)
                text: root.guide.command || ""
                textFormat: TextEdit.PlainText
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: TextEdit.Wrap
                readOnly: true
                selectByMouse: true
                activeFocusOnTab: true
                selectedTextColor: root.foreground
                selectionColor: Qt.rgba(root.linkColor.r, root.linkColor.g, root.linkColor.b, 0.3)
            }
        }
        Plugin.PanelButton {
            id: copyCommand
            objectName: "update-copy-command"
            text: "Copy command"
            foreground: root.foreground
            fontFamily: root.fontFamily
            outlined: true
            onClicked: { command.selectAll(); command.copy(); command.deselect() }
        }
    }

    Column {
        width: parent.width
        spacing: Style.space(8)
        Plugin.PanelButton {
            id: updateAction
            objectName: "update-action"
            width: parent.width
            visible: !!root.guide.canUpdate
            enabled: !Plugin.Model.updateRunning
            text: Plugin.Model.updateRunning ? "Starting update…" : root.guide.actionLabel || "Update"
            trailingIconName: "arrow-right"
            alignLeft: true
            outlined: true
            foreground: root.linkColor
            fontFamily: root.fontFamily
            onClicked: Plugin.Model.startUpdate()
        }
        Label {
            objectName: "update-status"
            visible: text !== ""
            text: Plugin.Model.updateError || Plugin.Model.updateMessage
            color: Plugin.Model.updateError ? Commons.Color.urgent : root.foreground
        }
        Plugin.PanelButton {
            id: releaseNotes
            objectName: "update-release-notes"
            width: parent.width
            text: "Release notes"
            trailingIconName: "arrow-right"
            alignLeft: true
            foreground: root.foreground
            fontFamily: root.fontFamily
            onClicked: Qt.openUrlExternally(root.guide.releaseUrl || "https://github.com/gelzinn/ai-status/releases/latest")
        }
        Plugin.PanelButton {
            objectName: "update-guide-link"
            width: parent.width
            text: "Full update guide and rollback"
            trailingIconName: "arrow-right"
            alignLeft: true
            foreground: root.foreground
            fontFamily: root.fontFamily
            onClicked: Qt.openUrlExternally(root.guide.guideUrl || "https://github.com/gelzinn/ai-status/blob/main/packages/lib/UPDATES.md")
        }
    }
}
