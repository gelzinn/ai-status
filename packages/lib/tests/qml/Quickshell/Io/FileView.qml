import QtQuick

QtObject {
    property string path: ""
    property bool blockLoading: false
    property string contents: {
        if (!path) return ""
        const request = new XMLHttpRequest()
        request.open("GET", path, false)
        request.send()
        return request.responseText
    }
    function text() { return contents }
}
