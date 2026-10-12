import QtQuick
import QtTest

Rectangle {
    id: maskContainer
    width: 100
    height: 100
    color: "#112233"
    Item {
        id: masked
        width: 100
        height: 100
        layer.enabled: GraphicsInfo.api !== GraphicsInfo.Software
        layer.effect: ShaderEffect {
            property var source
            property real fadeStart: 0.25
            property real fadeEnd: 0.75
            fragmentShader: Qt.resolvedUrl("plugin/scroll-fade.frag.qsb")
        }
        Rectangle { anchors.fill: parent; color: "#4c99e6" }
    }
    TestCase {
        name: "ScrollFade"
        when: windowShown
        function test_mask_changes_alpha_without_tinting_content() {
            if (GraphicsInfo.api === GraphicsInfo.Software) skip("ShaderEffect needs the OpenGL renderer; run with AI_STATUS_QML_RENDERER=opengl.")
            waitForRendering(masked)
            for (const background of ["#112233", "#ddeeff"]) {
                maskContainer.color = background
                waitForRendering(maskContainer)
                const image = grabImage(maskContainer)
                const top = image.pixel(50, 10)
                const middle = image.pixel(50, 50)
                const bottom = image.pixel(50, 90)
                compare(top, maskContainer.color)
                compare(bottom, Qt.rgba(76 / 255, 153 / 255, 230 / 255, 1))
                verify(Math.abs(middle.r - (top.r + bottom.r) / 2) < 0.02)
                verify(Math.abs(middle.g - (top.g + bottom.g) / 2) < 0.02)
                verify(Math.abs(middle.b - (top.b + bottom.b) / 2) < 0.02)
            }
        }
    }
}
