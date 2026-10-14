import QtQuick
import qs.Commons
import qs.Commons as Commons
import "." as Plugin

Plugin.PanelButton {
    id: root
    property var choices: []
    property int currentIndex: -1
    property bool multiple: false
    property real popupWidth: width
    property Item popupParent: parent
    property bool popupOpen: false
    property int highlighted: -1
    readonly property alias popupItem: overlay
    signal activated(int index)
    alignLeft: true
    outlined: true
    trailingIconName: "chevron-down"
    Accessible.role: Accessible.ComboBox
    onClicked: popupOpen = !popupOpen
    onVisibleChanged: if (!visible) popupOpen = false
    onEnabledChanged: if (!enabled) popupOpen = false
    onPopupOpenChanged: {
        if (popupOpen) {
            highlighted = Math.max(0, currentIndex)
            Qt.callLater(() => {
                if (popupOpen) {
                    menu.trigger = root.mapToItem(overlay, 0, root.height)
                    overlay.forceActiveFocus()
                    revealHighlight()
                }
            })
        } else if (visible && enabled) forceActiveFocus()
    }
    function dismiss() { popupOpen = false }
    function choose(index) {
        if (index < 0 || index >= choices.length) return
        highlighted = index
        activated(index)
        if (!multiple) dismiss()
        else Qt.callLater(() => {
            if (popupOpen) {
                overlay.forceActiveFocus()
                revealHighlight()
            }
        })
    }
    function revealHighlight() {
        const item = options.itemAt(highlighted)
        if (!item) return
        let top = item.y
        const groupKey = choices[highlighted].groupKey
        if (groupKey) {
            let first = highlighted
            while (first > 0 && choices[first - 1].groupKey === groupKey) first--
            const header = options.itemAt(first)
            // Keep the account heading visible along with the focused limit.
            if (header && item.y + item.height - header.y <= list.height) top = header.y
        }
        if (top < list.contentY) list.contentY = top
        else if (item.y + item.height > list.contentY + list.height)
            list.contentY = item.y + item.height - list.height
    }

    // The overlay belongs to the panel, so neither selector changes the form's size.
    FocusScope {
        id: overlay
        parent: root.popupParent
        anchors.fill: parent
        z: 100
        visible: root.popupOpen && root.visible
        Keys.onPressed: event => {
            if (event.key === Qt.Key_Escape) root.dismiss()
            else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) root.choose(root.highlighted)
            else if (event.key === Qt.Key_Up) root.highlighted = Math.max(0, root.highlighted - 1)
            else if (event.key === Qt.Key_Down) root.highlighted = Math.min(root.choices.length - 1, root.highlighted + 1)
            else if (event.key === Qt.Key_Home) root.highlighted = 0
            else if (event.key === Qt.Key_End) root.highlighted = root.choices.length - 1
            else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
                root.dismiss()
                root.nextItemInFocusChain(event.key === Qt.Key_Tab).forceActiveFocus(Qt.TabFocusReason)
            } else return
            root.revealHighlight()
            event.accepted = true
        }
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onClicked: root.dismiss()
            onWheel: event => { event.accepted = true }
        }
        Rectangle {
            id: menu
            objectName: root.objectName + "-menu"
            property point trigger: Qt.point(0, 0)
            width: Math.min(root.popupWidth, overlay.width)
            height: Math.min(optionColumn.implicitHeight + Style.space(8), Style.space(280), Math.max(0, overlay.height - Style.space(8)))
            x: Math.max(0, Math.min(trigger.x, overlay.width - width))
            y: Math.max(0, Math.min(trigger.y + Style.space(4) + height <= overlay.height ? trigger.y + Style.space(4) : trigger.y - root.height - height - Style.space(4), overlay.height - height))
            color: Qt.rgba(Commons.Color.popups.background.r, Commons.Color.popups.background.g, Commons.Color.popups.background.b, 1)
            border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.25)
            radius: Style.cornerRadius
            MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons }
            Flickable {
                id: list
                anchors.fill: parent
                anchors.margins: Style.space(4)
                contentWidth: width
                contentHeight: optionColumn.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Column {
                    id: optionColumn
                    width: list.width
                    Repeater {
                        id: options
                        model: root.choices
                        delegate: Column {
                            id: option
                            required property var modelData
                            required property int index
                            readonly property bool startsGroup: !!modelData.groupKey && (index === 0 || root.choices[index - 1].groupKey !== modelData.groupKey)
                            width: optionColumn.width
                            Item {
                                objectName: root.objectName + "-group-" + option.modelData.groupKey
                                visible: option.startsGroup
                                width: parent.width
                                height: visible ? Style.space(option.index === 0 ? 32 : 40) : 0
                                Rectangle {
                                    visible: option.index > 0
                                    width: parent.width - Style.space(12)
                                    x: Style.space(6)
                                    height: 1
                                    color: root.foreground
                                    opacity: 0.12
                                }
                                Image {
                                    anchors.left: parent.left
                                    anchors.leftMargin: Style.space(10)
                                    anchors.bottom: parent.bottom
                                    anchors.bottomMargin: Style.space(8)
                                    width: Style.space(16)
                                    height: width
                                    source: option.modelData.groupLogoSource || ""
                                    fillMode: Image.PreserveAspectFit
                                    asynchronous: true
                                }
                                Text {
                                    anchors.left: parent.left
                                    anchors.leftMargin: Style.space(34)
                                    anchors.right: parent.right
                                    anchors.rightMargin: Style.space(10)
                                    anchors.bottom: parent.bottom
                                    anchors.bottomMargin: Style.space(8)
                                    text: option.modelData.groupLabel || ""
                                    textFormat: Text.PlainText
                                    color: root.foreground
                                    font.family: root.fontFamily
                                    font.pixelSize: Style.font.body
                                    font.bold: true
                                    elide: Text.ElideRight
                                    Accessible.role: Accessible.StaticText
                                    Accessible.name: text
                                }
                            }
                            Plugin.PanelButton {
                                objectName: option.modelData.objectName || root.objectName + "-option-" + option.index
                                width: optionColumn.width
                                text: option.modelData.label
                                multiline: root.multiple
                                logoSource: option.modelData.logoSource || ""
                                prefixText: root.multiple ? (option.modelData.checked ? "[x]" : "[ ]")
                                    : option.modelData.groupKey ? (root.currentIndex === option.index ? "✓" : " ") : ""
                                foreground: root.foreground
                                fontFamily: root.fontFamily
                                alignLeft: true
                                activeFocusOnTab: false
                                color: root.highlighted === option.index ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12) : "transparent"
                                Accessible.name: option.modelData.groupLabel ? option.modelData.groupLabel + " · " + text : text
                                Accessible.role: root.multiple ? Accessible.CheckBox : Accessible.Button
                                Accessible.checked: root.multiple && !!option.modelData.checked
                                Accessible.selected: root.multiple ? !!option.modelData.checked : root.currentIndex === option.index
                                onClicked: root.choose(option.index)
                            }
                        }
                    }
                }
            }
        }
    }
}
