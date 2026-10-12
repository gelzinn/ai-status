// Native macOS adapter. Provider collection and preferences remain in Python.
// Build with swiftc -parse-as-library -framework Cocoa -framework SwiftUI -framework UserNotifications.
import Cocoa
import CoreText
import Darwin
import SwiftUI
import UserNotifications

private let commandNotification = Notification.Name("com.gelzin.ai-status.command")

struct RuntimeConfig: Decodable {
    let python: String
    let cli: String

    static func load() throws -> RuntimeConfig {
        guard let url = Bundle.main.url(forResource: "runtime", withExtension: "json") else {
            throw AppError.message("Runtime configuration is missing. Run the macOS installer again.")
        }
        let config = try JSONDecoder().decode(RuntimeConfig.self, from: Data(contentsOf: url))
        guard config.python.hasPrefix("/"), config.cli.hasPrefix("/"),
              FileManager.default.isExecutableFile(atPath: config.python),
              FileManager.default.isReadableFile(atPath: config.cli) else {
            throw AppError.message("Python or AI Status is unavailable. Run the macOS installer again.")
        }
        return config
    }

    func process(_ arguments: [String]) -> Process {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments = [cli] + arguments
        var environment = ProcessInfo.processInfo.environment
        let directories = [NSHomeDirectory() + "/.local/bin", "/opt/homebrew/bin", "/usr/local/bin",
                           environment["PATH"] ?? "", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
        environment["PATH"] = directories.filter { !$0.isEmpty }.joined(separator: ":")
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment
        process.currentDirectoryURL = URL(fileURLWithPath: cli).deletingLastPathComponent()
        return process
    }
}

enum AppError: LocalizedError {
    case message(String)
    var errorDescription: String? { if case .message(let value) = self { return value }; return nil }
}

struct Selection: Codable, Hashable {
    var provider: String = ""
    var idx: Int = 0
    var metric: String = ""
    init(provider: String = "", idx: Int = 0, metric: String = "") {
        self.provider = provider; self.idx = idx; self.metric = metric
    }
    enum CodingKeys: String, CodingKey { case provider, idx, metric }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        provider = try values.decodeIfPresent(String.self, forKey: .provider) ?? ""
        idx = try values.decodeIfPresent(Int.self, forKey: .idx) ?? 0
        metric = try values.decodeIfPresent(String.self, forKey: .metric) ?? ""
    }
}

struct Metric: Decodable, Identifiable {
    let key: String
    let name: String
    let percentage: Double?
    let value: String?
    let isAmount: Bool
    let detail: String
    var id: String { key }
    var displayValue: String {
        if let value = value, !value.isEmpty { return value }
        if let percentage = percentage { return String(format: "%.0f%%", percentage) }
        return "Unavailable"
    }
    var usable: Bool { percentage.map { $0.isFinite } ?? (value?.isEmpty == false) }
    enum CodingKeys: String, CodingKey { case key, name, percentage, value, isAmount, detail }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        key = try values.decode(String.self, forKey: .key)
        name = try values.decode(String.self, forKey: .name)
        percentage = try values.decodeIfPresent(Double.self, forKey: .percentage)
        value = try values.decodeIfPresent(String.self, forKey: .value)
        isAmount = try values.decodeIfPresent(Bool.self, forKey: .isAmount) ?? false
        detail = try values.decode(String.self, forKey: .detail)
    }
}

struct CreditRow: Decodable {
    let title: String
    let count: Int
    let expires: String
    let remaining: String
    let timezone: String
}

struct ResetCredits: Decodable {
    let available: Int
    let rows: [CreditRow]
    let undetailed: Int
    let timezone: String?
}

struct MonetaryCredit: Decodable, Identifiable {
    let id: String
    let title: String
    let heading: String?
    let status: String
    let value: String
    let expires: String
    let remaining: String
    let timezone: String
    let observed: String
    let observedValue: String
    let limitValue: String
    let usedValue: String
    let statusNote: String
    let stale: Bool
    enum CodingKeys: String, CodingKey {
        case id, title, heading, status, value, expires, remaining, timezone, observed, stale
        case observedValue = "observed_value", limitValue = "limit_value", usedValue = "used_value"
        case statusNote = "status_note"
    }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(String.self, forKey: .id)
        title = try values.decode(String.self, forKey: .title)
        heading = try values.decodeIfPresent(String.self, forKey: .heading)
        status = try values.decode(String.self, forKey: .status)
        value = try values.decode(String.self, forKey: .value)
        expires = try values.decodeIfPresent(String.self, forKey: .expires) ?? "Not reported"
        remaining = try values.decodeIfPresent(String.self, forKey: .remaining) ?? "Not reported"
        timezone = try values.decodeIfPresent(String.self, forKey: .timezone) ?? ""
        observed = try values.decodeIfPresent(String.self, forKey: .observed) ?? "Not reported"
        observedValue = try values.decodeIfPresent(String.self, forKey: .observedValue) ?? "Not reported"
        limitValue = try values.decodeIfPresent(String.self, forKey: .limitValue) ?? "Not reported"
        usedValue = try values.decodeIfPresent(String.self, forKey: .usedValue) ?? "Not reported"
        statusNote = try values.decodeIfPresent(String.self, forKey: .statusNote) ?? ""
        stale = try values.decodeIfPresent(Bool.self, forKey: .stale) ?? false
    }
}

struct Provider: Decodable, Identifiable {
    let connectionID: String
    let providerID: String
    let idx: Int
    let name: String
    let logoPath: String
    let loading: Bool
    let cached: Bool
    let error: String
    let metrics: [Metric]
    let resetCredits: ResetCredits?
    let monetaryCredits: [MonetaryCredit]
    var id: String { "\(connectionID):\(idx)" }
    enum CodingKeys: String, CodingKey {
        case connectionID = "id"
        case providerID = "providerId"
        case idx, name, logoPath, loading, cached, error, metrics, resetCredits, monetaryCredits
    }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        connectionID = try values.decode(String.self, forKey: .connectionID)
        providerID = try values.decodeIfPresent(String.self, forKey: .providerID) ?? connectionID
        idx = try values.decode(Int.self, forKey: .idx)
        name = try values.decode(String.self, forKey: .name)
        logoPath = try values.decode(String.self, forKey: .logoPath)
        loading = try values.decode(Bool.self, forKey: .loading)
        cached = try values.decode(Bool.self, forKey: .cached)
        error = try values.decode(String.self, forKey: .error)
        metrics = try values.decode([Metric].self, forKey: .metrics)
        resetCredits = try values.decodeIfPresent(ResetCredits.self, forKey: .resetCredits)
        monetaryCredits = try values.decodeIfPresent([MonetaryCredit].self, forKey: .monetaryCredits) ?? []
    }
    func selection(_ metric: Metric) -> Selection {
        Selection(provider: connectionID, idx: idx, metric: metric.key)
    }
    func monetaryCredit(_ metric: Metric) -> MonetaryCredit? {
        monetaryCredits.first { metric.key == "credits:" + $0.id }
    }
}

struct Settings: Decodable {
    let available: [String]
    let names: [String: String]
    let providerIds: [String: String]?
    let order: [String]
    let enabled: [String]
    let display: [String: Bool]
    let iconMode: String
    let usageDisplay: String?
    let notifications: NotificationPreferences?
}

struct NotificationHours: Codable {
    var start = ""
    var end = ""
}

struct NotificationRule: Codable {
    var connectionID: String
    var metric: String
    var thresholds: [Int]
    var enabled: Bool
    enum CodingKeys: String, CodingKey { case connectionID = "connection_id"; case metric, thresholds, enabled }
}

struct NotificationPreferences: Codable {
    var enabled = true
    var thresholds = [80, 95, 100]
    var recovery = true
    var recentOnly = false
    var mutedUntil: Double = 0
    var quietHours = NotificationHours()
    var workHours = NotificationHours()
    var rules: [NotificationRule] = []
    enum CodingKeys: String, CodingKey {
        case enabled, thresholds, recovery, rules
        case recentOnly = "recent_only", mutedUntil = "muted_until"
        case quietHours = "quiet_hours", workHours = "work_hours"
    }
    init() {}
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        enabled = try values.decodeIfPresent(Bool.self, forKey: .enabled) ?? true
        thresholds = try values.decodeIfPresent([Int].self, forKey: .thresholds) ?? [80, 95, 100]
        recovery = try values.decodeIfPresent(Bool.self, forKey: .recovery) ?? true
        recentOnly = try values.decodeIfPresent(Bool.self, forKey: .recentOnly) ?? false
        mutedUntil = try values.decodeIfPresent(Double.self, forKey: .mutedUntil) ?? 0
        quietHours = try values.decodeIfPresent(NotificationHours.self, forKey: .quietHours) ?? NotificationHours()
        workHours = try values.decodeIfPresent(NotificationHours.self, forKey: .workHours) ?? NotificationHours()
        rules = try values.decodeIfPresent([NotificationRule].self, forKey: .rules) ?? []
    }
    func isSilent(at now: Date = Date()) -> Bool {
        let components = Calendar.current.dateComponents([.hour, .minute], from: now)
        let current = String(format: "%02d:%02d", components.hour ?? 0, components.minute ?? 0)
        func inHours(_ hours: NotificationHours) -> Bool {
            guard !hours.start.isEmpty else { return false }
            return hours.start < hours.end
                ? hours.start <= current && current < hours.end
                : current >= hours.start || current < hours.end
        }
        return !enabled || now.timeIntervalSince1970 < mutedUntil || inHours(quietHours)
            || (!workHours.start.isEmpty && !inHours(workHours))
    }
}

struct QuotaNotification: Decodable {
    let id: String
    let title: String
    let body: String
    let kind: String
    let provider: String
    let idx: Int
    let metric: String
    let queuedAt: Double
    enum CodingKeys: String, CodingKey { case id, title, body, kind, provider, idx, metric; case queuedAt = "queued_at" }
    var selection: Selection { Selection(provider: provider, idx: idx, metric: metric) }
    var fresh: Bool { (0...300).contains(Date().timeIntervalSince1970 - queuedAt) }
}

struct ProjectInfo: Decodable {
    let name: String
    let version: String
    let commit: String
    let description: String
    let author: String
    let license: String
    let github: String
    let documentation: String
    let issues: String
}

struct VersionInfo: Decodable {
    let current: String
    let latest: String?
    let hasUpdate: Bool
    enum CodingKeys: String, CodingKey { case current, latest; case hasUpdate = "has_update" }
}

struct UpdateGuide: Decodable {
    let method: String
    let title: String
    let description: String
    let steps: [String]
    let command: String
    let actionLabel: String
    let canUpdate: Bool
    let releaseUrl: String
    let guideUrl: String

    // Older snapshots remain useful even before the shared core is updated.
    static let manualMacOS = UpdateGuide(
        method: "manual", title: "Update AI Status on macOS",
        description: "Re-run the macOS installer to install the latest stable version. Your settings and provider connections are preserved.",
        steps: ["Copy the command below and run it in Terminal.",
                "Follow the installation progress in Terminal. AI Status restarts after installation."],
        command: "curl -fsSL https://ai-status.gelzin.com/install/macos | bash",
        actionLabel: "", canUpdate: false,
        releaseUrl: "https://github.com/gelzinn/ai-status/releases/latest",
        guideUrl: "https://ai-status.gelzin.com/macos")
}

struct Snapshot: Decodable {
    let schemaVersion: Int
    let text: String
    let selected: Selection
    let iconMode: String
    let logoPath: String
    let loading: Bool
    let providers: [Provider]
    let settings: Settings
    let about: ProjectInfo
    let version: VersionInfo
    let update: UpdateGuide?
    let notifications: [QuotaNotification]?
}

enum Page: Equatable {
    case usage, settings, update, credits(String), cloudCredits(String, String)
}

enum SettingsSection: String, CaseIterable, Identifiable {
    case general, appearance, alerts, providers, guide, about
    var id: String { rawValue }
    var title: String { rawValue.capitalized }
    var icon: String {
        switch self {
        case .general: return "settings"
        case .appearance: return "paintbrush"
        case .alerts: return "bell"
        case .providers: return "server"
        case .guide: return "book-open"
        case .about: return "info"
        }
    }
    var detail: String {
        switch self {
        case .general: return "Choose the account and limit shown in your menu bar."
        case .appearance: return "Customize the menu bar icon and usage text."
        case .alerts: return "Set quota notifications and account-specific rules."
        case .providers: return "Enable providers and arrange their order in Usage."
        case .guide: return "macOS actions and keyboard shortcuts."
        case .about: return "Version and project links."
        }
    }
}

enum AboutLink: String, CaseIterable, Identifiable {
    case guide, issues, documentation, github
    var id: String { rawValue }
    var title: String {
        switch self {
        case .guide: return "Guide"
        case .issues: return "Report a bug"
        case .documentation: return "Documentation"
        case .github: return "GitHub"
        }
    }
    func url(_ info: ProjectInfo) -> URL? {
        let value: String
        switch self {
        case .guide: return nil
        case .issues: value = info.issues
        case .documentation: value = info.documentation
        case .github: value = info.github
        }
        guard let url = URL(string: value), url.scheme == "https" else { return nil }
        return url
    }
}

struct Choice: Identifiable {
    let selection: Selection
    let label: String
    let provider: String
    let logoPath: String
    var id: Selection { selection }
}

struct SettingsDraft {
    var order: [String] = []
    var enabled: Set<String> = []
    var display: [String: Bool] = [:]
    var iconMode = "bot"
    var usageDisplay = "used"
    var selected = Selection()
    var notifications = NotificationPreferences()
    var notificationThresholds = "80, 95, 100"
    var notificationRuleThresholds: [String: String] = [:]
    var saved = false
}

enum Assets {
    static let font = Font.custom("GeistMono-Regular", size: 13)
    static let cache = NSCache<NSString, NSImage>()
    static let panelIcons: PanelIcons = {
        do { return try PanelIcons.load() }
        catch { preconditionFailure("Bundled panel icons are unavailable: \(error)") }
    }()
    static func url(_ path: String) -> URL? {
        Bundle.main.resourceURL?.appendingPathComponent("assets").appendingPathComponent(path)
    }
    static func registerFonts() {
        for file in ["GeistMono-Regular.ttf", "GeistMono-Medium.ttf"] {
            if let url = url("fonts/" + file) {
                CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
            }
        }
    }
    static func image(provider: String = "", path: String = "") -> NSImage? {
        let candidates = [path, url("providers/\(provider).png")?.path ?? "", url("app.png")?.path ?? ""]
        for candidate in candidates where !candidate.isEmpty {
            if let cached = cache.object(forKey: candidate as NSString) { return cached }
            if let image = NSImage(contentsOfFile: candidate) {
                cache.setObject(image, forKey: candidate as NSString)
                return image
            }
        }
        return nil
    }
}

struct PanelIcons: Decodable {
    struct Controls: Decodable {
        let size: CGFloat
        let radius: CGFloat
        let hoverOpacity: Double
        let focusOpacity: Double
    }

    enum Command: Decodable {
        case move(CGPoint), line(CGPoint), curve(CGPoint, CGPoint, CGPoint), close

        init(from decoder: Decoder) throws {
            var values = try decoder.unkeyedContainer()
            let operation = try values.decode(String.self)
            func point() throws -> CGPoint {
                let x = try values.decode(CGFloat.self)
                let y = try values.decode(CGFloat.self)
                guard x.isFinite, y.isFinite else { throw AppError.message("Panel icon coordinates must be finite.") }
                return CGPoint(x: x, y: y)
            }
            switch operation {
            case "M": self = .move(try point())
            case "L": self = .line(try point())
            case "C":
                let first = try point(), second = try point(), end = try point()
                self = .curve(first, second, end)
            case "Z": self = .close
            default: throw AppError.message("Unsupported panel icon command: \(operation)")
            }
            guard values.isAtEnd else { throw AppError.message("Unexpected panel icon command coordinates.") }
        }
    }

    let viewBox: CGFloat
    let size: CGFloat
    let strokeWidth: CGFloat
    let controls: Controls
    let paths: [String: [Command]]

    static func load() throws -> PanelIcons {
        guard let url = Assets.url("panel-icons.json") else { throw AppError.message("Bundled panel icons are missing.") }
        let icons = try JSONDecoder().decode(PanelIcons.self, from: Data(contentsOf: url))
        guard icons.viewBox.isFinite, icons.viewBox > 0, icons.size.isFinite, icons.size > 0,
              icons.strokeWidth.isFinite, icons.strokeWidth > 0,
              icons.controls.size.isFinite, icons.controls.size >= icons.size,
              icons.controls.radius.isFinite, icons.controls.radius >= 0,
              (0...1).contains(icons.controls.hoverOpacity), (0...1).contains(icons.controls.focusOpacity),
              ["refresh-cw", "settings", "paintbrush", "bell", "server", "book-open", "info",
               "arrow-left", "arrow-right", "arrow-up", "arrow-down", "chevron-down", "copy", "check"]
                .allSatisfy({ icons.paths[$0]?.isEmpty == false }) else {
            throw AppError.message("Bundled panel icon geometry or controls are invalid.")
        }
        return icons
    }
}

final class Model: ObservableObject {
    @Published var snapshot: Snapshot?
    @Published var page: Page = .usage {
        didSet { if page != oldValue { keyboardFocusVisible = false } }
    }
    @Published var draft = SettingsDraft()
    @Published var settingsSection: SettingsSection = .general
    @Published var notificationAdvancedExpanded = false
    @Published var notificationEditingSelection: Selection?
    @Published var notificationRuleFocusRequest = 0
    @Published var error = ""
    @Published var settingsError = ""
    @Published var settingsSaving = false
    @Published var updateStarting = false
    @Published var updateError = ""
    @Published var updateMessage = ""
    @Published var isPresented = false
    @Published var keyboardFocusVisible = false
    @Published var notificationPermission = ""
    var changed: (() -> Void)?
    private let runtime: RuntimeConfig?
    private var backend: Process?
    private var actionProcess: Process?
    private var actions: [([String], ((String) -> Void)?, (String?) -> Void)] = []
    private var reconnect: DispatchWorkItem?
    private var retryDelay = 1.0
    private var stopping = false

    init(runtime: RuntimeConfig? = nil) { self.runtime = runtime }

    func observeFocusInput(_ event: NSEvent) {
        guard isPresented else { return }
        switch event.type {
        case .keyDown:
            if event.keyCode == 48 && event.modifierFlags.intersection([.command, .control, .option]).isEmpty {
                keyboardFocusVisible = true
            }
        case .leftMouseDown, .rightMouseDown, .otherMouseDown:
            keyboardFocusVisible = false
        default: break
        }
    }

    var choices: [Choice] {
        guard let snapshot = snapshot else { return [] }
        return draft.order.filter { draft.enabled.contains($0) }.flatMap { name -> [Choice] in
            let providers = snapshot.providers.filter { $0.connectionID == name }
            if providers.isEmpty {
                return [Choice(selection: Selection(provider: name, metric: "rolling"),
                               label: providerName(name), provider: logoProviderID(name), logoPath: "")]
            }
            return providers.flatMap { provider in
                provider.metrics.map { metric in
                    let parts = metric.key.split(separator: ":", maxSplits: 1)
                    let periodName = ["rolling": "Rolling Usage", "daily": "Daily Usage", "weekly": "Weekly Usage", "monthly": "Monthly Usage"][String(parts.first ?? "")]
                    let remainingName = periodName?.replacingOccurrences(of: "Usage", with: "Remaining")
                    let suffix = parts.count == 2 && (periodName == metric.name || remainingName == metric.name) && String(parts[1]) != metric.name ? " (\(parts[1]))" : ""
                    return Choice(selection: provider.selection(metric), label: provider.name + " · " + metric.name + suffix,
                                  provider: provider.providerID, logoPath: provider.logoPath)
                }
            }
        }
    }

    var settingsValid: Bool { settingsValidation == nil }
    var settingsValidation: (section: SettingsSection, message: String)? {
        if draft.enabled.isEmpty { return (.providers, "Enable at least one provider.") }
        if !choices.contains(where: { $0.selection == draft.selected }) {
            return (.general, "Choose an active provider and limit.")
        }
        if !draft.display.values.contains(true) { return (.appearance, "Choose at least one bar text field.") }
        if !["used", "remaining"].contains(draft.usageDisplay) { return (.appearance, "Choose a usage display mode.") }
        if Self.parseThresholds(draft.notificationThresholds) == nil ||
            !draft.notificationRuleThresholds.values.allSatisfy({ Self.parseThresholds($0) != nil }) {
            return (.alerts, "Alert thresholds must be whole percentages from 1 to 100, separated by commas.")
        }
        return nil
    }
    var settingsSelectionLabel: String {
        choices.first { $0.selection == draft.selected }?.label ?? "Choose a provider and limit in General."
    }
    var invalidAdvancedNotifications: Bool {
        draft.notificationRuleThresholds.values.contains { Self.parseThresholds($0) == nil }
    }
    var invalidNotificationRules: [NotificationRule] {
        draft.notifications.rules.filter { rule in
            let key = rule.connectionID + "\u{001f}" + rule.metric
            return Self.parseThresholds(draft.notificationRuleThresholds[key] ?? rule.thresholds.map(String.init).joined(separator: ", ")) == nil
        }
    }
    var notificationSelection: Selection { notificationEditingSelection ?? draft.selected }
    func notificationRuleLabel(_ rule: NotificationRule) -> String {
        if let choice = choices.first(where: { $0.selection.provider == rule.connectionID && $0.selection.metric == rule.metric }) {
            return choice.label
        }
        let provider = snapshot?.providers.first { $0.connectionID == rule.connectionID }
        let metric = provider?.metrics.first { $0.key == rule.metric }
        return (provider?.name ?? providerName(rule.connectionID)) + " · " + (metric?.name ?? rule.metric)
    }
    var notificationEditingLabel: String {
        let selection = notificationSelection
        if let choice = choices.first(where: { $0.selection == selection }) { return choice.label }
        return notificationRuleLabel(NotificationRule(connectionID: selection.provider, metric: selection.metric, thresholds: [], enabled: true))
    }
    func reviewNotificationRule(_ rule: NotificationRule) {
        guard page == .settings, !settingsSaving else { return }
        notificationEditingSelection = choices.first { $0.selection.provider == rule.connectionID && $0.selection.metric == rule.metric }?.selection
            ?? Selection(provider: rule.connectionID, metric: rule.metric)
        notificationAdvancedExpanded = true
        showSettingsSection(.alerts)
        keyboardFocusVisible = true
        notificationRuleFocusRequest += 1
    }
    var notificationLevels: [Int] {
        guard Self.parseThresholds(draft.notificationThresholds) != nil else { return [] }
        return draft.notificationThresholds.split(separator: ",").compactMap { Int($0.trimmingCharacters(in: .whitespaces)) }
    }
    func setNotificationLevel(_ index: Int, _ value: Int) {
        var levels = notificationLevels
        guard !settingsSaving, levels.indices.contains(index), (1...100).contains(value) else { return }
        levels[index] = value
        draft.notificationThresholds = levels.map(String.init).joined(separator: ", ")
        draft.saved = false
    }
    func addNotificationLevel() {
        guard !settingsSaving, Self.parseThresholds(draft.notificationThresholds) != nil else { return }
        let levels = notificationLevels
        guard let value = ([80, 95, 100] + Array(1...100)).first(where: { !levels.contains($0) }) else { return }
        draft.notificationThresholds = (levels + [value]).map(String.init).joined(separator: ", ")
        draft.saved = false
    }
    func removeNotificationLevel(_ index: Int) {
        var levels = notificationLevels
        guard !settingsSaving, levels.indices.contains(index) else { return }
        levels.remove(at: index)
        draft.notificationThresholds = levels.map(String.init).joined(separator: ", ")
        draft.saved = false
    }
    static func parseThresholds(_ text: String) -> [Int]? {
        if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return [] }
        let parts = text.split(separator: ",", omittingEmptySubsequences: false)
        let parsed = parts.compactMap { Int($0.trimmingCharacters(in: .whitespaces)) }
        guard parsed.count == parts.count, parsed.allSatisfy({ (1...100).contains($0) }) else { return nil }
        return Array(Set(parsed)).sorted()
    }
    var notificationRuleKey: String { notificationSelection.provider + "\u{001f}" + notificationSelection.metric }
    var notificationRule: NotificationRule? {
        draft.notifications.rules.first { $0.connectionID == notificationSelection.provider && $0.metric == notificationSelection.metric }
    }
    func setNotificationOverride(_ enabled: Bool) {
        if enabled && notificationRule == nil {
            let thresholds = Self.parseThresholds(draft.notificationThresholds) ?? [80, 95, 100]
            draft.notifications.rules.append(NotificationRule(connectionID: notificationSelection.provider,
                                                               metric: notificationSelection.metric,
                                                               thresholds: thresholds, enabled: true))
            draft.notificationRuleThresholds[notificationRuleKey] = thresholds.map(String.init).joined(separator: ", ")
        } else if !enabled {
            draft.notifications.rules.removeAll { $0.connectionID == notificationSelection.provider && $0.metric == notificationSelection.metric }
            draft.notificationRuleThresholds.removeValue(forKey: notificationRuleKey)
        }
        draft.saved = false
    }
    func setNotificationRuleEnabled(_ enabled: Bool) {
        if let index = draft.notifications.rules.firstIndex(where: {
            $0.connectionID == notificationSelection.provider && $0.metric == notificationSelection.metric
        }) { draft.notifications.rules[index].enabled = enabled }
        draft.saved = false
    }
    func muteNotifications(_ seconds: Double) {
        draft.notifications.mutedUntil = seconds > 0 ? Date().timeIntervalSince1970 + seconds : 0
        draft.saved = false
    }
    func acknowledgeNotification(_ identity: String) {
        enqueue(["notification-ack", "--id", identity]) { _ in }
    }
    func providerName(_ name: String) -> String { snapshot?.settings.names[name] ?? name }
    func logoProviderID(_ connection: String) -> String {
        snapshot?.settings.providerIds?[connection]
            ?? snapshot?.providers.first { $0.connectionID == connection }?.providerID ?? connection
    }
    var selectedProvider: Provider? {
        snapshot?.providers.first { $0.connectionID == snapshot?.selected.provider && $0.idx == snapshot?.selected.idx }
    }
    var creditProvider: Provider? {
        guard case .credits(let id) = page else { return nil }
        return snapshot?.providers.first { $0.id == id }
    }
    var cloudCreditProvider: Provider? {
        guard case .cloudCredits(let id, _) = page else { return nil }
        return snapshot?.providers.first { $0.id == id }
    }
    var cloudCredit: MonetaryCredit? {
        guard case .cloudCredits(_, let id) = page else { return nil }
        return cloudCreditProvider?.monetaryCredits.first { $0.id == id }
    }
    var updateGuide: UpdateGuide { snapshot?.update ?? .manualMacOS }
    var panelHeight: CGFloat {
        switch page {
        case .settings: return 680
        case .update: return 600
        case .credits: return min(680, CGFloat(310 + (creditProvider?.resetCredits?.rows.count ?? 0) * 82))
        case .cloudCredits: return 660
        case .usage:
            guard let providers = snapshot?.providers, !providers.isEmpty else { return 210 }
            let height = providers.reduce(85) { total, provider in
                total + 62 + provider.metrics.reduce(0) { $0 + (provider.monetaryCredit($1) == nil ? 78 : 36) } + (provider.cached ? 18 : 0)
                    + ((provider.resetCredits?.available ?? 0) > 0 ? 36 : 0)
            }
            return min(680, max(180, CGFloat(height)))
        }
    }

    func accept(_ data: Data) {
        // Ignore partial/incompatible output and preserve the last usable snapshot.
        guard let next = try? JSONDecoder().decode(Snapshot.self, from: data), next.schemaVersion == 1,
              next.providers.allSatisfy({ $0.metrics.allSatisfy { $0.usable } }) else { return }
        snapshot = next
        error = ""
        retryDelay = 1
        if case .credits(let id) = page, !next.providers.contains(where: { $0.id == id }) { page = .usage }
        if case .cloudCredits = page, cloudCredit == nil { page = .usage }
        changed?()
    }

    func start() {
        guard !stopping, backend == nil, let runtime = runtime else { return }
        let process = runtime.process(["daemon", "--format", "macos"])
        let output = Pipe()
        process.standardOutput = output
        process.standardError = FileHandle.nullDevice
        process.terminationHandler = { [weak self] finished in
            DispatchQueue.main.async {
                guard let self = self, self.backend === finished else { return }
                self.backend = nil
                self.scheduleReconnect()
            }
        }
        do {
            backend = process
            try process.run()
            DispatchQueue.global(qos: .utility).async { [weak self] in
                var buffer = Data()
                let input = output.fileHandleForReading
                defer { try? input.close() }
                while true {
                    let data = input.availableData
                    if data.isEmpty { break }
                    buffer.append(data)
                    while let end = buffer.firstIndex(of: 10) {
                        let line = Data(buffer[..<end])
                        buffer.removeSubrange(...end)
                        DispatchQueue.main.async { [weak self] in
                            guard let self = self, self.backend === process else { return }
                            self.accept(line)
                        }
                    }
                    // A broken backend cannot grow memory indefinitely with an unterminated line.
                    if buffer.count > 4 * 1024 * 1024 { buffer.removeAll() }
                }
            }
        } catch {
            backend = nil
            scheduleReconnect()
        }
    }

    private func scheduleReconnect() {
        guard !stopping else { return }
        error = "AI Status is reconnecting. Check the Python installation if this persists."
        let item = DispatchWorkItem { [weak self] in self?.start() }
        reconnect?.cancel()
        reconnect = item
        DispatchQueue.main.asyncAfter(deadline: .now() + retryDelay, execute: item)
        retryDelay = min(30, retryDelay * 2)
        changed?()
    }

    func refresh() {
        guard snapshot?.loading != true else { return }
        enqueue(["refresh", "--frontend", "macos"]) { [weak self] error in
            if let error = error { self?.error = error }
        }
    }
    func select(_ selection: Selection) {
        guard let data = try? JSONEncoder().encode(selection), let json = String(data: data, encoding: .utf8) else { return }
        enqueue(["select-metric", "--frontend", "macos", "--selection-json", json]) { [weak self] error in
            if let error = error { self?.error = error }
        }
    }
    func showSettings() {
        guard !settingsSaving, let snapshot = snapshot else { return }
        draft = SettingsDraft(order: snapshot.settings.order, enabled: Set(snapshot.settings.enabled),
                              display: snapshot.settings.display, iconMode: snapshot.settings.iconMode,
                              usageDisplay: snapshot.settings.usageDisplay == "remaining" ? "remaining" : "used",
                              selected: snapshot.selected)
        draft.notifications = snapshot.settings.notifications ?? NotificationPreferences()
        draft.notificationThresholds = draft.notifications.thresholds.map(String.init).joined(separator: ", ")
        draft.notificationRuleThresholds = Dictionary(uniqueKeysWithValues: draft.notifications.rules.map {
            ($0.connectionID + "\u{001f}" + $0.metric, $0.thresholds.map(String.init).joined(separator: ", "))
        })
        settingsError = ""
        settingsSection = .general
        notificationAdvancedExpanded = false
        notificationEditingSelection = nil
        notificationRuleFocusRequest = 0
        page = .settings
        changed?()
    }
    func showSettingsSection(_ section: SettingsSection) {
        guard page == .settings, !settingsSaving else { return }
        if section == .alerts && invalidAdvancedNotifications { notificationAdvancedExpanded = true }
        settingsSection = section
    }
    func toggleProvider(_ provider: String) {
        if draft.enabled.contains(provider) { draft.enabled.remove(provider) } else { draft.enabled.insert(provider) }
        if !choices.contains(where: { $0.selection == draft.selected }) { draft.selected = choices.first?.selection ?? Selection() }
        draft.saved = false
    }
    func moveProvider(_ provider: String, _ direction: Int) {
        guard let index = draft.order.firstIndex(of: provider), draft.order.indices.contains(index + direction) else { return }
        draft.order.swapAt(index, index + direction)
        draft.saved = false
    }
    func saveSettings() {
        guard settingsValid, !settingsSaving else { return }
        let selection = ["provider": draft.selected.provider, "idx": draft.selected.idx, "metric": draft.selected.metric] as [String: Any]
        var alerts = draft.notifications
        alerts.thresholds = Self.parseThresholds(draft.notificationThresholds) ?? []
        for index in alerts.rules.indices {
            let rule = alerts.rules[index]
            let key = rule.connectionID + "\u{001f}" + rule.metric
            if let text = draft.notificationRuleThresholds[key], let values = Self.parseThresholds(text) {
                alerts.rules[index].thresholds = values
            }
        }
        guard let alertsData = try? JSONEncoder().encode(alerts),
              let alertsObject = try? JSONSerialization.jsonObject(with: alertsData) else { return }
        let payload: [String: Any] = ["enabled": draft.order.filter { draft.enabled.contains($0) },
                                     "display": draft.display, "iconMode": draft.iconMode,
                                     "usageDisplay": draft.usageDisplay, "selected": selection,
                                     "notifications": alertsObject]
        guard let data = try? JSONSerialization.data(withJSONObject: payload), let json = String(data: data, encoding: .utf8) else { return }
        settingsSaving = true
        settingsError = ""
        draft.saved = false
        enqueue(["save-settings", "--frontend", "macos", "--settings-json", json]) { [weak self] error in
            guard let self = self else { return }
            self.settingsSaving = false
            self.settingsError = error ?? ""
            self.draft.saved = error == nil
            if let error = error, error.contains("quiet_hours") || error.contains("work_hours") {
                self.notificationAdvancedExpanded = true
                self.showSettingsSection(.alerts)
            }
        }
    }
    func showCredits(_ provider: Provider) {
        guard (provider.resetCredits?.available ?? 0) > 0 else { return }
        page = .credits(provider.id)
        changed?()
    }
    func showCloudCredits(_ provider: Provider, _ credit: MonetaryCredit) {
        guard snapshot?.providers.contains(where: {
            $0.id == provider.id && $0.monetaryCredits.contains(where: { $0.id == credit.id })
        }) == true else { return }
        page = .cloudCredits(provider.id, credit.id)
        changed?()
    }
    func showAbout() {
        guard !settingsSaving else { return }
        if page != .settings { showSettings() }
        showSettingsSection(.about)
    }
    func openAboutLink(_ link: AboutLink) {
        guard page == .settings, !settingsSaving else { return }
        if link == .guide {
            showSettingsSection(.guide)
        } else if let info = snapshot?.about, let url = link.url(info) {
            NSWorkspace.shared.open(url)
        }
    }
    func showUpdate() {
        updateError = ""
        updateMessage = ""
        page = .update
        changed?()
    }
    func startUpdate() {
        guard updateGuide.canUpdate, !updateStarting else { return }
        updateStarting = true
        updateError = ""
        updateMessage = ""
        enqueue(["update"], output: { [weak self] message in
            self?.updateMessage = message
        }) { [weak self] error in
            guard let self = self else { return }
            self.updateStarting = false
            self.updateError = error ?? ""
        }
    }
    func back() {
        guard !settingsSaving else { return }
        page = .usage
        changed?()
    }

    private func enqueue(_ arguments: [String], output: ((String) -> Void)? = nil,
                         completion: @escaping (String?) -> Void) {
        guard !stopping, runtime != nil else { completion("The AI Status runtime is unavailable."); return }
        actions.append((arguments, output, completion))
        drain()
    }
    private func drain() {
        guard !stopping, actionProcess == nil, !actions.isEmpty, let runtime = runtime else { return }
        let (arguments, output, completion) = actions.removeFirst()
        let process = runtime.process(arguments)
        let errors = Pipe()
        process.standardError = errors
        // Share one pipe for captured results so neither stream blocks the other.
        if output != nil { process.standardOutput = errors }
        else { process.standardOutput = FileHandle.nullDevice }
        do {
            actionProcess = process
            try process.run()
            DispatchQueue.global(qos: .utility).async { [weak self] in
                let data = errors.fileHandleForReading.readDataToEndOfFile()
                try? errors.fileHandleForReading.close()
                process.waitUntilExit()
                let message = String(data: data.prefix(2048), encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
                DispatchQueue.main.async {
                    guard let self = self, self.actionProcess === process, !self.stopping else { return }
                    self.actionProcess = nil
                    if process.terminationStatus == 0 { output?(message ?? "") }
                    completion(process.terminationStatus == 0 ? nil : (message?.isEmpty == false ? message : "Could not apply this change. Try again."))
                    self.drain()
                }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 15) { [weak self] in
                guard let self = self, self.actionProcess === process, process.isRunning else { return }
                Self.stopProcess(process)
            }
        } catch {
            actionProcess = nil
            completion("Could not start Python. Run the macOS installer again.")
            drain()
        }
    }

    private static func stopProcess(_ process: Process) {
        guard process.isRunning else { return }
        process.terminationHandler = nil
        let pid = process.processIdentifier
        let target = getpgid(pid) == pid ? -pid : pid
        kill(target, SIGTERM)
        for _ in 0..<20 {
            if !process.isRunning { break }
            usleep(10_000)
        }
        if process.isRunning { kill(target, SIGKILL) }
    }
    func shutdown() {
        stopping = true
        reconnect?.cancel()
        actions.removeAll()
        if let process = backend { Self.stopProcess(process) }
        if let process = actionProcess { Self.stopProcess(process) }
        backend = nil
        actionProcess = nil
    }
}

private enum Palette {
    static let surface = Color(red: 17 / 255, green: 17 / 255, blue: 17 / 255)
    static let border = Color.white.opacity(0.10)
    static let bright = Color(red: 238 / 255, green: 238 / 255, blue: 238 / 255)
    static let dim = Color(red: 136 / 255, green: 136 / 255, blue: 136 / 255)
    static let update = Color(red: 137 / 255, green: 180 / 255, blue: 250 / 255)
    static let control = Color(red: 170 / 255, green: 170 / 255, blue: 170 / 255)
}

struct ProviderLogo: View {
    let provider: String
    var path = ""
    var body: some View {
        Group {
            if let image = Assets.image(provider: provider, path: path) {
                Image(nsImage: image).resizable().scaledToFit()
            } else { Image(systemName: "sparkles") }
        }.frame(width: 16, height: 16).accessibilityHidden(true)
    }
}

struct PanelFocusPosition: Equatable {
    let id: String
    let frame: CGRect
}

struct PanelFocusPreference: PreferenceKey {
    static var defaultValue: [PanelFocusPosition] = []
    static func reduce(value: inout [PanelFocusPosition], nextValue: () -> [PanelFocusPosition]) { value += nextValue() }
}

struct PanelFocusGeometry: View {
    let id: String
    let focused: Bool
    @Environment(\.panelScrollFocusTracking) private var tracking
    var body: some View {
        if tracking {
            GeometryReader { geometry in
                Color.clear.preference(key: PanelFocusPreference.self,
                                       value: focused ? [PanelFocusPosition(id: id, frame: geometry.frame(in: .named("panel-scroll")))] : [])
            }
        } else { Color.clear }
    }
}

struct PanelFocusTarget: ViewModifier {
    @State private var id = UUID().uuidString
    @FocusState private var focused: Bool
    func body(content: Content) -> some View {
        content.id(id).focused($focused).background(PanelFocusGeometry(id: id, focused: focused))
    }
}

struct HoverButton<Label: View>: View {
    var bordered = false
    var padding: CGFloat = 6
    var hoverColor = Color.white.opacity(0.045)
    let action: () -> Void
    @ViewBuilder let label: () -> Label
    @State private var hovering = false
    @Environment(\.isEnabled) private var enabled
    var body: some View {
        Button(action: action) {
            label().frame(maxWidth: .infinity, alignment: .leading).padding(padding).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .modifier(PanelFocusTarget())
        .background(RoundedRectangle(cornerRadius: 6).fill(hovering && enabled ? hoverColor : .clear))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(bordered ? Palette.border : .clear))
        .opacity(enabled ? 1 : 0.4)
        .onHover { hovering = $0 }
    }
}

struct PanelIconShape: Shape {
    let commands: [PanelIcons.Command]
    let viewBox: CGFloat

    func path(in rect: CGRect) -> Path {
        func scaled(_ point: CGPoint) -> CGPoint {
            CGPoint(x: rect.minX + point.x * rect.width / viewBox,
                    y: rect.minY + point.y * rect.height / viewBox)
        }
        var path = Path()
        for command in commands {
            switch command {
            case .move(let point): path.move(to: scaled(point))
            case .line(let point): path.addLine(to: scaled(point))
            case .curve(let first, let second, let end):
                path.addCurve(to: scaled(end), control1: scaled(first), control2: scaled(second))
            case .close: path.closeSubpath()
            }
        }
        return path
    }
}

struct PanelIcon: View {
    let name: String
    private let icons = Assets.panelIcons
    var body: some View {
        PanelIconShape(commands: icons.paths[name] ?? [], viewBox: icons.viewBox)
            .stroke(style: StrokeStyle(lineWidth: icons.strokeWidth * icons.size / icons.viewBox,
                                       lineCap: .round, lineJoin: .round))
            .frame(width: icons.size, height: icons.size)
            .accessibilityHidden(true)
    }
}

private struct ControlKeyboardFocusVisibleKey: EnvironmentKey {
    static let defaultValue = false
}

private struct PanelScrollFocusTrackingKey: EnvironmentKey {
    static let defaultValue = false
}

private extension EnvironmentValues {
    var panelScrollFocusTracking: Bool {
        get { self[PanelScrollFocusTrackingKey.self] }
        set { self[PanelScrollFocusTrackingKey.self] = newValue }
    }
    var controlKeyboardFocusVisible: Bool {
        get { self[ControlKeyboardFocusVisibleKey.self] }
        set { self[ControlKeyboardFocusVisibleKey.self] = newValue }
    }
}

struct ControlButton: View {
    let icon: String
    let help: String
    var spinning = false
    let action: () -> Void
    @State private var hovering = false
    @State private var focusID = UUID().uuidString
    @FocusState private var focused: Bool
    @Environment(\.controlKeyboardFocusVisible) private var keyboardFocusVisible
    @Environment(\.isEnabled) private var enabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private let controls = Assets.panelIcons.controls
    var body: some View {
        Button(action: action) {
            PanelIcon(name: icon).rotationEffect(.degrees(spinning && !reduceMotion ? 360 : 0))
                .animation(spinning && !reduceMotion ? .linear(duration: 1).repeatForever(autoreverses: false) : nil, value: spinning)
                .frame(width: controls.size, height: controls.size).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .id(focusID)
        .focused($focused)
        .background(PanelFocusGeometry(id: focusID, focused: focused))
        .foregroundColor(focused && keyboardFocusVisible && enabled ? Palette.bright : Palette.control)
        .background(RoundedRectangle(cornerRadius: controls.radius)
            .fill(hovering && enabled ? Color.white.opacity(controls.hoverOpacity) : .clear))
        .overlay(RoundedRectangle(cornerRadius: controls.radius)
            .stroke(focused && keyboardFocusVisible && enabled ? Color.white.opacity(controls.focusOpacity) : .clear, lineWidth: 1))
        .opacity(enabled ? 1 : 0.4)
        .onHover { hovering = $0 }
        .help(help).accessibilityLabel(help)
    }
}

struct UsageBar: View {
    let percentage: Double
    let selected: Bool
    let loading: Bool
    let index: Int
    @State private var displayed = 0.0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var body: some View {
        TimelineView(.animation(minimumInterval: 0.04, paused: !loading || reduceMotion)) { context in
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle().fill(Color.white.opacity(0.015))
                    if loading {
                        let phase = context.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 1.5) / 1.5
                        LinearGradient(colors: [.clear, Color.white.opacity(0.15), .clear], startPoint: .leading, endPoint: .trailing)
                            .offset(x: reduceMotion ? 0 : geometry.size.width * (phase * 2 - 1))
                    } else {
                        Rectangle().fill(selected ? Palette.bright : Color.white.opacity(0.3))
                            .frame(width: geometry.size.width * min(100, max(0, displayed)) / 100)
                    }
                }.clipped().overlay(Rectangle().stroke(Palette.border, lineWidth: 1))
            }
        }
        .frame(height: 15)
        .onAppear { displayed = percentage }
        .onChange(of: percentage) { displayed = $0 }
        .animation(reduceMotion || loading ? nil : .timingCurve(0.16, 1, 0.3, 1, duration: 1.5).delay(0.1 + Double(index) * 0.15), value: displayed)
        .accessibilityHidden(true)
    }
}

struct UsagePage: View {
    @ObservedObject var model: Model
    var body: some View {
        VStack(alignment: .leading, spacing: 26) {
            if model.snapshot?.providers.isEmpty != false {
                Text(model.snapshot?.loading != false ? "Checking your connected providers…" :
                     model.snapshot?.settings.enabled.isEmpty == true ? "No providers enabled. Choose them in Settings." :
                     "No usage available. Connect a provider and refresh.")
                HoverButton(action: model.showSettings) { Text("Settings") }
            }
            ForEach(Array((model.snapshot?.providers ?? []).enumerated()), id: \.element.id) { groupIndex, provider in
                let selected = provider.connectionID == model.snapshot?.selected.provider && provider.idx == model.snapshot?.selected.idx
                VStack(alignment: .leading, spacing: 16) {
                    HoverButton(action: { if let metric = provider.metrics.first { model.select(provider.selection(metric)) } }) {
                        HStack(spacing: 8) {
                            Text(selected ? "→" : " ").frame(width: 14)
                            ProviderLogo(provider: provider.providerID, path: provider.logoPath)
                            Text(provider.name).fontWeight(selected ? .medium : .regular)
                        }.foregroundColor(selected ? Palette.bright : Palette.dim)
                    }.accessibilityLabel(provider.name)
                    if provider.cached {
                        Text("Cached data").font(.custom("GeistMono-Regular", size: 11)).foregroundColor(Palette.dim)
                            .padding(.leading, 24).help(provider.error)
                    }
                    ForEach(provider.metrics) { metric in
                        if let credit = provider.monetaryCredit(metric) {
                            HoverButton(action: { model.showCloudCredits(provider, credit) }) {
                                HStack {
                                    Text(credit.title + ": " + credit.value)
                                    Spacer()
                                    PanelIcon(name: "arrow-right")
                                }
                            }.padding(.leading, 18)
                                .accessibilityLabel("\(provider.name), \(credit.title), \(credit.value), show details")
                        } else {
                            let active = selected && metric.key == model.snapshot?.selected.metric
                            HoverButton(padding: 4, action: { model.select(provider.selection(metric)) }) {
                                HStack(alignment: .top, spacing: 8) {
                                    Text(active ? "•" : " ").frame(width: 16)
                                    VStack(alignment: .leading, spacing: 4) {
                                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                                            Text(metric.name + (metric.isAmount ? ":" : ""))
                                            if !metric.isAmount { Spacer(minLength: 0) }
                                            Text(provider.loading && model.isPresented ? "…" : metric.displayValue)
                                                .fixedSize(horizontal: false, vertical: true)
                                        }
                                        if let percentage = metric.percentage {
                                            HStack(spacing: 5) {
                                                Text("[")
                                                UsageBar(percentage: percentage, selected: active,
                                                         loading: provider.loading && model.isPresented, index: groupIndex)
                                                Text("]")
                                            }
                                        }
                                        if !metric.detail.isEmpty {
                                            Text(metric.detail).font(.custom("GeistMono-Regular", size: 11)).foregroundColor(Palette.dim.opacity(0.7))
                                                .fixedSize(horizontal: false, vertical: true).padding(.leading, 10)
                                        }
                                    }
                                }.foregroundColor(active ? Palette.bright : Palette.dim)
                            }.accessibilityLabel("\(provider.name), \(metric.name), \(metric.displayValue)")
                        }
                    }
                    if let credits = provider.resetCredits, credits.available > 0 {
                        HoverButton(action: { model.showCredits(provider) }) {
                            HStack {
                                Text("Reset credits: \(credits.available) available")
                                Spacer()
                                PanelIcon(name: "arrow-right")
                            }
                        }.padding(.leading, 18)
                    }
                }
            }
        }
    }
}

struct SettingsNavigationButton: View {
    let section: SettingsSection
    let selected: Bool
    let action: () -> Void
    let focusChanged: () -> Void
    @State private var hovering = false
    @FocusState private var focused: Bool
    @Environment(\.controlKeyboardFocusVisible) private var keyboardFocusVisible
    @Environment(\.isEnabled) private var enabled
    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                PanelIcon(name: section.icon)
                Text(section.title).fixedSize(horizontal: true, vertical: false)
            }
                .padding(.horizontal, 16).padding(.vertical, 9).contentShape(Rectangle())
        }.buttonStyle(.plain).focused($focused)
            .foregroundColor(selected || (focused && keyboardFocusVisible) ? Palette.bright : Palette.dim)
            .background(RoundedRectangle(cornerRadius: 6)
                .fill(selected ? Palette.bright.opacity(0.09) : hovering && enabled ? Palette.bright.opacity(0.045) : .clear))
            .overlay(RoundedRectangle(cornerRadius: 6)
                .stroke(focused && keyboardFocusVisible ? Palette.bright.opacity(0.5) : Palette.border))
            .opacity(enabled ? 1 : 0.4)
            .background(RoundedRectangle(cornerRadius: 6).fill(Palette.surface))
            .onHover { hovering = $0 }
            .onChange(of: focused) { if $0 { focusChanged() } }
            .accessibilityLabel(section.title)
            .accessibilityAddTraits(selected ? .isSelected : [])
            .help(section.detail)
    }
}

struct SettingsNavigation: View {
    @ObservedObject var model: Model
    private let tabGap: CGFloat = 12
    static let height: CGFloat = 58
    var body: some View {
        ScrollViewReader { scroll in
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: tabGap) {
                    ForEach(SettingsSection.allCases) { section in
                        SettingsNavigationButton(section: section, selected: model.settingsSection == section,
                                                 action: { model.showSettingsSection(section) },
                                                 focusChanged: { scroll.scrollTo(section.id, anchor: .center) })
                            .id(section.id)
                    }
                }.padding(.horizontal, 16).padding(.vertical, tabGap)
            }.frame(height: Self.height)
                .onAppear { scroll.scrollTo(model.settingsSection.id, anchor: .center) }
                .onChange(of: model.settingsSection) { scroll.scrollTo($0.id, anchor: .center) }
        }.disabled(model.settingsSaving)
    }
}

struct SettingsHeading: View {
    let title: String
    var detail: String? = nil
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).foregroundColor(Palette.bright)
            if let detail = detail {
                Text(detail).font(.custom("GeistMono-Regular", size: 11))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

struct SettingsPage: View {
    @ObservedObject var model: Model
    private let fields = [("show_provider", "Provider name"), ("show_model", "Model / plan"),
                          ("show_metric", "Limit name"), ("show_pct", "Usage value")]
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            if model.settingsSection != .alerts {
                SettingsHeading(title: model.settingsSection.title,
                                detail: model.settingsSection == .general ? nil : model.settingsSection.detail)
            }
            switch model.settingsSection {
            case .general:
                general
            case .appearance:
                appearance
            case .alerts:
                NotificationSettingsView(model: model)
            case .providers:
                providers
            case .guide:
                GuidePage()
            case .about:
                if let info = model.snapshot?.about { AboutPage(info: info, model: model) }
            }
        }.disabled(model.settingsSaving)
    }

    private var general: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                SettingsHeading(title: "Active provider & limit", detail: SettingsSection.general.detail)
                Picker("Active provider & limit", selection: Binding(get: { model.draft.selected }, set: {
                    model.draft.selected = $0; model.draft.saved = false
                })) {
                    if model.choices.isEmpty { Text("Choose a provider and limit").tag(Selection()) }
                    ForEach(model.choices) { choice in
                        Label { Text(choice.label) } icon: { ProviderLogo(provider: choice.provider, path: choice.logoPath) }
                            .tag(choice.selection)
                    }
                }.labelsHidden().pickerStyle(.menu).modifier(PanelFocusTarget()).frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private var appearance: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                SettingsHeading(title: "Usage display")
                Picker("Usage display", selection: Binding(get: { model.draft.usageDisplay }, set: {
                    model.draft.usageDisplay = $0; model.draft.saved = false
                })) {
                    Text("Used").tag("used")
                    Text("Remaining").tag("remaining")
                }.labelsHidden().pickerStyle(.menu).modifier(PanelFocusTarget()).frame(maxWidth: .infinity, alignment: .leading)
            }
            VStack(alignment: .leading, spacing: 8) {
                SettingsHeading(title: "Bar display")
                ForEach(fields, id: \.0) { key, label in
                    Toggle(label, isOn: Binding(get: { model.draft.display[key] ?? false }, set: {
                        model.draft.display[key] = $0; model.draft.saved = false
                    })).toggleStyle(.checkbox).modifier(PanelFocusTarget())
                }
                Picker("Icon", selection: Binding(get: { model.draft.iconMode }, set: {
                    model.draft.iconMode = $0; model.draft.saved = false
                })) {
                    Text("None").tag("off")
                    Text("Bot").tag("bot")
                    Text("Provider logo").tag("logo")
                }.pickerStyle(.menu).modifier(PanelFocusTarget()).frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private var providers: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(model.draft.order, id: \.self) { provider in
                HStack(spacing: 4) {
                    Toggle(isOn: Binding(get: { model.draft.enabled.contains(provider) }, set: { _ in model.toggleProvider(provider) })) {
                        HStack(spacing: 6) {
                            ProviderLogo(provider: model.logoProviderID(provider))
                            Text(model.providerName(provider))
                        }
                    }.toggleStyle(.checkbox).modifier(PanelFocusTarget())
                    Spacer(minLength: 0)
                    ControlButton(icon: "arrow-up", help: "Move \(model.providerName(provider)) up",
                                  action: { model.moveProvider(provider, -1) }).disabled(model.draft.order.first == provider)
                    ControlButton(icon: "arrow-down", help: "Move \(model.providerName(provider)) down",
                                  action: { model.moveProvider(provider, 1) }).disabled(model.draft.order.last == provider)
                }.padding(.vertical, 3)
            }
        }
    }
}

struct NotificationLevelsView: View {
    @ObservedObject var model: Model
    @FocusState private var addLevelFocused: Bool
    @State private var addLevelFocusID = UUID().uuidString
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            SettingsHeading(title: "Alert levels", detail: "Notify when quota consumed reaches each percentage.")
            ForEach(Array(model.notificationLevels.enumerated()), id: \.offset) { index, value in
                HStack(spacing: 8) {
                    Text("\(value)%").frame(width: 42, alignment: .trailing).foregroundColor(Palette.bright)
                    Slider(value: Binding(get: {
                        Double(model.notificationLevels.indices.contains(index) ? model.notificationLevels[index] : value)
                    }, set: { model.setNotificationLevel(index, Int($0.rounded())) }), in: 1...100, step: 1) {
                        Text("Alert level \(index + 1)")
                    }.labelsHidden().modifier(PanelFocusTarget()).accessibilityValue("\(value)%")
                    Button("Remove") {
                        model.removeNotificationLevel(index)
                        DispatchQueue.main.async { addLevelFocused = true }
                    }.buttonStyle(.borderless).modifier(PanelFocusTarget())
                        .font(.custom("GeistMono-Regular", size: 11))
                        .accessibilityLabel("Remove \(value)% alert level")
                }
            }
            if Model.parseThresholds(model.draft.notificationThresholds) == nil {
                Text("Correct the saved alert levels before using the sliders.")
                    .font(.custom("GeistMono-Regular", size: 11)).foregroundColor(.orange)
                TextField("80, 95, 100", text: Binding(get: { model.draft.notificationThresholds }, set: {
                    model.draft.notificationThresholds = $0; model.draft.saved = false
                })).textFieldStyle(.roundedBorder).modifier(PanelFocusTarget()).accessibilityLabel("Correct alert levels")
            }
            Button("Add level", action: model.addNotificationLevel).buttonStyle(.borderless)
                .id(addLevelFocusID).focused($addLevelFocused)
                .background(PanelFocusGeometry(id: addLevelFocusID, focused: addLevelFocused))
                .disabled(Model.parseThresholds(model.draft.notificationThresholds) == nil || Set(model.notificationLevels).count == 100)
        }
    }
}

struct SettingsAdvancedDisclosureStyle: DisclosureGroupStyle {
    func makeBody(configuration: Configuration) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HoverButton(bordered: true, action: { configuration.isExpanded.toggle() }) {
                HStack(spacing: 8) {
                    PanelIcon(name: "chevron-down").rotationEffect(.degrees(configuration.isExpanded ? 0 : -90))
                    configuration.label
                    Spacer()
                }
            }.accessibilityValue(configuration.isExpanded ? "Expanded" : "Collapsed")
                .accessibilityHint("Press Space to show or hide advanced notification settings.")
            if configuration.isExpanded { configuration.content }
        }
    }
}

struct NotificationSettingsView: View {
    @ObservedObject var model: Model
    @FocusState private var ruleThresholdsFocused: Bool
    @State private var ruleFocusID = UUID().uuidString
    @FocusState private var customizationFocused: Bool
    @State private var customizationFocusID = UUID().uuidString
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                SettingsHeading(title: "Quota notifications")
                Toggle("Enable quota alerts", isOn: Binding(get: { model.draft.notifications.enabled }, set: {
                    model.draft.notifications.enabled = $0; model.draft.saved = false
                })).toggleStyle(.switch).modifier(PanelFocusTarget())
                Toggle("Pause for 1 hour", isOn: Binding(get: {
                    model.draft.notifications.mutedUntil > Date().timeIntervalSince1970
                }, set: { model.muteNotifications($0 ? 3600 : 0) })).toggleStyle(.switch).modifier(PanelFocusTarget())
                if model.draft.notifications.mutedUntil > Date().timeIntervalSince1970 {
                    Text("Paused until " + Date(timeIntervalSince1970: model.draft.notifications.mutedUntil).formatted(date: .abbreviated, time: .shortened))
                        .font(.custom("GeistMono-Regular", size: 11))
                }
                Toggle("Notify when quota recovers", isOn: Binding(get: { model.draft.notifications.recovery }, set: {
                    model.draft.notifications.recovery = $0; model.draft.saved = false
                })).toggleStyle(.checkbox).modifier(PanelFocusTarget())
            }
            NotificationLevelsView(model: model)
            DisclosureGroup("Advanced", isExpanded: $model.notificationAdvancedExpanded) {
                advanced.padding(.top, 12)
            }.disclosureGroupStyle(SettingsAdvancedDisclosureStyle())
            if !model.notificationPermission.isEmpty {
                Text(model.notificationPermission).font(.custom("GeistMono-Regular", size: 11))
                Button("macOS notification settings") {
                    if let url = URL(string: "x-apple.systempreferences:com.apple.Notifications-Settings.extension") {
                        NSWorkspace.shared.open(url)
                    }
                }.buttonStyle(.borderless).modifier(PanelFocusTarget())
            }
        }.onAppear {
            if model.invalidAdvancedNotifications { model.notificationAdvancedExpanded = true }
        }.onChange(of: model.draft.notificationRuleThresholds) { _ in
            if model.invalidAdvancedNotifications { model.notificationAdvancedExpanded = true }
        }.onChange(of: model.notificationRuleFocusRequest) { _ in
            DispatchQueue.main.async { ruleThresholdsFocused = true }
        }
    }

    private var advanced: some View {
        VStack(alignment: .leading, spacing: 16) {
            Toggle("Recovery only for accounts used in the last day", isOn: Binding(get: {
                model.draft.notifications.recentOnly
            }, set: {
                model.draft.notifications.recentOnly = $0; model.draft.saved = false
            })).toggleStyle(.checkbox).modifier(PanelFocusTarget())
            schedules
            VStack(alignment: .leading, spacing: 8) {
                SettingsHeading(title: "Per-limit alerts", detail: model.notificationEditingLabel)
                if model.notificationEditingSelection != nil {
                    Button("Use menu bar limit") {
                        model.notificationEditingSelection = nil
                        DispatchQueue.main.async { customizationFocused = true }
                    }
                        .buttonStyle(.borderless).modifier(PanelFocusTarget())
                }
                Toggle("Customize alerts for this account & limit", isOn: Binding(get: {
                    model.notificationRule != nil
                }, set: model.setNotificationOverride)).toggleStyle(.checkbox)
                    .id(customizationFocusID).focused($customizationFocused)
                    .background(PanelFocusGeometry(id: customizationFocusID, focused: customizationFocused))
                if model.notificationRule != nil {
                    Toggle("Enable this limit's alerts", isOn: Binding(get: {
                        model.notificationRule?.enabled ?? true
                    }, set: model.setNotificationRuleEnabled)).toggleStyle(.checkbox).modifier(PanelFocusTarget())
                    HStack {
                        Text("Thresholds (%)")
                        TextField("80, 95, 100", text: Binding(get: {
                            model.draft.notificationRuleThresholds[model.notificationRuleKey] ?? ""
                        }, set: {
                            model.draft.notificationRuleThresholds[model.notificationRuleKey] = $0; model.draft.saved = false
                        })).textFieldStyle(.roundedBorder).id(ruleFocusID).focused($ruleThresholdsFocused)
                            .background(PanelFocusGeometry(id: ruleFocusID, focused: ruleThresholdsFocused))
                            .accessibilityLabel("This limit's alert thresholds")
                    }
                }
                if model.invalidAdvancedNotifications {
                    Text("Correct the alert levels for these limits:")
                        .font(.custom("GeistMono-Regular", size: 11)).foregroundColor(.orange)
                    ForEach(Array(model.invalidNotificationRules.enumerated()), id: \.offset) { _, rule in
                        HoverButton(bordered: true, action: { model.reviewNotificationRule(rule) }) {
                            HStack {
                                Text("Review " + model.notificationRuleLabel(rule)).fixedSize(horizontal: false, vertical: true)
                                Spacer()
                                PanelIcon(name: "arrow-right")
                            }
                        }
                    }
                }
            }
        }
    }

    private var schedules: some View {
        VStack(alignment: .leading, spacing: 8) {
            SettingsHeading(title: "Schedules", detail: "Local timezone. Leave both fields empty to disable a schedule.")
            HStack {
                Text("Quiet hours")
                TextField("HH:MM", text: Binding(get: { model.draft.notifications.quietHours.start }, set: {
                    model.draft.notifications.quietHours.start = $0; model.draft.saved = false
                })).textFieldStyle(.roundedBorder).modifier(PanelFocusTarget()).accessibilityLabel("Quiet hours start")
                Text("to")
                TextField("HH:MM", text: Binding(get: { model.draft.notifications.quietHours.end }, set: {
                    model.draft.notifications.quietHours.end = $0; model.draft.saved = false
                })).textFieldStyle(.roundedBorder).modifier(PanelFocusTarget()).accessibilityLabel("Quiet hours end")
            }
            HStack {
                Text("Work hours")
                TextField("HH:MM", text: Binding(get: { model.draft.notifications.workHours.start }, set: {
                    model.draft.notifications.workHours.start = $0; model.draft.saved = false
                })).textFieldStyle(.roundedBorder).modifier(PanelFocusTarget()).accessibilityLabel("Work hours start")
                Text("to")
                TextField("HH:MM", text: Binding(get: { model.draft.notifications.workHours.end }, set: {
                    model.draft.notifications.workHours.end = $0; model.draft.saved = false
                })).textFieldStyle(.roundedBorder).modifier(PanelFocusTarget()).accessibilityLabel("Work hours end")
            }
        }
    }
}

struct ResetCreditsPage: View {
    let provider: Provider
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 8) {
                ProviderLogo(provider: provider.providerID, path: provider.logoPath)
                Text(provider.name).foregroundColor(Palette.bright)
            }
            if provider.cached { Text("Cached data").font(.custom("GeistMono-Regular", size: 11)).help(provider.error) }
            VStack(alignment: .leading, spacing: 8) {
                Text("Usage limit resets").foregroundColor(Palette.bright)
                Text(provider.providerID == "codex" ? "Restore your 5-hour or weekly limit,\nor both, depending on the reset type." :
                     "Restore eligible usage limits.\nCredits expire on the dates below.")
            }
            if let credits = provider.resetCredits, credits.available > 0 {
                VStack(alignment: .leading, spacing: 0) {
                    HStack(spacing: 12) { Text("Reset type").frame(maxWidth: .infinity, alignment: .leading); Text("Expires").frame(maxWidth: .infinity, alignment: .leading) }
                        .font(.custom("GeistMono-Regular", size: 11)).padding(12)
                        .background(Palette.bright.opacity(0.04))
                    ForEach(Array(credits.rows.enumerated()), id: \.offset) { _, row in
                        Divider()
                        HStack(alignment: .top, spacing: 12) {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(row.title).foregroundColor(Palette.bright)
                                Text("\(row.count) \(row.count == 1 ? "credit" : "credits")").font(.custom("GeistMono-Regular", size: 11))
                            }.frame(maxWidth: .infinity, alignment: .leading)
                            VStack(alignment: .leading, spacing: 5) {
                                Text(row.expires).foregroundColor(Palette.bright)
                                Text(row.remaining).font(.custom("GeistMono-Regular", size: 11))
                            }.frame(maxWidth: .infinity, alignment: .leading)
                        }.padding(12)
                    }
                    Divider()
                    HStack(spacing: 12) {
                        Text("Available resets").foregroundColor(Palette.dim)
                        Spacer()
                        Text("\(credits.available)").foregroundColor(Palette.bright).fontWeight(.medium)
                    }.padding(12)
                        .background(Palette.bright.opacity(0.04))
                }.clipShape(RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Palette.border))
                if let timezone = credits.timezone, !timezone.isEmpty {
                    Text(timezone).font(.custom("GeistMono-Regular", size: 11)).foregroundColor(Palette.dim)
                }
                if credits.undetailed > 0 { Text("Some reset details haven't been provided yet.").font(.custom("GeistMono-Regular", size: 11)) }
            } else { Text("No reset credits available.") }
        }
    }
}

struct CloudCreditsPage: View {
    let provider: Provider
    let credit: MonetaryCredit

    private struct Field: Identifiable {
        let label: String
        let value: String
        var hint = ""
        var id: String { label }
    }
    private var fields: [Field] {
        var rows = [Field(label: "Status", value: credit.status.capitalized),
                    Field(label: "Allowance", value: credit.limitValue),
                    Field(label: "Used", value: credit.usedValue),
                    Field(label: "Expires", value: credit.expires, hint: credit.remaining),
                    Field(label: "Last observed", value: credit.observed)]
        if credit.status == "expired" || credit.status == "unavailable" {
            rows.append(Field(label: "Last observed balance", value: credit.observedValue))
        }
        return rows
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 8) {
                ProviderLogo(provider: provider.providerID, path: provider.logoPath)
                Text(credit.heading ?? (provider.name + " · " + credit.title)).foregroundColor(Palette.bright)
            }
            if provider.cached { Text("Cached data").font(.custom("GeistMono-Regular", size: 11)).help(provider.error) }
            VStack(alignment: .leading, spacing: 4) {
                Text(credit.status == "available" || credit.status == "exhausted" ? "Available balance" : "Current balance")
                    .font(.custom("GeistMono-Regular", size: 11))
                Text(credit.value).font(.custom("GeistMono-Regular", size: 24)).fontWeight(.medium)
                    .foregroundColor(Palette.bright)
            }
            Text("Credits for Claude cloud sessions.")
            if credit.status == "expired" {
                Text("These credits have expired. The last observed balance is shown for reference.")
                    .font(.custom("GeistMono-Regular", size: 11))
            } else if !credit.statusNote.isEmpty {
                Text(credit.statusNote + ". Amounts below reflect the last observation.")
                    .font(.custom("GeistMono-Regular", size: 11))
            }
            VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(fields.enumerated()), id: \.element.id) { index, field in
                    if index > 0 {
                        Rectangle().fill(Palette.border).frame(height: 1).accessibilityHidden(true)
                    }
                    HStack(alignment: .top, spacing: 0) {
                        Text(field.label).frame(maxWidth: .infinity, alignment: .leading).padding(12)
                        VStack(alignment: .leading, spacing: 5) {
                            Text(field.value).foregroundColor(Palette.bright)
                            if !field.hint.isEmpty {
                                Text(field.hint).font(.custom("GeistMono-Regular", size: 11))
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading).padding(12)
                    }
                }
            }.background {
                GeometryReader { geometry in
                    Palette.bright.opacity(0.04).frame(width: geometry.size.width / 2)
                        .overlay(alignment: .trailing) {
                            Rectangle().fill(Palette.border).frame(width: 1).accessibilityHidden(true)
                        }
                }
            }.clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Palette.border, lineWidth: 1))
            if !credit.timezone.isEmpty {
                Text("Local time · " + credit.timezone).font(.custom("GeistMono-Regular", size: 11))
            }
        }
    }
}

struct UpdatePage: View {
    @ObservedObject var model: Model
    @State private var copiedCommand = false

    private func open(_ value: String) {
        if let url = URL(string: value), url.scheme == "https" { NSWorkspace.shared.open(url) }
    }

    var body: some View {
        let guide = model.updateGuide
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 8) {
                Text(guide.title).foregroundColor(Palette.bright)
                if let version = model.snapshot?.version {
                    Text("Installed: v\(version.current)" + (version.latest.map { "\nAvailable: v" + $0 } ?? ""))
                        .font(.custom("GeistMono-Regular", size: 11))
                }
                Text(guide.description).fixedSize(horizontal: false, vertical: true)
            }
            if guide.canUpdate {
                HoverButton(bordered: true, hoverColor: Palette.update.opacity(0.10), action: model.startUpdate) {
                    HStack {
                        Text(model.updateStarting ? "Opening updater…" : guide.actionLabel)
                        Spacer()
                        PanelIcon(name: "arrow-right")
                    }.foregroundColor(Palette.update)
                }.disabled(model.updateStarting)
            }
            if !model.updateError.isEmpty {
                Text(model.updateError + "\nUse the command below or open the installation guide to retry.")
                    .foregroundColor(.orange).fixedSize(horizontal: false, vertical: true)
            }
            if !model.updateMessage.isEmpty {
                Text(model.updateMessage).foregroundColor(Palette.bright).fixedSize(horizontal: false, vertical: true)
            }
            VStack(alignment: .leading, spacing: 10) {
                ForEach(Array(guide.steps.enumerated()), id: \.offset) { index, step in
                    HStack(alignment: .top, spacing: 8) {
                        Text("\(index + 1).").foregroundColor(Palette.bright)
                        Text(step).fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            if !guide.command.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Terminal command").foregroundColor(Palette.bright)
                    HStack(alignment: .top, spacing: 8) {
                        Text(guide.command).font(.custom("GeistMono-Regular", size: 11))
                            .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        ControlButton(icon: copiedCommand ? "check" : "copy",
                                      help: copiedCommand ? "Copied" : "Copy command", action: {
                            NSPasteboard.general.clearContents()
                            copiedCommand = NSPasteboard.general.setString(guide.command, forType: .string)
                        }).accessibilityLabel("Copy command")
                    }.padding(10).frame(maxWidth: .infinity, alignment: .leading)
                        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Palette.border))
                }
            }
            VStack(spacing: 6) {
                HoverButton(action: { open(guide.releaseUrl) }) {
                    HStack { Text("Release notes"); Spacer(); PanelIcon(name: "arrow-right") }
                }
                HoverButton(action: { open(guide.guideUrl) }) {
                    HStack { Text("Installation guide"); Spacer(); PanelIcon(name: "arrow-right") }
                }
            }
            Text("Updating is optional. You can return to usage and update later.")
                .font(.custom("GeistMono-Regular", size: 11))
        }
    }
}

struct GuideFlowLayout: Layout {
    var spacing: CGFloat = 4
    private func arrangement(_ width: CGFloat, _ subviews: Subviews) -> (points: [CGPoint], size: CGSize) {
        var points: [CGPoint] = [], x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x > 0 && x + size.width > width { x = 0; y += rowHeight + spacing; rowHeight = 0 }
            points.append(CGPoint(x: x, y: y))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return (points, CGSize(width: width, height: y + rowHeight))
    }
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        arrangement(proposal.width ?? 150, subviews).size
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let points = arrangement(bounds.width, subviews).points
        for (index, subview) in subviews.enumerated() {
            subview.place(at: CGPoint(x: bounds.minX + points[index].x, y: bounds.minY + points[index].y),
                          anchor: .topLeading, proposal: .unspecified)
        }
    }
}

struct GuideActionText: View {
    let action: String
    var body: some View {
        GuideFlowLayout {
            ForEach(Array(GuidePage.tokens(action).enumerated()), id: \.offset) { _, token in
                if token.key {
                    Text(token.text).fixedSize().padding(.horizontal, 5).padding(.vertical, 2)
                        .background(RoundedRectangle(cornerRadius: 3).fill(Palette.bright.opacity(0.04)))
                        .overlay(RoundedRectangle(cornerRadius: 3).strokeBorder(Palette.border))
                        .accessibilityLabel("Key " + token.text)
                } else { Text(token.text).fixedSize().padding(.vertical, 2) }
            }
        }
    }
}

struct GuidePage: View {
    struct Token {
        let text: String
        let key: Bool
    }
    static func tokens(_ text: String) -> [Token] {
        let expression = try! NSRegularExpression(pattern: #"(?<![A-Za-z0-9])(?:Shift\+Tab|Tab|Esc|Space|C|R)(?![A-Za-z0-9])"#)
        let value = text as NSString
        var result: [Token] = [], end = 0
        for match in expression.matches(in: text, range: NSRange(location: 0, length: value.length)) {
            let plain = value.substring(with: NSRange(location: end, length: match.range.location - end))
            result += plain.split(whereSeparator: \.isWhitespace).map { Token(text: String($0), key: false) }
            result.append(Token(text: value.substring(with: match.range), key: true))
            end = NSMaxRange(match.range)
        }
        result += value.substring(from: end).split(whereSeparator: \.isWhitespace).map { Token(text: String($0), key: false) }
        return result
    }
    struct Row: Identifiable {
        let feature: String
        let action: String
        var id: String { feature }
    }
    static let rows = [
        Row(feature: "Open Usage", action: "Click the menu bar icon."),
        Row(feature: "Settings", action: "Gear icon or C on Usage; or right-click the menu bar icon → Settings."),
        Row(feature: "Refresh", action: "Refresh icon or R on Usage."),
        Row(feature: "Choose a limit", action: "Click a limit on Usage."),
        Row(feature: "Scroll content", action: "Trackpad or mouse wheel."),
        Row(feature: "Switch tabs", action: "Click a Settings tab. Scroll the strip to reveal more."),
        Row(feature: "Move focus", action: "Tab / Shift+Tab."),
        Row(feature: "Activate a button", action: "Space when focused."),
        Row(feature: "Adjust alert levels", action: "Drag a slider in Alerts."),
        Row(feature: "Reorder providers", action: "Providers → up/down buttons."),
        Row(feature: "Save settings", action: "Save applies all tabs and keeps Settings open."),
        Row(feature: "Cancel settings", action: "Cancel, Back or Esc returns to Usage without saving."),
        Row(feature: "Reset credits", action: "Click Reset credits when available."),
        Row(feature: "Cloud credits", action: "Click a Cloud credits row."),
        Row(feature: "Update AI Status", action: "Click Update available to open the update guide."),
        Row(feature: "Close the panel", action: "Esc on Usage, or click the menu bar icon again.")
    ]

    private func row(_ feature: String, _ action: String, heading: Bool = false) -> some View {
        HStack(alignment: .top, spacing: 0) {
            Text(feature).frame(maxWidth: .infinity, alignment: .leading).padding(12)
            GuideActionText(action: action).foregroundColor(Palette.bright)
                .frame(maxWidth: .infinity, alignment: .leading).padding(12)
        }.font(.custom("GeistMono-Regular", size: 11))
            .fontWeight(heading ? .medium : .regular)
            .foregroundColor(heading ? Palette.bright : Palette.dim)
            .fixedSize(horizontal: false, vertical: true)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            row("Feature", "Action / shortcut", heading: true)
            ForEach(Self.rows) { item in
                Rectangle().fill(Palette.border).frame(height: 1).accessibilityHidden(true)
                row(item.feature, item.action)
            }
        }.background {
            GeometryReader { geometry in
                Palette.bright.opacity(0.04).frame(width: geometry.size.width / 2)
                    .overlay(alignment: .trailing) {
                        Rectangle().fill(Palette.border).frame(width: 1).accessibilityHidden(true)
                    }
            }
        }.clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Palette.border, lineWidth: 1))
    }
}

struct AboutPage: View {
    let info: ProjectInfo
    @ObservedObject var model: Model
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            if let image = Assets.image() { Image(nsImage: image).resizable().scaledToFit().frame(width: 40, height: 40) }
            Text(info.name).font(.custom("GeistMono-Medium", size: 16)).foregroundColor(Palette.bright)
            Text(info.description)
            Text("Version: v\(info.version)\nCommit: \(info.commit)\nLicense: \(info.license)\nAuthor: \(info.author)")
                .font(.custom("GeistMono-Regular", size: 11))
            VStack(spacing: 6) {
                ForEach(AboutLink.allCases) { link in
                    HoverButton(bordered: true, action: { model.openAboutLink(link) }) {
                        HStack { Text(link.title); Spacer(); PanelIcon(name: "arrow-right") }
                    }
                }
            }
        }
    }
}

struct PanelScrollPreference: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) { value = nextValue() }
}

struct PanelScrollMask: View {
    let fading: Bool
    var body: some View {
        if fading {
            VStack(spacing: 0) {
                LinearGradient(stops: [.init(color: .clear, location: 0), .init(color: .white, location: 0.92),
                                       .init(color: .white, location: 1)],
                               startPoint: .top, endPoint: .bottom).frame(height: SettingsNavigation.height)
                Rectangle().fill(Color.white)
            }
        } else { Rectangle().fill(Color.white) }
    }
}

struct PanelScrollContent: View {
    @ObservedObject var model: Model
    @State private var scrollOffset: CGFloat = 0
    @State private var focusedID = ""
    var body: some View {
        GeometryReader { viewport in
            ScrollViewReader { scroll in
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        if !model.error.isEmpty { Text(model.error).font(.custom("GeistMono-Regular", size: 11)).foregroundColor(.orange) }
                        if model.page == .usage && model.snapshot?.version.hasUpdate == true {
                            HoverButton(hoverColor: Palette.update.opacity(0.10), action: model.showUpdate) {
                                HStack {
                                    Text("Update available: v" + (model.snapshot?.version.latest ?? ""))
                                    Spacer()
                                    PanelIcon(name: "arrow-right")
                                }.foregroundColor(Palette.update)
                            }.help("Show update instructions")
                        }
                        switch model.page {
                        case .usage: UsagePage(model: model)
                        case .settings: SettingsPage(model: model)
                        case .update: UpdatePage(model: model)
                        case .credits: if let provider = model.creditProvider { ResetCreditsPage(provider: provider) }
                        case .cloudCredits:
                            if let provider = model.cloudCreditProvider, let credit = model.cloudCredit {
                                CloudCreditsPage(provider: provider, credit: credit)
                            }
                        }
                    }.environment(\.panelScrollFocusTracking, true)
                        .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 16).padding(.bottom, 18)
                        .padding(.top, model.page == .settings ? SettingsNavigation.height + 18 : 18)
                        .background(GeometryReader { geometry in
                            Color.clear.preference(key: PanelScrollPreference.self, value: geometry.frame(in: .named("panel-scroll")).minY)
                        })
                        .id("page-top")
                }.coordinateSpace(name: "panel-scroll")
                    .mask(PanelScrollMask(fading: model.page == .settings && scrollOffset > 0.5))
                    .onPreferenceChange(PanelScrollPreference.self) { scrollOffset = max(0, -$0) }
                    .onPreferenceChange(PanelFocusPreference.self) { positions in
                        guard let focus = positions.first else { focusedID = ""; return }
                        guard focus.id != focusedID, focus.frame.height > 0 else { return }
                        focusedID = focus.id
                        guard model.keyboardFocusVisible else { return }
                        let top = model.page == .settings ? SettingsNavigation.height + 8 : 8
                        if focus.frame.minY < top {
                            let alignment = min(1, top / max(1, viewport.size.height - focus.frame.height))
                            scroll.scrollTo(focus.id, anchor: UnitPoint(x: 0.5, y: alignment))
                        } else if focus.frame.maxY > viewport.size.height - 8 {
                            scroll.scrollTo(focus.id, anchor: .bottom)
                        }
                    }
                    .onChange(of: model.page) { page in
                        focusedID = ""
                        if page == .settings || page == .update || model.cloudCredit != nil { scroll.scrollTo("page-top", anchor: .top) }
                    }.onChange(of: model.settingsSection) { _ in
                        focusedID = ""
                        scroll.scrollTo("page-top", anchor: .top)
                    }
            }
        }
    }
}

struct PanelView: View {
    @ObservedObject var model: Model
    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                if model.page != .usage {
                    ControlButton(icon: "arrow-left", help: "Back to usage (Esc)", action: model.back)
                        .disabled(model.settingsSaving)
                        .padding(.trailing, 4)
                }
                Text(model.page == .settings ? "Settings" : model.page == .update ? "Update AI Status" : "AI Status").foregroundColor(Palette.bright)
                Spacer(minLength: 0)
                Text(model.snapshot.map { "v" + $0.version.current } ?? "").font(.custom("GeistMono-Regular", size: 11))
                if model.page != .settings && model.page != .update {
                    ControlButton(icon: "refresh-cw", help: "Refresh usage (R)",
                                  spinning: model.snapshot?.loading == true && model.isPresented, action: model.refresh)
                        .disabled(model.snapshot?.loading == true)
                    if model.page == .usage { ControlButton(icon: "settings", help: "Configure (C)", action: model.showSettings) }
                }
            }.padding(.horizontal, 16).frame(height: 49)
            Rectangle().fill(Palette.border).frame(height: 1).accessibilityHidden(true)
            ZStack(alignment: .top) {
                PanelScrollContent(model: model).zIndex(0)
                if model.page == .settings { SettingsNavigation(model: model).zIndex(1) }
            }
            if model.page == .settings {
                Rectangle().fill(Palette.border).frame(height: 1).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 8) {
                    if !model.settingsError.isEmpty {
                        Text(model.settingsError).font(.custom("GeistMono-Regular", size: 11)).foregroundColor(.orange).padding(.top, 12)
                    } else if let validation = model.settingsValidation {
                        Text(validation.message).font(.custom("GeistMono-Regular", size: 11)).foregroundColor(.orange).padding(.top, 12)
                        if model.settingsSection != validation.section {
                            Button("Review " + validation.section.title) { model.showSettingsSection(validation.section) }
                                .buttonStyle(.borderless).disabled(model.settingsSaving)
                        }
                    }
                    HStack(spacing: 8) {
                        Spacer()
                        if model.draft.saved { Text("Saved").font(.custom("GeistMono-Regular", size: 11)) }
                        Button("Cancel", action: model.back).buttonStyle(.plain).padding(6).disabled(model.settingsSaving)
                        Button(model.settingsSaving ? "Saving…" : "Save", action: model.saveSettings)
                            .buttonStyle(.plain).padding(6).overlay(RoundedRectangle(cornerRadius: 6).stroke(Palette.border))
                            .disabled(!model.settingsValid || model.settingsSaving)
                    }.frame(height: 49)
                }.padding(.horizontal, 16)
            }
        }
        .frame(width: 380).frame(maxHeight: .infinity)
        .font(Assets.font).foregroundColor(Palette.dim).background(Palette.surface)
        .environment(\.controlKeyboardFocusVisible, model.keyboardFocusVisible)
        .preferredColorScheme(.dark)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSPopoverDelegate, UNUserNotificationCenterDelegate {
    private let model: Model
    private var statusItem: NSStatusItem!
    private let popover = NSPopover()
    private var inputMonitor: Any?
    private var signalSources: [DispatchSourceSignal] = []
    private var spinnerTimer: Timer?
    private var spinnerFrame = 0
    private let showSettingsOnLaunch: Bool
    private var notificationCheckRunning = false
    private var notificationPermissionRequested = false
    private var submittedNotificationIDs: Set<String> = []
    private var inFlightNotificationIDs: Set<String> = []
    private var notificationSelection: Selection?

    init(runtime: RuntimeConfig, settings: Bool) {
        model = Model(runtime: runtime)
        showSettingsOnLaunch = settings
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        UNUserNotificationCenter.current().delegate = self
        Assets.registerFonts()
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.target = self
        statusItem.button?.action = #selector(clicked(_:))
        statusItem.button?.sendAction(on: [.leftMouseUp, .rightMouseUp])
        popover.behavior = .transient
        popover.delegate = self
        popover.contentViewController = NSHostingController(rootView: PanelView(model: model))
        popover.contentSize = NSSize(width: 380, height: 210)
        popover.appearance = NSAppearance(named: .darkAqua)
        model.changed = { [weak self] in
            guard let self = self else { return }
            self.updateStatus()
            self.resize()
            self.checkNotifications()
            if let selection = self.notificationSelection, self.model.snapshot != nil {
                self.notificationSelection = nil
                self.model.select(selection)
            }
            if self.showSettingsOnLaunch && self.model.snapshot != nil && !self.didShowInitialSettings {
                self.didShowInitialSettings = true
                self.configure(nil)
            }
        }
        DistributedNotificationCenter.default().addObserver(self, selector: #selector(receiveCommand(_:)), name: commandNotification, object: nil)
        inputMonitor = NSEvent.addLocalMonitorForEvents(matching: [.keyDown, .leftMouseDown, .rightMouseDown, .otherMouseDown]) { [weak self] event in
            guard let self = self else { return event }
            self.model.observeFocusInput(event)
            return event.type == .keyDown ? self.handleKey(event) : event
        }
        for number in [SIGTERM, SIGINT, SIGHUP, SIGUSR2] {
            signal(number, SIG_IGN)
            let source = DispatchSource.makeSignalSource(signal: number, queue: .main)
            source.setEventHandler { NSApp.terminate(nil) }
            source.resume()
            signalSources.append(source)
        }
        updateStatus()
        model.start()
    }
    private func checkNotifications() {
        guard !notificationCheckRunning, let snapshot = model.snapshot,
              snapshot.settings.notifications?.enabled != false else { return }
        notificationCheckRunning = true
        let center = UNUserNotificationCenter.current()
        center.getNotificationSettings { [weak self] settings in
            DispatchQueue.main.async {
                guard let self = self else { return }
                switch settings.authorizationStatus {
                case .notDetermined:
                    guard !self.notificationPermissionRequested else {
                        self.notificationCheckRunning = false
                        return
                    }
                    self.notificationPermissionRequested = true
                    center.requestAuthorization(options: [.alert, .sound]) { [weak self] granted, _ in
                        DispatchQueue.main.async {
                            guard let self = self else { return }
                            self.notificationCheckRunning = false
                            self.model.notificationPermission = granted ? "" : "Allow AI Status notifications in macOS Settings to receive quota alerts."
                            if granted { self.checkNotifications() }
                        }
                    }
                case .authorized, .provisional:
                    self.model.notificationPermission = ""
                    // Stable request IDs plus Notification Center's existing IDs
                    // close the restart gap between submission and outbox ack.
                    center.getDeliveredNotifications { delivered in
                        center.getPendingNotificationRequests { pending in
                            let existing = Set(delivered.map { $0.request.identifier } + pending.map { $0.identifier })
                            DispatchQueue.main.async { [weak self] in
                                guard let self = self else { return }
                                self.notificationCheckRunning = false
                                self.submitNotifications(existing: existing)
                            }
                        }
                    }
                default:
                    self.notificationCheckRunning = false
                    self.model.notificationPermission = "Allow AI Status notifications in macOS Settings to receive quota alerts."
                }
            }
        }
    }
    private func submitNotifications(existing: Set<String>) {
        guard let snapshot = model.snapshot,
              !(snapshot.settings.notifications ?? NotificationPreferences()).isSilent() else { return }
        let center = UNUserNotificationCenter.current()
        for event in snapshot.notifications ?? [] {
            guard event.fresh else { continue }
            if ["recovery", "partial_recovery"].contains(event.kind) && snapshot.settings.notifications?.recovery == false { continue }
            if existing.contains(event.id) || submittedNotificationIDs.contains(event.id) {
                model.acknowledgeNotification(event.id)
                continue
            }
            guard !inFlightNotificationIDs.contains(event.id) else { continue }
            inFlightNotificationIDs.insert(event.id)
            let content = UNMutableNotificationContent()
            content.title = event.title
            content.body = event.body
            content.sound = .default
            content.threadIdentifier = "quota:" + event.provider
            content.userInfo = ["provider": event.provider, "idx": event.idx, "metric": event.metric]
            center.add(UNNotificationRequest(identifier: event.id, content: content, trigger: nil)) { [weak self] error in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.inFlightNotificationIDs.remove(event.id)
                    if error == nil {
                        self.submittedNotificationIDs.insert(event.id)
                        self.model.acknowledgeNotification(event.id)
                    }
                }
            }
        }
    }
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .list, .sound])
    }
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        let info = response.notification.request.content.userInfo
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { completionHandler(); return }
            if let provider = info["provider"] as? String, let idx = info["idx"] as? Int,
               let metric = info["metric"] as? String {
                let selection = Selection(provider: provider, idx: idx, metric: metric)
                if self.model.snapshot == nil { self.notificationSelection = selection }
                else { self.model.select(selection) }
            }
            self.model.page = .usage
            self.show()
            completionHandler()
        }
    }
    private var didShowInitialSettings = false
    private func resize() {
        let screenHeight = statusItem.button?.window?.screen?.visibleFrame.height ?? 800
        popover.contentSize = NSSize(width: 380, height: min(model.panelHeight, max(180, screenHeight - 80)))
    }
    private func updateStatus() {
        guard let button = statusItem.button else { return }
        let snapshot = model.snapshot
        let spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"][spinnerFrame % 10]
        var text = (snapshot?.text ?? "AI Status …").replacingOccurrences(of: "\u{f06a9}", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if snapshot?.loading != false { text = text.replacingOccurrences(of: "…", with: spinner) }
        button.title = text
        button.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        button.toolTip = model.selectedProvider.map { $0.name + ($0.cached ? " · cached" : "") } ?? "AI Status"
        let mode = snapshot?.iconMode ?? "bot"
        let source = mode == "off" ? nil : Assets.image(provider: mode == "logo" ? model.selectedProvider?.providerID ?? "" : "",
                                                       path: mode == "logo" ? snapshot?.logoPath ?? "" : "")
        if let image = source?.copy() as? NSImage {
            image.size = NSSize(width: 16, height: 16)
            // app.png includes an opaque background; treating its alpha as a
            // template would replace the artwork with a solid square.
            image.isTemplate = false
            button.image = image
        } else { button.image = nil }
        button.imagePosition = .imageLeading
        if snapshot?.loading != false && spinnerTimer == nil {
            spinnerTimer = Timer.scheduledTimer(withTimeInterval: 0.15, repeats: true) { [weak self] _ in
                self?.spinnerFrame += 1
                self?.updateStatus()
            }
        } else if snapshot?.loading == false {
            spinnerTimer?.invalidate()
            spinnerTimer = nil
        }
    }
    private func show() {
        guard let button = statusItem.button else { return }
        resize()
        model.keyboardFocusVisible = false
        model.isPresented = true
        NSApp.activate(ignoringOtherApps: true)
        if !popover.isShown { popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY) }
        popover.contentViewController?.view.window?.makeKey()
    }
    @objc private func clicked(_ sender: Any?) {
        if NSApp.currentEvent?.type == .rightMouseUp {
            let menu = NSMenu()
            for (title, selector) in [("Open dashboard", #selector(openUsage(_:))), ("Refresh", #selector(refresh(_:))),
                                      ("Settings", #selector(configure(_:))), ("About AI Status", #selector(about(_:)))] {
                let item = NSMenuItem(title: title, action: selector, keyEquivalent: "")
                item.target = self
                if title == "Refresh" { item.isEnabled = model.snapshot?.loading != true }
                menu.addItem(item)
            }
            menu.addItem(.separator())
            let quit = NSMenuItem(title: "Quit AI Status", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
            quit.target = NSApp
            menu.addItem(quit)
            menu.autoenablesItems = false
            statusItem.menu = menu
            statusItem.button?.performClick(nil)
            statusItem.menu = nil
        } else if popover.isShown { popover.performClose(nil) } else { show() }
    }
    @objc private func openUsage(_ sender: Any?) { model.page = .usage; show() }
    @objc private func refresh(_ sender: Any?) { model.refresh() }
    @objc private func configure(_ sender: Any?) { model.showSettings(); show() }
    @objc private func about(_ sender: Any?) { model.showAbout(); show() }
    @objc private func receiveCommand(_ notification: Notification) {
        switch notification.object as? String {
        case "settings": configure(nil)
        case "quit": NSApp.terminate(nil)
        default: openUsage(nil)
        }
    }
    private func handleKey(_ event: NSEvent) -> NSEvent? {
        guard popover.isShown else { return event }
        if event.keyCode == 53 {
            if model.page == .usage { popover.performClose(nil) } else { model.back() }
            return nil
        }
        guard event.modifierFlags.intersection([.command, .control, .option]).isEmpty else { return event }
        if model.page != .settings && model.page != .update {
            switch event.charactersIgnoringModifiers?.lowercased() {
            case "r": model.refresh(); return nil
            case "c": configure(nil); return nil
            default: break
            }
        }
        return event
    }
    func popoverDidClose(_ notification: Notification) {
        model.keyboardFocusVisible = false
        model.isPresented = false
        if !model.settingsSaving { model.page = .usage }
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { openUsage(nil); return false }
    func applicationWillTerminate(_ notification: Notification) {
        spinnerTimer?.invalidate()
        if let monitor = inputMonitor { NSEvent.removeMonitor(monitor) }
        DistributedNotificationCenter.default().removeObserver(self)
        model.shutdown()
        NSStatusBar.system.removeStatusItem(statusItem)
    }
}

@main enum AIStatusMain {
    static func main() {
        do {
            if CommandLine.arguments.contains("--check-runtime") {
                _ = try RuntimeConfig.load()
                print("AI Status runtime OK")
                return
            }
            if CommandLine.arguments.contains("--smoke") { try smoke(); return }
            let command = CommandLine.arguments.contains("--settings") ? "settings" : CommandLine.arguments.contains("--quit") ? "quit" : "show"
            let cache = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("ai-status")
            try FileManager.default.createDirectory(at: cache, withIntermediateDirectories: true)
            let lock = Darwin.open(cache.appendingPathComponent("macos.lock").path, O_CREAT | O_RDWR, S_IRUSR | S_IWUSR)
            guard lock >= 0 else { throw AppError.message("Unable to open the AI Status instance lock.") }
            defer { Darwin.close(lock) }
            guard flock(lock, LOCK_EX | LOCK_NB) == 0 else {
                DistributedNotificationCenter.default().postNotificationName(commandNotification, object: command, userInfo: nil, deliverImmediately: true)
                if command == "quit" {
                    // Updating must wait for the old host to release its lock;
                    // otherwise a newly launched host could exit as a duplicate.
                    let deadline = ProcessInfo.processInfo.systemUptime + 3
                    while ProcessInfo.processInfo.systemUptime < deadline {
                        if flock(lock, LOCK_EX | LOCK_NB) == 0 { return }
                        usleep(50_000)
                    }
                    throw AppError.message("AI Status did not quit. Choose Quit AI Status from its menu and retry.")
                }
                return
            }
            if command == "quit" { return }
            let runtime = try RuntimeConfig.load()
            let application = NSApplication.shared
            let delegate = AppDelegate(runtime: runtime, settings: command == "settings")
            application.delegate = delegate
            withExtendedLifetime(delegate) { application.run() }
        } catch {
            fputs("AI Status: \(error.localizedDescription)\n", stderr)
            exit(1)
        }
    }

    private static func smoke() throws {
        var previewDirectory: URL?
        if let index = CommandLine.arguments.firstIndex(of: "--preview-directory") {
            guard CommandLine.arguments.indices.contains(index + 1), !CommandLine.arguments[index + 1].hasPrefix("--") else {
                throw AppError.message("--preview-directory requires a destination folder.")
            }
            previewDirectory = URL(fileURLWithPath: CommandLine.arguments[index + 1], isDirectory: true)
            try FileManager.default.createDirectory(at: previewDirectory!, withIntermediateDirectories: true)
        }
        let sample = #"""
        {"schemaVersion":1,"text":"Codex 27%","selected":{"provider":"codex","idx":0,"metric":"weekly"},
         "iconMode":"logo","logoPath":"","loading":false,
         "providers":[{"id":"codex","idx":0,"name":"Codex (Pro)","logoPath":"","loading":false,"cached":false,"error":"",
         "metrics":[{"key":"weekly","name":"Weekly Usage","percentage":27,"detail":"Resets in 3d 14h"}],
         "resetCredits":{"available":3,"undetailed":0,"timezone":"Local time · UTC-03:00","rows":[{"title":"Full reset","count":1,"expires":"Oct 22, 18:05","remaining":"12d 1h left","timezone":"UTC-03:00"},
         {"title":"Full reset","count":1,"expires":"Oct 29, 18:05","remaining":"18d 23h left","timezone":"UTC-03:00"},
         {"title":"Full reset","count":1,"expires":"Nov 06, 20:41","remaining":"27d 1h left","timezone":"UTC-03:00"}]}},
         {"id":"claude","idx":0,"name":"Claude (Max)","logoPath":"","loading":false,"cached":false,"error":"",
         "metrics":[{"key":"rolling","name":"Rolling Usage","percentage":9,"detail":"Resets in 34m"},
         {"key":"weekly","name":"Weekly Usage","percentage":46,"detail":"Resets in 3d 12h"},
         {"key":"weekly:Fable","name":"Weekly Usage","percentage":0,"detail":"Fable · Resets in 3d 12h"}],
         "resetCredits":{"available":1,"undetailed":0,"timezone":"Local time · UTC+00:00","rows":[{"title":"Usage reset","count":1,"expires":"Oct 15, 14:00","remaining":"5d left","timezone":"UTC+00:00"}]}}],
         "settings":{"available":["codex","claude","antigravity","commandcode","copilot","kiro","opencode","zai"],
         "names":{"codex":"Codex","claude":"Claude","antigravity":"Antigravity","commandcode":"Command Code","copilot":"Copilot","kiro":"Kiro","opencode":"OpenCode","zai":"Z.AI"},
         "order":["codex","claude","antigravity","commandcode","copilot","kiro","opencode","zai"],
         "enabled":["codex","claude"],"display":{"show_provider":true,"show_model":false,"show_metric":false,"show_pct":true},"iconMode":"logo"},
         "about":{"name":"AI Status","version":"0.10.0","commit":"sample","description":"Monitor AI provider usage limits from your desktop.",
         "author":"gelzin.com","license":"MIT","github":"https://github.com/gelzinn/ai-status","documentation":"https://github.com/gelzinn/ai-status#readme","issues":"https://github.com/gelzinn/ai-status/issues/new"},
         "version":{"current":"0.10.0","latest":null,"has_update":false}}
        """#
        _ = NSApplication.shared
        Assets.registerFonts()
        guard Assets.image() != nil, Assets.url("fonts/GeistMono-Regular.ttf").map({ FileManager.default.isReadableFile(atPath: $0.path) }) == true else {
            throw AppError.message("Bundled app artwork or Geist Mono is missing.")
        }
        _ = try PanelIcons.load()
        try smokeFocusInput()
        let model = Model()
        model.accept(Data(sample.utf8))
        guard let snapshot = model.snapshot, snapshot.providers.count == 2,
              model.selectedProvider?.providerID == "codex", snapshot.providers.allSatisfy({ $0.monetaryCredits.isEmpty }) else {
            throw AppError.message("Legacy snapshot decoding failed.")
        }
        guard !model.updateGuide.canUpdate, !model.updateGuide.command.isEmpty else {
            throw AppError.message("Legacy update guide fallback failed.")
        }
        model.showSettings()
        guard model.settingsValid, model.choices.count == 4, model.draft.usageDisplay == "used" else {
            throw AppError.message("Settings model or legacy usage display fallback failed.")
        }
        model.draft.display["show_provider"] = false
        model.draft.usageDisplay = "remaining"
        model.accept(Data(sample.utf8))
        guard model.draft.display["show_provider"] == false, model.draft.usageDisplay == "remaining" else {
            throw AppError.message("A refresh replaced the settings draft.")
        }
        model.draft.usageDisplay = "invalid"
        guard !model.settingsValid else { throw AppError.message("Invalid usage display was accepted.") }
        let remainingSample = sample.replacingOccurrences(of: "\"iconMode\":\"logo\"}", with: "\"iconMode\":\"logo\",\"usageDisplay\":\"remaining\"}")
        model.accept(Data(remainingSample.utf8))
        model.showSettings()
        guard model.settingsValid, model.draft.usageDisplay == "remaining" else {
            throw AppError.message("Reopening settings did not reload the saved usage display.")
        }
        let malformed = Data(sample.replacingOccurrences(of: "\"schemaVersion\":1", with: "\"schemaVersion\":2").utf8)
        model.accept(malformed)
        guard model.snapshot?.schemaVersion == 1 else { throw AppError.message("Invalid snapshot replaced usable data.") }
        try smokeSettingsSections(sample: sample, directory: previewDirectory)
        try smokeAccounts(sample: sample, directory: previewDirectory)
        try smokeCloudCredits(sample: sample, directory: previewDirectory)
        try smokeNotifications(sample: sample)
        try smokeUpdate(sample: sample, directory: previewDirectory)
        model.isPresented = true
        let pages: [(String, Page)] = [("usage", .usage), ("settings", .settings),
                                      ("reset-credits", .credits(snapshot.providers[0].id))]
        for (name, page) in pages {
            model.page = page
            try renderSmokePage(model, name: name, directory: previewDirectory)
        }
        model.showAbout()
        try renderSmokePage(model, name: "about", directory: previewDirectory)
        print("AI Status macOS smoke OK: usage, settings subnavigation and shared draft, quota notifications, reset credits, Cloud credits, update guide, settings guide, about, accounts, metered values, resources, panel icons, keyboard focus, snapshot validation")
    }

    private static func smokeSettingsSections(sample: String, directory: URL?) throws {
        let model = Model()
        model.accept(Data(sample.utf8))
        model.showSettings()
        guard model.page == .settings, model.settingsSection == .general,
              SettingsSection.allCases.map(\.rawValue) == ["general", "appearance", "alerts", "providers", "guide", "about"] else {
            throw AppError.message("Settings did not open in General with the expected sections.")
        }
        guard let info = model.snapshot?.about,
              AboutLink.allCases.map(\.title) == ["Guide", "Report a bug", "Documentation", "GitHub"],
              AboutLink.guide.url(info) == nil,
              AboutLink.issues.url(info) == URL(string: info.issues),
              AboutLink.documentation.url(info) == URL(string: info.documentation),
              AboutLink.github.url(info) == URL(string: info.github) else {
            throw AppError.message("About link order or internal/external destinations are invalid.")
        }
        let guideRows = GuidePage.rows.map { ["feature": $0.feature, "action": $0.action] }
        let guideData = try JSONSerialization.data(withJSONObject: guideRows)
        guard !guideRows.isEmpty, Set(GuidePage.rows.map(\.id)).count == guideRows.count,
              GuidePage.rows.allSatisfy({ !$0.feature.isEmpty && !$0.action.isEmpty }),
              let decodedRows = try JSONSerialization.jsonObject(with: guideData) as? [[String: String]],
              decodedRows == guideRows else {
            throw AppError.message("Guide table contains missing, duplicate or invalid text.")
        }
        guard GuidePage.tokens("C / R / Esc / Tab / Shift+Tab / Space").filter(\.key).map(\.text)
                == ["C", "R", "Esc", "Tab", "Shift+Tab", "Space"],
              !GuidePage.tokens("Click the menu bar icon.").contains(where: { $0.key }) else {
            throw AppError.message("Guide keyboard tokens or mouse instructions are invalid.")
        }
        model.draft.selected = model.choices[2].selection
        model.draft.display["show_provider"] = false
        model.draft.iconMode = "bot"
        model.draft.usageDisplay = "remaining"
        model.toggleProvider("antigravity")
        model.moveProvider("codex", 1)
        model.draft.notifications.recovery = false
        model.draft.notifications.quietHours = NotificationHours(start: "22:00", end: "08:00")
        model.draft.notifications.workHours = NotificationHours(start: "09:00", end: "18:00")
        model.draft.notificationThresholds = "85, 95"
        model.setNotificationOverride(true)
        model.setNotificationRuleEnabled(false)
        model.draft.notificationRuleThresholds[model.notificationRuleKey] = "90, 100"
        model.notificationAdvancedExpanded = true
        model.settingsError = "Retain pending save feedback."
        let pending = model.draft
        let encoder = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        let pendingNotifications = try encoder.encode(pending.notifications)
        for section in SettingsSection.allCases {
            model.showSettingsSection(section)
            model.accept(Data(sample.utf8))
            guard model.settingsSection == section, model.page == .settings,
                  model.draft.order == pending.order, model.draft.enabled == pending.enabled,
                  model.draft.display == pending.display, model.draft.iconMode == pending.iconMode,
                  model.draft.usageDisplay == pending.usageDisplay, model.draft.selected == pending.selected,
                  model.draft.notificationThresholds == pending.notificationThresholds,
                  model.draft.notificationRuleThresholds == pending.notificationRuleThresholds,
                  model.draft.saved == pending.saved,
                  model.notificationAdvancedExpanded,
                  try encoder.encode(model.draft.notifications) == pendingNotifications,
                  model.settingsError == "Retain pending save feedback.", model.settingsValid,
                  model.settingsSelectionLabel.contains("Claude"), model.settingsSelectionLabel.contains("Weekly") else {
                throw AppError.message("Settings navigation or a refresh replaced pending edits or alert account context.")
            }
        }
        model.showSettingsSection(.general)
        model.showAbout()
        guard model.page == .settings, model.settingsSection == .about,
              model.draft.selected == pending.selected, model.draft.usageDisplay == pending.usageDisplay,
              try encoder.encode(model.draft.notifications) == pendingNotifications else {
            throw AppError.message("About did not open as a tab in the current settings session.")
        }
        model.openAboutLink(.guide)
        guard model.page == .settings, model.settingsSection == .guide,
              model.draft.selected == pending.selected, model.draft.usageDisplay == pending.usageDisplay,
              try encoder.encode(model.draft.notifications) == pendingNotifications else {
            throw AppError.message("The internal Guide link replaced pending settings edits.")
        }
        model.showSettingsSection(.general)
        guard model.draft.selected == pending.selected, model.draft.usageDisplay == pending.usageDisplay else {
            throw AppError.message("Leaving the About tab replaced pending settings edits.")
        }
        model.showSettingsSection(.alerts)
        model.settingsSaving = true
        model.showSettingsSection(.providers)
        model.showAbout()
        model.openAboutLink(.guide)
        model.back()
        guard model.page == .settings, model.settingsSection == .alerts else {
            throw AppError.message("Settings navigation was allowed during a save.")
        }
        model.settingsSaving = false
        model.draft.notificationThresholds = "80, invalid"
        model.showSettingsSection(.general)
        guard !model.settingsValid, model.settingsValidation?.section == .alerts else {
            throw AppError.message("A hidden alert validation error was lost.")
        }
        model.draft.notificationThresholds = pending.notificationThresholds
        model.draft.display = model.draft.display.mapValues { _ in false }
        guard !model.settingsValid, model.settingsValidation?.section == .appearance else {
            throw AppError.message("A hidden appearance validation error was lost.")
        }
        model.draft.display = pending.display
        model.draft.enabled = []
        guard !model.settingsValid, model.settingsValidation?.section == .providers else {
            throw AppError.message("A hidden provider validation error was lost.")
        }
        model.showAbout()
        model.back()
        guard model.page == .usage else { throw AppError.message("Back from the About tab did not leave Settings.") }
        model.showAbout()
        guard model.page == .settings, model.settingsSection == .about,
              model.draft.selected == model.snapshot?.selected else {
            throw AppError.message("Opening About outside Settings did not start a saved settings session.")
        }
        model.back()
        model.showSettings()
        guard model.page == .settings, model.settingsSection == .general,
              model.draft.selected == model.snapshot?.selected,
              model.draft.usageDisplay == "used", model.draft.iconMode == "logo",
              model.draft.enabled == Set(["codex", "claude"]), model.settingsError.isEmpty, model.settingsValid,
              !model.notificationAdvancedExpanded, model.notificationEditingSelection == nil else {
            throw AppError.message("Cancel and reopen did not restore saved settings in General.")
        }
        try smokeSettingsPreviews(sample: sample, directory: directory)
    }

    private static func smokeSettingsPreviews(sample: String, directory: URL?) throws {
        guard var document = try JSONSerialization.jsonObject(with: Data(sample.utf8)) as? [String: Any],
              var settings = document["settings"] as? [String: Any] else {
            throw AppError.message("Settings preview fixture failed.")
        }
        let names = ["codex": "Codex", "claude": "Claude", "cursor": "Cursor", "opencode": "OpenCode",
                     "copilot": "Copilot", "kiro": "Kiro", "openrouter": "OpenRouter", "anthropic-api": "Anthropic API",
                     "openai-api": "OpenAI API", "google-cloud": "Google Cloud", "grok-bot": "Grok Bot",
                     "commandcode": "Command Code", "deepinfra": "DeepInfra", "deepseek": "DeepSeek",
                     "kimi": "Kimi", "minimax": "MiniMax"]
        let order = ["codex", "claude", "cursor", "opencode", "copilot", "kiro", "openrouter", "anthropic-api",
                     "openai-api", "google-cloud", "grok-bot", "commandcode", "deepinfra", "deepseek", "kimi", "minimax"]
        settings["names"] = names
        settings["available"] = order
        settings["order"] = order
        settings["enabled"] = Array(order.prefix(4))
        document["settings"] = settings
        let model = Model()
        model.accept(try JSONSerialization.data(withJSONObject: document))
        model.showSettings()
        model.isPresented = true
        for section in SettingsSection.allCases {
            model.showSettingsSection(section)
            try renderSmokePage(model, name: "settings-" + section.rawValue, directory: directory)
        }
        model.showSettingsSection(.alerts)
        model.notificationAdvancedExpanded = true
        try renderSmokePage(model, name: "settings-alerts-advanced", directory: directory)
    }

    private static func smokeNotifications(sample: String) throws {
        guard var document = try JSONSerialization.jsonObject(with: Data(sample.utf8)) as? [String: Any],
              var settings = document["settings"] as? [String: Any] else { throw AppError.message("Notification sample failed.") }
        settings["notifications"] = ["enabled": true, "thresholds": [80, 95, 100], "recovery": true,
                                     "recent_only": true, "muted_until": 0,
                                     "quiet_hours": ["start": "22:00", "end": "08:00"],
                                     "work_hours": ["start": "09:00", "end": "18:00"],
                                     "rules": [["connection_id": "claude", "metric": "weekly:Fable",
                                                "thresholds": [90, 100], "enabled": false]]]
        document["settings"] = settings
        document["notifications"] = [["id": "smoke-event", "title": "AI Status · Quota alert", "body": "Codex weekly: 95% used.",
                                      "kind": "threshold", "provider": "codex", "idx": 0, "metric": "weekly",
                                      "queued_at": Date().timeIntervalSince1970]]
        let model = Model()
        model.accept(try JSONSerialization.data(withJSONObject: document))
        model.showSettings()
        guard model.settingsValid, model.snapshot?.notifications?.first?.fresh == true,
              model.snapshot?.notifications?.first?.selection == Selection(provider: "codex", metric: "weekly"),
              model.draft.notifications.recentOnly, model.draft.notifications.workHours.start == "09:00",
              model.draft.notifications.rules.first?.enabled == false else {
            throw AppError.message("Native notification settings or queue decoding failed.")
        }
        guard model.notificationLevels == [80, 95, 100] else { throw AppError.message("Alert levels did not decode for sliders.") }
        model.setNotificationLevel(0, 1)
        model.setNotificationLevel(1, 100)
        model.setNotificationLevel(0, 101)
        guard model.notificationLevels == [1, 100, 100], Model.parseThresholds(model.draft.notificationThresholds) == [1, 100] else {
            throw AppError.message("Slider limits or existing threshold normalization changed.")
        }
        model.removeNotificationLevel(2)
        model.addNotificationLevel()
        guard model.notificationLevels == [1, 100, 80] else { throw AppError.message("Adding or removing an alert level lost pending slider edits.") }
        while !model.notificationLevels.isEmpty { model.removeNotificationLevel(0) }
        guard model.notificationLevels.isEmpty, model.settingsValid else { throw AppError.message("Empty alert levels changed existing native validation.") }
        model.draft.notificationThresholds = "80, 95, 100"
        let overrideKey = model.draft.notificationRuleThresholds.keys.first!
        model.draft.notificationRuleThresholds[overrideKey] = "invalid"
        model.showSettingsSection(.alerts)
        guard !model.settingsValid, model.notificationAdvancedExpanded else {
            throw AppError.message("An invalid hidden notification override did not expand Advanced.")
        }
        let menuBarSelection = model.draft.selected
        model.setNotificationOverride(true)
        let menuBarRuleKey = model.notificationRuleKey
        model.draft.notificationRuleThresholds[menuBarRuleKey] = "101"
        guard model.invalidNotificationRules.count == 2,
              let firstInvalid = model.invalidNotificationRules.first else {
            throw AppError.message("Multiple invalid notification rules were not identified.")
        }
        model.reviewNotificationRule(firstInvalid)
        guard model.notificationRuleKey == overrideKey, model.notificationEditingLabel.contains("Claude"),
              model.notificationEditingLabel.contains("Fable"), model.draft.selected == menuBarSelection,
              model.notificationAdvancedExpanded, model.notificationRuleFocusRequest == 1 else {
            throw AppError.message("Reviewing a hidden rule changed menu bar selection or failed to target its editor.")
        }
        model.draft.notificationRuleThresholds[overrideKey] = "90, 100"
        guard let secondInvalid = model.invalidNotificationRules.first else { throw AppError.message("Another invalid rule was lost during review.") }
        model.reviewNotificationRule(secondInvalid)
        model.draft.notificationRuleThresholds[model.notificationRuleKey] = "85, 100"
        guard model.invalidNotificationRules.isEmpty, model.settingsValid,
              model.draft.selected == menuBarSelection else { throw AppError.message("Resolving rule errors changed another setting.") }
        model.notificationEditingSelection = nil
        model.showSettingsSection(.appearance)
        model.showSettingsSection(.alerts)
        guard model.notificationAdvancedExpanded else { throw AppError.message("Settings navigation discarded Advanced disclosure state.") }
        model.draft.notificationThresholds = "80, invalid"
        guard !model.settingsValid else { throw AppError.message("Invalid notification thresholds were accepted.") }
        model.draft.notificationThresholds = "95, 80, 95, 100"
        guard model.settingsValid, Model.parseThresholds(model.draft.notificationThresholds) == [80, 95, 100],
              Model.parseThresholds("101") == nil, Model.parseThresholds("80,") == nil else {
            throw AppError.message("Notification threshold validation failed.")
        }
        model.setNotificationOverride(true)
        model.setNotificationRuleEnabled(false)
        guard model.notificationRule?.enabled == false, model.draft.notifications.rules.count == 2 else {
            throw AppError.message("Account and limit notification override failed.")
        }
        model.setNotificationOverride(false)
        guard model.draft.notifications.rules.count == 1, model.draft.notifications.rules.first?.connectionID == "claude" else {
            throw AppError.message("Editing a notification override changed another account's rule.")
        }
        model.muteNotifications(3600)
        guard model.draft.notifications.mutedUntil > Date().timeIntervalSince1970 else {
            throw AppError.message("Notification silence deadline failed.")
        }
        model.muteNotifications(0)
        let roundtrip = try JSONDecoder().decode(NotificationPreferences.self, from: JSONEncoder().encode(model.draft.notifications))
        guard roundtrip.mutedUntil == 0, roundtrip.recentOnly, roundtrip.rules.count == 1,
              roundtrip.quietHours.end == "08:00", roundtrip.workHours.end == "18:00" else {
            throw AppError.message("Saving notifications lost recovery, schedule or account preferences.")
        }
        guard let quiet = Calendar.current.date(bySettingHour: 23, minute: 15, second: 0, of: Date()),
              let working = Calendar.current.date(bySettingHour: 11, minute: 0, second: 0, of: Date()),
              let offWork = Calendar.current.date(bySettingHour: 20, minute: 0, second: 0, of: Date()),
              roundtrip.isSilent(at: quiet), !roundtrip.isSilent(at: working), roundtrip.isSilent(at: offWork) else {
            throw AppError.message("Native quiet and working hours did not protect delayed notification delivery.")
        }
    }

    private static func smokeUpdate(sample: String, directory: URL?) throws {
        guard var document = try JSONSerialization.jsonObject(with: Data(sample.utf8)) as? [String: Any] else {
            throw AppError.message("Update sample setup failed.")
        }
        document["version"] = ["current": "0.10.0", "latest": "0.12.1", "has_update": true] as [String: Any]
        document["update"] = [
            "method": "macos-installer", "title": "Update AI Status on macOS",
            "description": "Install the latest stable version. Your settings and provider connections are preserved.",
            "steps": ["Open the updater in Terminal.", "Follow its progress. AI Status restarts after installation."],
            "command": "curl -fsSL https://ai-status.gelzin.com/install/macos | bash",
            "actionLabel": "Open updater in Terminal", "canUpdate": true,
            "releaseUrl": "https://github.com/gelzinn/ai-status/releases/latest",
            "guideUrl": "https://ai-status.gelzin.com/macos",
        ] as [String: Any]
        // No runtime is provided: smoke tests never execute the installer.
        let model = Model()
        model.accept(try JSONSerialization.data(withJSONObject: document))
        guard let selection = model.snapshot?.selected, model.updateGuide.canUpdate,
              model.updateGuide.steps.count == 2, model.snapshot?.version.latest == "0.12.1" else {
            throw AppError.message("Update guide decoding failed.")
        }
        model.isPresented = true
        try renderSmokePage(model, name: "update-available", directory: directory)
        model.showUpdate()
        guard model.page == .update else { throw AppError.message("Update guide navigation failed.") }
        try renderSmokePage(model, name: "update-guide", directory: directory)
        model.startUpdate()
        guard !model.updateStarting, !model.updateError.isEmpty, model.updateMessage.isEmpty else {
            throw AppError.message("Unavailable update runtime did not expose a retry guide.")
        }
        try renderSmokePage(model, name: "update-error", directory: directory)
        try smokeUpdateResult(document: document, directory: directory)
        model.back()
        guard model.page == .usage, model.snapshot?.selected == selection else {
            throw AppError.message("Returning from the update guide changed the selected metric.")
        }
        document.removeValue(forKey: "update")
        model.accept(try JSONSerialization.data(withJSONObject: document))
        model.showUpdate()
        model.startUpdate()
        guard !model.updateGuide.canUpdate, model.updateError.isEmpty, !model.updateStarting else {
            throw AppError.message("Manual update fallback attempted to run an updater.")
        }
        try renderSmokePage(model, name: "update-manual", directory: directory)
    }

    private static func smokeUpdateResult(document: [String: Any], directory: URL?) throws {
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent("ai-status-update-smoke-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let script = temporary.appendingPathComponent("fixture.sh")
        let model = Model(runtime: RuntimeConfig(python: "/bin/sh", cli: script.path))
        defer { model.shutdown() }
        model.accept(try JSONSerialization.data(withJSONObject: document))
        model.showUpdate()
        // Only fixture output is executed; no installer or network request runs.
        try "printf '%s\\n' 'AI Status is already up to date.'\n".write(to: script, atomically: true, encoding: .utf8)
        model.startUpdate()
        try awaitSmokeUpdateResult(model)
        guard model.updateError.isEmpty, model.updateMessage == "AI Status is already up to date." else {
            throw AppError.message("Update result did not preserve the CLI status.")
        }
        model.isPresented = true
        try renderSmokePage(model, name: "update-up-to-date", directory: directory)
        try "printf '%s\\n' 'Could not open Terminal.' >&2\nexit 1\n".write(to: script, atomically: true, encoding: .utf8)
        model.startUpdate()
        try awaitSmokeUpdateResult(model)
        guard model.updateError == "Could not open Terminal.", model.updateMessage.isEmpty else {
            throw AppError.message("A failed update command reported a successful handoff.")
        }
    }

    private static func awaitSmokeUpdateResult(_ model: Model) throws {
        let deadline = Date().addingTimeInterval(3)
        while model.updateStarting && Date() < deadline {
            RunLoop.current.run(until: Date().addingTimeInterval(0.01))
        }
        guard !model.updateStarting else { throw AppError.message("Update result fixture timed out.") }
    }

    private static func smokeFocusInput() throws {
        func tabEvent(_ modifiers: NSEvent.ModifierFlags) -> NSEvent? {
            NSEvent.keyEvent(with: .keyDown, location: .zero, modifierFlags: modifiers, timestamp: 0,
                             windowNumber: 0, context: nil, characters: "\t", charactersIgnoringModifiers: "\t",
                             isARepeat: false, keyCode: 48)
        }
        guard let tab = tabEvent([]), let backTab = tabEvent(.shift), let commandTab = tabEvent(.command),
              let click = NSEvent.mouseEvent(with: .leftMouseDown, location: .zero, modifierFlags: [], timestamp: 0,
                                            windowNumber: 0, context: nil, eventNumber: 0, clickCount: 1, pressure: 1) else {
            throw AppError.message("Unable to create keyboard focus smoke events.")
        }
        let model = Model()
        guard !model.keyboardFocusVisible else { throw AppError.message("Initial focus showed a keyboard outline.") }
        model.observeFocusInput(tab)
        guard !model.keyboardFocusVisible else { throw AppError.message("A hidden panel accepted Tab focus.") }
        model.isPresented = true
        model.observeFocusInput(commandTab)
        guard !model.keyboardFocusVisible else { throw AppError.message("Command-Tab enabled a panel focus outline.") }
        model.observeFocusInput(tab)
        guard model.keyboardFocusVisible else { throw AppError.message("Tab navigation did not enable a focus outline.") }
        model.observeFocusInput(click)
        guard !model.keyboardFocusVisible else { throw AppError.message("A mouse click retained the keyboard focus outline.") }
        model.observeFocusInput(backTab)
        guard model.keyboardFocusVisible else { throw AppError.message("Shift-Tab navigation did not enable a focus outline.") }
        model.page = .settings
        guard !model.keyboardFocusVisible else { throw AppError.message("A new page inherited a keyboard focus outline.") }
        model.observeFocusInput(tab)
        model.showSettingsSection(.alerts)
        guard model.settingsSection == .alerts, model.keyboardFocusVisible else {
            throw AppError.message("Settings subnavigation discarded keyboard focus feedback.")
        }
    }

    private static func smokeCloudCredits(sample: String, directory: URL?) throws {
        guard var document = try JSONSerialization.jsonObject(with: Data(sample.utf8)) as? [String: Any],
              var settings = document["settings"] as? [String: Any],
              let providers = document["providers"] as? [[String: Any]],
              var provider = providers.last else { throw AppError.message("Cloud credits sample setup failed.") }
        let identity = "account:cloud-work"
        provider["id"] = identity
        provider["providerId"] = "claude"
        provider["idx"] = 2
        provider["name"] = "Claude (Max) · Work"
        settings["available"] = [identity]
        settings["enabled"] = [identity]
        settings["order"] = [identity]
        settings["names"] = [identity: "Claude · Work"]
        settings["providerIds"] = [identity: "claude"]
        document["settings"] = settings
        document["selected"] = ["provider": identity, "idx": 2, "metric": "rolling"] as [String: Any]
        let states = [("available", "$42.50", 42.5), ("exhausted", "$0.00", 0.0),
                      ("expired", "Expired", 75.25), ("unavailable", "Unavailable", 75.25)]
        for (state, value, balance) in states {
            let detail = state.capitalized + " · Expires 2026-11-05T07:59:00Z"
            var credit: [String: Any] = ["id": "claude-cloud", "title": "Cloud credits", "currency": "USD",
                "heading": "Claude (Max) · Cloud credits · Work",
                "status": state, "value": value, "balance": state == "available" || state == "exhausted" ? balance as Any : NSNull(),
                "stale": state == "unavailable", "expires": "Nov 05, 2026, 07:59", "remaining": state == "expired" ? "Expired" : "24d 13h left",
                "timezone": "UTC+00:00", "observed": "Oct 11, 2026, 18:05", "observed_value": String(format: "$%.2f", balance),
                "limit_value": "$100.00", "used_value": String(format: "$%.2f", 100 - balance),
                "status_note": state == "unavailable" ? "Refresh unavailable" : "", "detail": detail]
            provider["monetaryCredits"] = [credit]
            provider["metrics"] = [
                ["key": "rolling", "name": "Rolling Usage", "percentage": 9,
                 "detail": "Resets in 34m"] as [String: Any],
                ["key": "credits:claude-cloud", "name": "Cloud credits", "percentage": NSNull(),
                 "hasPercentage": false, "value": value, "isAmount": state == "available" || state == "exhausted",
                 "detail": detail] as [String: Any],
            ]
            document["providers"] = [provider]
            document["text"] = "Claude (Max) · Work " + value
            let model = Model()
            model.accept(try JSONSerialization.data(withJSONObject: document))
            guard let current = model.selectedProvider, current.providerID == "claude",
                  current.metrics.count == 2, current.metrics[0].percentage == 9,
                  current.metrics[1].percentage == nil, current.metrics[1].usable,
                  current.metrics[1].displayValue == value, current.metrics[1].detail == detail,
                  current.monetaryCredits.count == 1, current.monetaryCredits[0].status == state,
                  current.resetCredits?.available == 1 else {
                throw AppError.message("Cloud credits state or coexistence with quota and reset credits failed.")
            }
            let selection = current.selection(current.metrics[1])
            guard selection.provider == identity, selection.idx == 2, selection.metric == "credits:claude-cloud" else {
                throw AppError.message("Cloud credits selection lost its account identity.")
            }
            model.isPresented = true
            try renderSmokePage(model, name: "cloud-" + state, directory: directory)
            let quotaSelection = model.snapshot?.selected
            model.keyboardFocusVisible = true
            model.showCloudCredits(current, current.monetaryCredits[0])
            guard model.page == .cloudCredits(current.id, "claude-cloud"), model.cloudCreditProvider?.idx == 2,
                  model.cloudCredit?.value == value, model.cloudCredit?.expires == "Nov 05, 2026, 07:59",
                  model.cloudCredit?.remaining == (state == "expired" ? "Expired" : "24d 13h left"),
                  model.cloudCredit?.observedValue == String(format: "$%.2f", balance),
                  model.cloudCredit?.limitValue == "$100.00", model.cloudCredit?.usedValue == String(format: "$%.2f", 100 - balance),
                  model.cloudCredit?.observed == "Oct 11, 2026, 18:05",
                  model.cloudCredit?.heading == "Claude (Max) · Cloud credits · Work",
                  model.cloudCredit?.timezone == "UTC+00:00", !model.keyboardFocusVisible,
                  model.snapshot?.selected == quotaSelection else {
                throw AppError.message("Cloud details navigation changed quota selection, lost its account, or omitted expiration details.")
            }
            try renderSmokePage(model, name: "cloud-details-" + state, directory: directory)
            if state == "available" {
                var legacyCredit = credit
                for field in ["heading", "expires", "remaining", "timezone", "observed", "observed_value", "limit_value", "used_value", "status_note"] {
                    legacyCredit.removeValue(forKey: field)
                }
                let legacy = try JSONDecoder().decode(MonetaryCredit.self, from: JSONSerialization.data(withJSONObject: legacyCredit))
                guard legacy.heading == nil, legacy.expires == "Not reported", legacy.limitValue == "Not reported", legacy.observedValue == "Not reported" else {
                    throw AppError.message("Legacy Cloud details invented missing balances or expiration.")
                }
                // A new snapshot updates an already open page without reopening it.
                credit["status"] = "expired"
                credit["value"] = "Expired"
                credit["remaining"] = "Expired"
                provider["monetaryCredits"] = [credit]
                document["providers"] = [provider]
                model.accept(try JSONSerialization.data(withJSONObject: document))
                guard model.page == .cloudCredits(current.id, "claude-cloud"), model.cloudCredit?.status == "expired",
                      model.snapshot?.selected == quotaSelection else {
                    throw AppError.message("An open Cloud details page did not follow offline expiration.")
                }
                var other = provider
                other["id"] = "account:cloud-personal"
                other["name"] = "Claude (Max) · Personal"
                other["monetaryCredits"] = [credit.merging(["value": "$8.25", "status": "available", "heading": "Claude (Max) · Cloud credits · Personal"]) { _, new in new }]
                // Reorder two accounts with the same credit ID and keep the exact entry.
                document["providers"] = [other, provider]
                model.accept(try JSONSerialization.data(withJSONObject: document))
                guard model.cloudCreditProvider?.connectionID == identity, model.cloudCredit?.value == "Expired" else {
                    throw AppError.message("Cloud details followed another account after a refresh.")
                }
                provider["monetaryCredits"] = []
                document["providers"] = [other, provider]
                model.accept(try JSONSerialization.data(withJSONObject: document))
                guard model.page == .usage, model.snapshot?.selected == quotaSelection else {
                    throw AppError.message("A removed Cloud credit left a stale details page open.")
                }
                model.showCloudCredits(current, current.monetaryCredits[0])
                guard model.page == .usage else {
                    throw AppError.message("An old Cloud button reopened a removed credit.")
                }
                provider["monetaryCredits"] = [credit]
                document["providers"] = [other, provider]
                model.accept(try JSONSerialization.data(withJSONObject: document))
                model.showCloudCredits(current, current.monetaryCredits[0])
                document["providers"] = [other]
                model.accept(try JSONSerialization.data(withJSONObject: document))
                guard model.page == .usage else {
                    throw AppError.message("A removed Cloud account left a stale details page open.")
                }
                provider["monetaryCredits"] = [credit]
                document["providers"] = [provider]
                model.accept(try JSONSerialization.data(withJSONObject: document))
            }
            model.back()
            guard model.page == .usage, model.snapshot?.selected == quotaSelection else {
                throw AppError.message("Going back from Cloud details changed quota selection.")
            }
            model.showCredits(current)
            guard model.page == .credits(current.id), model.creditProvider?.resetCredits?.available == 1 else {
                throw AppError.message("Cloud details displaced the existing reset credits page.")
            }
            model.showSettings()
            guard model.settingsValid, model.choices.count == 2,
                  model.choices.first(where: { $0.selection == selection })?.label == "Claude (Max) · Work · Cloud credits" else {
                throw AppError.message("Cloud credits account settings label exposes an internal identity or omits the metric.")
            }
        }
    }

    private static func smokeAccounts(sample: String, directory: URL?) throws {
        guard var document = try JSONSerialization.jsonObject(with: Data(sample.utf8)) as? [String: Any],
              var settings = document["settings"] as? [String: Any] else {
            throw AppError.message("Account sample setup failed.")
        }
        let identities = ["account:personal", "account:work"]
        document["providers"] = zip(identities, ["Personal", "Work"]).map { identity, label -> [String: Any] in
            let balance = label == "Work" ? "$42.50" : "$8.25"
            return ["id": identity, "providerId": "openrouter", "idx": 0, "name": "OpenRouter · " + label,
                    "logoPath": "", "loading": false, "cached": false, "error": "", "resetCredits": NSNull(),
                    "metrics": [
                        ["key": "balance:Available balance", "name": "Available balance", "percentage": NSNull(),
                         "value": balance, "isAmount": true, "hasPercentage": false, "detail": ""],
                        ["key": "credits:Account credits", "name": "Account credits", "percentage": 25,
                         "value": "$25.00 / $100.00", "isAmount": false, "hasPercentage": true, "detail": "Available balance: $75.00"],
                        ["key": "monthly", "name": "Monthly Usage", "percentage": NSNull(),
                         "value": "Unlimited", "isAmount": false, "hasPercentage": false, "detail": "Included usage"],
                    ]]
        }
        settings["available"] = identities
        settings["enabled"] = identities
        settings["order"] = identities
        settings["names"] = ["account:personal": "OpenRouter · Personal", "account:work": "OpenRouter · Work"]
        settings["providerIds"] = ["account:personal": "openrouter", "account:work": "openrouter"]
        document["settings"] = settings
        document["selected"] = ["provider": "account:work", "idx": 0, "metric": "balance:Available balance"] as [String: Any]
        document["text"] = "OpenRouter · Work $42.50"
        let model = Model()
        model.accept(try JSONSerialization.data(withJSONObject: document))
        guard let snapshot = model.snapshot, snapshot.providers.count == 2,
              Set(snapshot.providers.map { $0.id }).count == 2,
              let current = model.selectedProvider, current.connectionID == "account:work", current.providerID == "openrouter",
              current.metrics[0].percentage == nil, current.metrics[0].isAmount, current.metrics[0].displayValue == "$42.50",
              current.metrics[1].percentage == 25, current.metrics[1].displayValue == "$25.00 / $100.00",
              current.metrics[2].percentage == nil, current.metrics[2].displayValue == "Unlimited" else {
            throw AppError.message("Account identities or metered metric decoding failed.")
        }
        let selection = current.selection(current.metrics[0])
        guard selection.provider == "account:work", selection.metric == "balance:Available balance" else {
            throw AppError.message("Account metric selection lost its connection identity.")
        }
        model.isPresented = true
        try renderSmokePage(model, name: "accounts-usage", directory: directory)
        model.showSettings()
        guard model.settingsValid, model.choices.count == 6,
              Set(model.choices.map { $0.selection.provider }) == Set(identities),
              model.logoProviderID("account:work") == "openrouter" else {
            throw AppError.message("Account settings or provider artwork mapping failed.")
        }
        model.moveProvider("account:work", -1)
        model.toggleProvider("account:personal")
        guard model.draft.order.first == "account:work", model.draft.enabled == Set(["account:work"]),
              model.settingsValid, model.draft.selected.provider == "account:work" else {
            throw AppError.message("Reordering or disabling one account changed another account.")
        }
    }

    private static func renderSmokePage(_ model: Model, name: String, directory: URL?) throws {
        let host = NSHostingController(rootView: PanelView(model: model).transaction {
            $0.disablesAnimations = true
            $0.animation = nil
        })
        host.view.frame = NSRect(x: 0, y: 0, width: 380, height: model.panelHeight)
        host.view.layoutSubtreeIfNeeded()
        if let directory = directory {
            let window = NSWindow(contentRect: host.view.frame, styleMask: [.borderless], backing: .buffered, defer: false)
            window.isReleasedWhenClosed = false
            window.appearance = NSAppearance(named: .darkAqua)
            window.contentViewController = host
            window.setFrameOrigin(NSPoint(x: -10_000, y: -10_000))
            window.orderFront(nil)
            defer { window.close() }
            // Let SwiftUI mount once with animations disabled for deterministic fills.
            RunLoop.current.run(until: Date().addingTimeInterval(0.1))
            host.view.layoutSubtreeIfNeeded()
            func capture(_ captureName: String) throws {
                host.view.displayIfNeeded()
                guard let bitmap = host.view.bitmapImageRepForCachingDisplay(in: host.view.bounds) else {
                    throw AppError.message("Unable to render the \(captureName) preview.")
                }
                host.view.cacheDisplay(in: host.view.bounds, to: bitmap)
                guard let png = bitmap.representation(using: .png, properties: [:]) else {
                    throw AppError.message("Unable to encode the \(captureName) preview.")
                }
                try png.write(to: directory.appendingPathComponent(captureName + ".png"), options: .atomic)
            }
            try capture(name)
            if name.hasPrefix("settings-") {
                func scrollViews(_ view: NSView) -> [NSScrollView] {
                    var result = (view as? NSScrollView).map { [$0] } ?? []
                    for child in view.subviews { result += scrollViews(child) }
                    return result
                }
                guard let scroll = scrollViews(host.view).filter({ $0.contentView.bounds.height > SettingsNavigation.height })
                        .max(by: { $0.contentView.bounds.height < $1.contentView.bounds.height }),
                      let document = scroll.documentView else {
                    throw AppError.message("Unable to inspect the \(name) native content scroll view.")
                }
                let clip = scroll.contentView
                let range = max(0, document.frame.height - clip.bounds.height)
                print("AI Status macOS \(name): native vertical scroll range \(range)")
                if range > 0.5 {
                    var destination = clip.bounds
                    destination.origin.y = document.isFlipped ? document.frame.maxY - clip.bounds.height : document.frame.minY
                    destination = clip.constrainBoundsRect(destination)
                    clip.scroll(to: destination.origin)
                    scroll.reflectScrolledClipView(clip)
                    RunLoop.current.run(until: Date().addingTimeInterval(0.1))
                    host.view.layoutSubtreeIfNeeded()
                    guard abs(clip.bounds.minY - destination.minY) < 1 else {
                        throw AppError.message("The \(name) native scroll view did not reach its end.")
                    }
                    try capture(name + "-bottom")
                }
            }
        }
    }
}
