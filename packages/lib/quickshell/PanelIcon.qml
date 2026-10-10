import QtQuick
import QtQuick.Shapes

// Lucide paths, matching the landing page's icon family. See LUCIDE-LICENSE.
Item {
    id: root
    property string name: ""
    property color foreground: "white"
    readonly property var paths: ({
        "refresh-cw": "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8 M21 3v5h-5 M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16 M8 16H3v5",
        "settings": "M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915 M15 12a3 3 0 1 0-6 0a3 3 0 1 0 6 0",
        "arrow-left": "M12 19l-7-7 7-7 M19 12H5",
        "arrow-right": "M5 12h14 M12 5l7 7-7 7",
        "arrow-up": "M12 19V5 M5 12l7-7 7 7",
        "arrow-down": "M12 5v14 M19 12l-7 7-7-7",
        "chevron-down": "M6 9l6 6 6-6"
    })
    implicitWidth: 16
    implicitHeight: 16

    Shape {
        width: 24
        height: 24
        anchors.centerIn: parent
        scale: Math.min(root.width, root.height) / 24
        antialiasing: true
        // GeometryRenderer ignores Item.antialiasing. Resolve rounded strokes
        // with MSAA in this small layer, then smoothly scale to the icon size.
        layer.enabled: visible
        layer.samples: 4
        layer.smooth: true
        ShapePath {
            strokeColor: root.foreground
            strokeWidth: 2
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            fillColor: "transparent"
            PathSvg { path: root.paths[root.name] || "" }
        }
    }
}
