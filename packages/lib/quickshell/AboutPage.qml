import QtQuick
import qs.Commons
import "." as Plugin

Column {
    id: root
    property color foreground: "white"
    property string fontFamily: Style.font.family
    readonly property var info: Plugin.Model.snapshot.about || {}
    signal guideRequested()
    spacing: Style.space(16)
    function focusFirstControl() {
        const first = projectLinks.itemAt(0)
        if (first) first.forceActiveFocus(Qt.TabFocusReason)
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
        Image {
            source: Qt.resolvedUrl("../assets/app.png")
            width: Style.space(40)
            height: width
            fillMode: Image.PreserveAspectFit
        }
        Label { text: root.info.name || "AI Status"; font.bold: true; font.pixelSize: Style.font.body + 3 }
        Label { text: root.info.description || "Monitor AI provider usage limits from your desktop." }
        Label {
            objectName: "about-metadata"
            text: "Version: v" + (root.info.version || "—") + "\nCommit: " + (root.info.commit || "Unavailable") + "\nLicense: " + (root.info.license || "MIT") + "\nAuthor: " + (root.info.author || "gelzin.com")
            opacity: 0.7
        }
    }
    Column {
        width: parent.width
        spacing: Style.space(6)
        Repeater {
            id: projectLinks
            model: [
                {key: "guide", label: "Guide", url: ""},
                {key: "issues", label: "Report a bug", url: root.info.issues},
                {key: "documentation", label: "Documentation", url: root.info.documentation},
                {key: "github", label: "GitHub", url: root.info.github}
            ]
            delegate: Plugin.PanelButton {
                required property var modelData
                objectName: "about-link-" + modelData.key
                width: parent.width
                text: modelData.label
                alignLeft: true
                outlined: true
                trailingIconName: "arrow-right"
                foreground: root.foreground
                fontFamily: root.fontFamily
                enabled: modelData.key === "guide" || !!modelData.url
                onClicked: modelData.key === "guide" ? root.guideRequested() : Qt.openUrlExternally(modelData.url)
            }
        }
    }
}
