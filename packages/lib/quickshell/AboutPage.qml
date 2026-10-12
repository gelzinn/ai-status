import QtQuick
import qs.Commons
import "." as Plugin

Column {
    id: root
    property color foreground: "white"
    property string fontFamily: Style.font.family
    readonly property var info: Plugin.Model.snapshot.about || {}
    spacing: Style.space(20)
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
            model: [
                {label: "GitHub", url: root.info.github},
                {label: "Documentation", url: root.info.documentation},
                {label: "Report a bug", url: root.info.issues}
            ]
            delegate: Plugin.PanelButton {
                required property var modelData
                width: parent.width
                text: modelData.label
                alignLeft: true
                outlined: true
                trailingIconName: "arrow-right"
                foreground: root.foreground
                fontFamily: root.fontFamily
                enabled: !!modelData.url
                onClicked: Qt.openUrlExternally(modelData.url)
            }
        }
    }
    Column {
        width: parent.width
        spacing: Style.space(10)
        Label { text: "Quick guide"; font.bold: true }
        Label { text: "Bar: click to show usage; right-click to open settings. Scroll to switch providers; middle-click to switch limits." }
        Label { text: "Usage: click a limit to show it in the bar. Refresh checks now; Reset credits shows the available resets. Update available opens the update guide." }
        Label { text: "Settings: use General, Appearance, Alerts and Providers to configure the bar and quota notifications. Save applies all changes and keeps settings open." }
        Label { text: "Keyboard: R refreshes, C opens settings, Esc goes back. Tab moves between controls; arrows move through selector options." }
    }
}
