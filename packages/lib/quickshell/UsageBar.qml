import QtQuick
import qs.Commons

Rectangle {
    id: root
    property real percentage: 0
    property bool active: false
    property bool loading: false
    property int groupIndex: 0
    property color foreground: "#eeeeee"
    property real displayed: 0
    property real fillOpacity: 1
    property real phase: 0
    property bool mounted: false
    readonly property real target: Math.max(0, Math.min(100, percentage))
    readonly property bool shimmering: shimmer.running
    readonly property bool filling: fill.running
    implicitHeight: Style.space(15)
    radius: Style.space(1)
    color: Qt.rgba(foreground.r, foreground.g, foreground.b, loading ? 0.055 : 0.03)
    border.width: 1
    border.color: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.09)
    clip: true

    function startFill() {
        if (loading || !visible) return
        fill.stop()
        widthAnimation.from = displayed
        opacityAnimation.from = fillOpacity
        mounted = true
        fill.start()
    }
    function updateAnimation() {
        delay.stop()
        if (!visible) {
            fill.stop()
            if (mounted) { displayed = target; fillOpacity = 1 }
        } else if (loading) {
            fill.stop()
            fillOpacity = 0
        } else if (mounted) startFill()
        else delay.start()
    }
    onTargetChanged: updateAnimation()
    onLoadingChanged: updateAnimation()
    onVisibleChanged: updateAnimation()
    Component.onCompleted: updateAnimation()

    Timer {
        id: delay
        interval: 100 + root.groupIndex * 150
        onTriggered: root.startFill()
    }
    ParallelAnimation {
        id: fill
        NumberAnimation {
            id: widthAnimation
            target: root
            property: "displayed"
            to: root.target
            duration: 1500
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [0.16, 1, 0.3, 1, 1, 1]
        }
        NumberAnimation {
            id: opacityAnimation
            target: root
            property: "fillOpacity"
            to: 1
            duration: 1500
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [0.16, 1, 0.3, 1, 1, 1]
        }
    }
    NumberAnimation {
        id: shimmer
        target: root
        property: "phase"
        from: 0
        to: 1
        duration: 1500
        loops: Animation.Infinite
        running: root.loading && root.visible
    }
    Item {
        anchors.fill: parent
        anchors.margins: 1
        clip: true
        Rectangle {
            visible: !root.loading
            width: parent.width * root.displayed / 100
            height: parent.height
            color: root.foreground
            opacity: root.fillOpacity * (root.active ? 1 : 0.36)
        }
        Rectangle {
            visible: root.loading
            x: (2 * root.phase - 1) * width
            width: parent.width
            height: parent.height
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: 0.5; color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.15) }
                GradientStop { position: 1; color: "transparent" }
            }
        }
    }
}
