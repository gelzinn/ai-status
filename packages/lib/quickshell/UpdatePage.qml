import QtQuick
import qs.Commons
import "." as Plugin

Column {
    id: root
    property color foreground: "white"
    property string fontFamily: Style.font.family
    readonly property color linkColor: "#89b4fa"
    readonly property var guide: Plugin.Model.snapshot.update || {}
    readonly property var version: Plugin.Model.snapshot.version || {}
    readonly property bool alreadyCurrent: version.has_update === false || (!Plugin.Model.updateRunning && Plugin.Model.updateError === "" && Plugin.Model.updateMessage.indexOf("already up to date") !== -1)
    property Item actionControl: null
    property bool commandExpanded: false
    readonly property bool showCommand: !guide.canUpdate || commandExpanded
    property bool commandCopied: false
    spacing: Style.space(16)

    function focusFirstControl() {
        if (actionControl && actionControl.visible && actionControl.enabled) actionControl.forceActiveFocus()
        else if (manualCommand.visible) manualCommand.forceActiveFocus()
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
        Label { text: "Latest stable version"; font.bold: true }
        Label {
            objectName: "update-versions"
            text: "v" + (root.version.current || "—") +
                  (!root.alreadyCurrent && root.version.latest && root.version.latest !== root.version.current ? "  →  v" + root.version.latest : "")
            opacity: 0.7
        }
        Label {
            objectName: "update-description"
            text: root.alreadyCurrent ? "Your settings are kept." : root.guide.description || "See the update guide for your installation."
        }
    }

    Column {
        width: parent.width
        spacing: Style.space(6)
        visible: !!root.guide.command
        Plugin.PanelButton {
            id: manualCommand
            objectName: "update-manual-command"
            width: parent.width
            visible: !!root.guide.canUpdate
            text: root.showCommand ? "Hide manual update" : "Update manually…"
            trailingIconName: "chevron-down"
            alignLeft: true
            foreground: root.foreground
            fontFamily: root.fontFamily
            onClicked: root.commandExpanded = !root.showCommand
        }
        Rectangle {
            objectName: "update-command-box"
            width: parent.width
            visible: root.showCommand
            implicitHeight: Math.max(command.implicitHeight + Style.space(20), Style.space(50))
            radius: Style.cornerRadius
            color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
            border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)
            TextEdit {
                id: command
                objectName: "update-command"
                x: Style.space(10)
                y: Style.space(10)
                width: Math.max(0, parent.width - Style.space(58))
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
            Plugin.PanelButton {
                id: copyCommand
                objectName: "update-copy-command"
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: Style.space(8)
                width: Style.space(30)
                text: root.commandCopied ? "Copied" : "Copy command"
                iconName: root.commandCopied ? "check" : "copy"
                foreground: root.foreground
                fontFamily: root.fontFamily
                onClicked: {
                    command.selectAll()
                    command.copy()
                    command.deselect()
                    root.commandCopied = true
                    copiedFeedback.restart()
                }
            }
        }
    }

    Timer {
        id: copiedFeedback
        interval: 2000
        onTriggered: root.commandCopied = false
    }

    Connections {
        target: Plugin.Model
        function onUpdateErrorChanged() {
            if (Plugin.Model.updateError !== "") root.commandExpanded = true
        }
    }

    Column {
        width: parent.width
        spacing: Style.space(8)
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
            text: "Installation guide"
            trailingIconName: "arrow-right"
            alignLeft: true
            foreground: root.foreground
            fontFamily: root.fontFamily
            onClicked: Qt.openUrlExternally(root.guide.guideUrl || "https://github.com/gelzinn/ai-status/blob/main/packages/lib/UPDATES.md")
        }
    }
}
