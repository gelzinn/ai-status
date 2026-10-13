import QtQuick
import qs.Commons
import qs.Ui as Ui
import "." as Plugin

Ui.BarWidget {
    id: root
    moduleName: "io.github.gelzinn.ai-status"
    readonly property bool opened: panelLoader.item ? panelLoader.item.opened : false
    readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing : false

    function open() { if (panelLoader.item) panelLoader.item.open() }
    function close() { if (panelLoader.item) panelLoader.item.close() }
    function toggle() { if (panelLoader.item) panelLoader.item.toggle() }
    function configure() { if (panelLoader.item) panelLoader.item.configure() }
    function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }
    function injectPanel() {
        if (!panelLoader.item) return
        panelLoader.item.bar = root.bar
        panelLoader.item.anchorItem = button
        panelLoader.item.hostWidget = root
    }

    implicitWidth: vertical ? barSize : content.implicitWidth + Style.space(17)
    implicitHeight: vertical ? content.implicitWidth + Style.space(17) : barSize
    onBarChanged: injectPanel()
    Component.onCompleted: Plugin.Model.acquire(root)
    Component.onDestruction: Plugin.Model.release(root)

    Connections {
        target: Plugin.Model
        function onNotificationActivated() {
            if (Plugin.Model.notificationOwner !== root || !panelLoader.item) return
            panelLoader.item.showUsage()
            root.open()
        }
    }

    Loader {
        id: panelLoader
        active: true
        visible: false
        source: Qt.resolvedUrl("Panel.qml")
        onLoaded: {
            root.injectPanel()
            Qt.callLater(root.injectPanel)
        }
    }

    Ui.WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        fixedWidth: root.width
        fixedHeight: root.height
        labelVisible: false
        hasVisualContent: true
        tooltipText: ""
        Accessible.name: "AI Status"
        onPressed: buttonCode => {
            if (buttonCode === Qt.LeftButton) root.toggle()
            else if (buttonCode === Qt.RightButton) root.configure()
            else if (buttonCode === Qt.MiddleButton) Plugin.Model.action("cycle-metric")
        }
        onWheelMoved: delta => {
            if (delta !== 0) Plugin.Model.action(delta > 0 ? "scroll-up" : "scroll-down")
        }

        Row {
            id: content
            anchors.centerIn: parent
            spacing: Style.spacing.controlGap
            rotation: root.vertical ? 90 : 0
            Repeater {
                model: Plugin.Model.snapshot.barItems && Plugin.Model.snapshot.barItems.length
                    ? Plugin.Model.snapshot.barItems : [{text: Plugin.Model.snapshot.text || "AI Status", logoPath: Plugin.Model.snapshot.logoPath || ""}]
                delegate: Row {
                    required property var modelData
                    required property int index
                    objectName: "bar-item-" + index
                    spacing: Style.spacing.controlGap
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        visible: index > 0
                        text: "·"
                        color: button.foreground
                        opacity: 0.5
                        font.family: button.fontFamily
                        font.pixelSize: Style.font.body
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Image {
                        objectName: "bar-item-logo-" + index
                        source: modelData.logoPath ? "file://" + modelData.logoPath : ""
                        visible: Plugin.Model.snapshot.iconMode === "logo" && status === Image.Ready
                        width: visible ? Style.font.icon : 0
                        height: Style.font.icon
                        anchors.verticalCenter: parent.verticalCenter
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }
                    Text {
                        objectName: "bar-item-label-" + index
                        text: (modelData.text || "AI Status").replace(/…/g, Plugin.Model.spinner)
                        textFormat: Text.PlainText
                        color: button.foreground
                        font.family: button.fontFamily
                        font.pixelSize: Style.font.body
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }
}
