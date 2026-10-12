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
    readonly property var notes: guide.releaseNotes || {}
    readonly property bool hasReleaseNotes: !!version.has_update && !alreadyCurrent && typeof notes.version === "string" && notes.version === version.latest && typeof notes.body === "string" && notes.body.trim() !== ""
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

    // Qt handles Markdown formatting. Raw HTML and inline image loading are
    // disabled here; external links remain available through the browser.
    function safeReleaseNotesMarkdown(body) {
        let fence = ""
        return body.split(/\r?\n/).map(line => {
            const marker = line.match(/^\s{0,3}(`{3,}|~{3,})/)
            if (marker) {
                if (!fence) fence = marker[1]
                else if (marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = ""
                return line
            }
            if (fence) return line
            return line.split(/(`+[^`]*`+)/).map((part, index) => index % 2 ? part : part.replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/!\[/g, "[")).join("")
        }).join("\n")
    }

    function isSafeReleaseNotesLink(link) {
        return /^https?:\/\/[^\s/]+(?:[/?#]|$)/i.test(link) && !/[\u0000-\u0020\u007f]/.test(link)
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
    }

    Column {
        objectName: "update-release-notes-content"
        width: parent.width
        spacing: Style.space(10)
        visible: root.hasReleaseNotes
        Label { text: "What's new"; font.bold: true }
        TextEdit {
            objectName: "update-release-notes-body"
            width: parent.width
            text: root.hasReleaseNotes ? root.safeReleaseNotesMarkdown(root.notes.body) : ""
            textFormat: TextEdit.MarkdownText
            wrapMode: TextEdit.Wrap
            readOnly: true
            selectByMouse: true
            activeFocusOnTab: true
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            selectedTextColor: root.foreground
            selectionColor: Qt.rgba(root.linkColor.r, root.linkColor.g, root.linkColor.b, 0.3)
            Accessible.role: Accessible.StaticText
            Accessible.name: "What's new in v" + (root.notes.version || "")
            onLinkActivated: link => {
                if (root.isSafeReleaseNotesLink(link)) Qt.openUrlExternally(link)
            }
        }
    }

    Column {
        width: parent.width
        spacing: Style.space(6)
        visible: !!root.guide.command
        Plugin.PanelButton {
            id: manualCommand
            outlined: true
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
            outlined: true
            objectName: "update-release-notes"
            width: parent.width
            text: "Release notes"
            trailingIconName: "arrow-right"
            alignLeft: true
            foreground: root.foreground
            fontFamily: root.fontFamily
            onClicked: Qt.openUrlExternally(root.hasReleaseNotes && root.isSafeReleaseNotesLink(root.notes.url || "") ? root.notes.url : root.guide.releaseUrl || "https://github.com/gelzinn/ai-status/releases/latest")
        }
        Plugin.PanelButton {
            objectName: "update-guide-link"
            outlined: true
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
