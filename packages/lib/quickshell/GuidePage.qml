import QtQuick
import qs.Commons

Column {
    id: root
    property color foreground: "white"
    property string fontFamily: Style.font.family
    readonly property var rows: [
        {id: "open", feature: "Open Usage", action: "Click the bar icon."},
        {id: "settings", feature: "Settings", action: "Right-click the bar or press C on Usage."},
        {id: "refresh", feature: "Refresh", action: "Refresh button or R on Usage."},
        {id: "providers", feature: "Switch providers", action: "Scroll on the bar."},
        {id: "limits", feature: "Switch limits", action: "Middle-click the bar."},
        {id: "select", feature: "Choose a limit", action: "Click a limit on Usage."},
        {id: "tabs", feature: "Switch tabs", action: "Click a tab or use Left / Right on tabs. Scroll the strip to reveal more."},
        {id: "focus", feature: "Move focus", action: "Tab / Shift+Tab."},
        {id: "activate", feature: "Activate", action: "Space / Enter when focused."},
        {id: "selector", feature: "Choose an option", action: "Up / Down in an open select, then Enter. Esc closes it."},
        {id: "thresholds", feature: "Adjust alert levels", action: "Drag a slider or use Left / Right when focused."},
        {id: "order", feature: "Reorder providers", action: "Row arrows in Providers."},
        {id: "save", feature: "Save settings", action: "Save applies all tabs and keeps Settings open."},
        {id: "cancel", feature: "Cancel settings", action: "Cancel, Back or Esc returns to Usage without saving."},
        {id: "credits", feature: "Credit details", action: "Click a reset-credit or cloud-credit row."}
    ]
    spacing: Style.space(16)
    function tokens(action) {
        const pattern = /Shift\+Tab|\b(?:Tab|Esc|Space|Enter|Left|Right|Up|Down|C|R)\b(?![-\w])/g
        let result = [], end = 0, match
        function words(value) {
            return value.trim().split(/\s+/).filter(value => value).map(value => ({text: value, key: false}))
        }
        while ((match = pattern.exec(action)) !== null) {
            result = result.concat(words(action.slice(end, match.index)))
            result.push({text: match[0], key: true})
            end = pattern.lastIndex
        }
        return result.concat(words(action.slice(end)))
    }
    component Label: Text {
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        wrapMode: Text.WordWrap
    }
    Column {
        width: parent.width
        spacing: Style.space(4)
        Label { text: "Guide"; font.bold: true }
        Label { width: parent.width; text: "Everyday actions and keyboard shortcuts."; opacity: 0.5; font.pixelSize: Style.font.caption }
    }
    Rectangle {
        id: frame
        objectName: "guide-table"
        width: parent.width
        height: table.implicitHeight + 2
        radius: Style.cornerRadius
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.15)
        readonly property real labelWidth: table.width * 0.35
        Rectangle {
            x: 1
            y: 1
            width: frame.labelWidth
            height: parent.height - 2
            color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04)
        }
        Rectangle {
            x: frame.labelWidth + 1
            y: 1
            width: 1
            height: parent.height - 2
            color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.09)
        }
        Column {
            id: table
            x: 1
            y: 1
            width: parent.width - 2
            Item {
                width: parent.width
                height: Math.max(headerLeft.implicitHeight, headerRight.implicitHeight) + Style.space(24)
                Label { id: headerLeft; x: Style.space(12); y: Style.space(12); width: frame.labelWidth - Style.space(24); text: "Feature"; font.bold: true }
                Label { id: headerRight; x: frame.labelWidth + Style.space(12); y: Style.space(12); width: parent.width - x - Style.space(12); text: "Action or shortcut"; font.bold: true }
            }
            Repeater {
                model: root.rows
                delegate: Item {
                    required property var modelData
                    width: table.width
                    implicitHeight: Math.max(title.implicitHeight, value.implicitHeight) + Style.space(24)
                    Rectangle { width: parent.width; height: 1; color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.09) }
                    Label {
                        id: title
                        objectName: "guide-feature-" + parent.modelData.id
                        x: Style.space(12)
                        y: Style.space(12)
                        width: frame.labelWidth - Style.space(24)
                        text: parent.modelData.feature
                        opacity: 0.55
                    }
                    Flow {
                        id: value
                        objectName: "guide-action-" + parent.modelData.id
                        x: frame.labelWidth + Style.space(12)
                        y: Style.space(12)
                        width: parent.width - x - Style.space(12)
                        spacing: Style.space(4)
                        Repeater {
                            model: root.tokens(value.parent.modelData.action)
                            delegate: Rectangle {
                                required property var modelData
                                objectName: modelData.key ? "guide-keycap-" + modelData.text : ""
                                width: word.implicitWidth + (modelData.key ? Style.space(8) : 0)
                                height: word.implicitHeight + Style.space(4)
                                radius: Style.space(3)
                                color: modelData.key ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.04) : "transparent"
                                border.width: modelData.key ? 1 : 0
                                border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.2)
                                Label { id: word; anchors.centerIn: parent; text: parent.modelData.text; font.pixelSize: Style.font.caption }
                            }
                        }
                    }
                }
            }
        }
    }
}
