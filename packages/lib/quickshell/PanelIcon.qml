import QtQuick
import QtQuick.Shapes
import "." as Plugin

// Shared native-panel Lucide geometry. See LUCIDE-LICENSE.
Item {
    id: root
    property string name: ""
    property color foreground: "white"
    readonly property string pathData: Plugin.PanelIcons.path(name)
    implicitWidth: Plugin.PanelIcons.data.size
    implicitHeight: Plugin.PanelIcons.data.size

    Shape {
        width: Plugin.PanelIcons.data.viewBox
        height: width
        anchors.centerIn: parent
        scale: Math.min(root.width, root.height) / width
        antialiasing: true
        // GeometryRenderer ignores Item.antialiasing. Resolve rounded strokes
        // with MSAA in this small layer, then smoothly scale to the icon size.
        layer.enabled: visible
        layer.samples: 4
        layer.smooth: true
        ShapePath {
            strokeColor: root.foreground
            strokeWidth: Plugin.PanelIcons.data.strokeWidth
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            fillColor: "transparent"
            PathSvg { path: root.pathData }
        }
    }
}
