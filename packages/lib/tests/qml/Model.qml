pragma Singleton
import QtQuick
Item {
    signal settingsSaved()
    property string errorMessage: ""
    property var actions: []
    function action(command) { actions = actions.concat([command]) }
    property var saved: null
    property var chosen: null
    property bool settingsSaving: false
    property string settingsError: ""
    property string spinner: "⠋"
    property var snapshot: ({})
    function saveSettings(settings) { saved = settings }
    function selectMetric(provider, idx, metric) { chosen = {provider: provider, idx: idx, metric: metric} }
    function reset() {
        actions = []
        saved = null
        chosen = null
        settingsError = ""
        snapshot = {
            about: {name: "AI Status", version: "0.9.0", commit: "12345678", license: "MIT", author: "gelzin.com", github: "https://github.com/gelzinn/ai-status", documentation: "https://github.com/gelzinn/ai-status#readme", issues: "https://github.com/gelzinn/ai-status/issues/new"},
            loading: false,
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
                names: {claude: "Claude", codex: "Codex", kiro: "Kiro"},
                order: ["claude", "codex", "kiro"], enabled: ["claude", "codex"],
                display: {show_provider: true, show_model: true, show_metric: false, show_pct: true},
                iconMode: "logo"
            }
        }
    }
}
