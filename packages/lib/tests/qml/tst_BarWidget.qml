import QtQuick
import QtTest
import "plugin" as Plugin

Item {
    width: 1000
    height: 100
    Plugin.BarWidget { id: widget }
    TestCase {
        name: "BarWidget"
        when: windowShown
        function init() {
            Plugin.Model.reset()
            widget.vertical = false
        }
        function test_ordered_items_render_individual_labels_and_logos_and_expand_width() {
            const snapshot = Object.assign({}, Plugin.Model.snapshot)
            snapshot.iconMode = "logo"
            const claude = Qt.resolvedUrl("assets/providers/claude.png").toString().replace("file://", "")
            const codex = Qt.resolvedUrl("assets/providers/codex.png").toString().replace("file://", "")
            snapshot.barItems = [{text: "Claude 25%", logoPath: claude}, {text: "Codex …", logoPath: codex}, {text: "Claude 50%", logoPath: claude}]
            Plugin.Model.snapshot = snapshot
            tryCompare(findChild(widget, "bar-item-logo-0"), "status", Image.Ready)
            tryCompare(findChild(widget, "bar-item-logo-1"), "status", Image.Ready)
            compare(findChild(widget, "bar-item-label-0").text, "Claude 25%")
            compare(findChild(widget, "bar-item-label-1").text, "Codex " + Plugin.Model.spinner)
            compare(findChild(widget, "bar-item-label-2").text, "Claude 50%")
            verify(findChild(widget, "bar-item-logo-0").visible)
            verify(findChild(widget, "bar-item-logo-1").visible)
            const multipleWidth = widget.implicitWidth
            snapshot.barItems = [snapshot.barItems[0]]
            Plugin.Model.snapshot = Object.assign({}, snapshot)
            wait(20)
            verify(widget.implicitWidth < multipleWidth)
            compare(widget.implicitHeight, widget.barSize)
            widget.vertical = true
            compare(widget.implicitWidth, widget.barSize)
            verify(widget.implicitHeight > widget.barSize)
        }
        function test_old_snapshot_and_empty_multi_list_keep_generic_label() {
            Plugin.Model.snapshot = Object.assign({}, Plugin.Model.snapshot, {text: "AI Status", iconMode: "off", barItems: []})
            compare(findChild(widget, "bar-item-label-0").text, "AI Status")
            verify(!findChild(widget, "bar-item-logo-0").visible)
            Plugin.Model.snapshot = Object.assign({}, Plugin.Model.snapshot, {text: "Claude 25%", barItems: undefined})
            compare(findChild(widget, "bar-item-label-0").text, "Claude 25%")
        }
    }
}
