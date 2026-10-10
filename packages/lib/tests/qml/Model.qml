pragma Singleton
import QtQuick
Item {
    property var saved: null
    property bool settingsSaving: false
    property string settingsError: ""
    property string spinner: "⠋"
    property var snapshot: ({})
    function saveSettings(settings) { saved = settings }
    function reset() {
        saved = null
        settingsError = ""
        snapshot = {
            selected: {provider: "claude", idx: 0, metric: "rolling"},
            providers: [
                {id: "claude", idx: 0, name: "Claude (Max)", logoPath: "", loading: false, cached: false, error: "", metrics: [
                    {key: "rolling", name: "Rolling Usage", percentage: 2, detail: "Resets in 4h 55m"},
                    {key: "weekly", name: "Weekly Usage", percentage: 24, detail: "Resets in 3d 16h"},
                    {key: "weekly:Fable", name: "Weekly Usage", percentage: 53, detail: "Fable · Resets in 3d 16h"}
                ]},
                {id: "codex", idx: 0, name: "Codex (Plus)", logoPath: "", loading: false, cached: false, error: "", metrics: [
                    {key: "rolling", name: "Rolling Usage", percentage: 3, detail: "Resets in 4h 25m"},
                    {key: "weekly", name: "Weekly Usage", percentage: 25, detail: "Resets in 6d 12h"}
                ]}
            ],
            settings: {
                order: ["claude", "codex", "kiro"], enabled: ["claude", "codex"],
                display: {show_provider: true, show_model: true, show_metric: false, show_pct: true},
                iconMode: "logo"
            }
        }
    }
}
