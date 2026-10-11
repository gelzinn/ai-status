// Native macOS adapter. Provider collection and preferences remain in Python.
// Build with swiftc -parse-as-library -framework Cocoa -framework SwiftUI.
import Cocoa
import CoreText
import Darwin
import SwiftUI

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
    var id: String { "\(connectionID):\(idx)" }
    enum CodingKeys: String, CodingKey {
        case connectionID = "id"
        case providerID = "providerId"
        case idx, name, logoPath, loading, cached, error, metrics, resetCredits
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
    }
    func selection(_ metric: Metric) -> Selection {
        Selection(provider: connectionID, idx: idx, metric: metric.key)
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
}

enum Page: Equatable {
    case usage, settings, about, update, credits(String)
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
    var selected = Selection()
    var saved = false
}

enum Assets {
    static let font = Font.custom("GeistMono-Regular", size: 13)
    static let cache = NSCache<NSString, NSImage>()
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

final class Model: ObservableObject {
    @Published var snapshot: Snapshot?
    @Published var page: Page = .usage
    @Published var draft = SettingsDraft()
    @Published var error = ""
    @Published var settingsError = ""
    @Published var settingsSaving = false
    @Published var updateStarting = false
    @Published var updateError = ""
    @Published var updateMessage = ""
    @Published var isPresented = false
    var changed: (() -> Void)?
    private let runtime: RuntimeConfig?
    private var backend: Process?
    private var actionProcess: Process?
    private var actions: [([String], ((String) -> Void)?, (String?) -> Void)] = []
    private var reconnect: DispatchWorkItem?
    private var retryDelay = 1.0
    private var stopping = false

    init(runtime: RuntimeConfig? = nil) { self.runtime = runtime }

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
                    let suffix = metric.key.split(separator: ":", maxSplits: 1).dropFirst().first.map { " (\($0))" } ?? ""
                    return Choice(selection: provider.selection(metric), label: provider.name + " · " + metric.name + suffix,
                                  provider: provider.providerID, logoPath: provider.logoPath)
                }
            }
        }
    }

    var settingsValid: Bool {
        !draft.enabled.isEmpty && draft.display.values.contains(true) && choices.contains { $0.selection == draft.selected }
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
    var updateGuide: UpdateGuide { snapshot?.update ?? .manualMacOS }
    var panelHeight: CGFloat {
        switch page {
        case .settings: return 680
        case .about: return 640
        case .update: return 600
        case .credits: return min(680, CGFloat(310 + (creditProvider?.resetCredits?.rows.count ?? 0) * 82))
        case .usage:
            guard let providers = snapshot?.providers, !providers.isEmpty else { return 210 }
            let height = providers.reduce(85) { total, provider in
                total + 62 + provider.metrics.count * 78 + (provider.cached ? 18 : 0)
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
                              selected: snapshot.selected)
        settingsError = ""
        page = .settings
        changed?()
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
        let payload: [String: Any] = ["enabled": draft.order.filter { draft.enabled.contains($0) },
                                     "display": draft.display, "iconMode": draft.iconMode, "selected": selection]
        guard let data = try? JSONSerialization.data(withJSONObject: payload), let json = String(data: data, encoding: .utf8) else { return }
        settingsSaving = true
        settingsError = ""
        draft.saved = false
        enqueue(["save-settings", "--frontend", "macos", "--settings-json", json]) { [weak self] error in
            guard let self = self else { return }
            self.settingsSaving = false
            self.settingsError = error ?? ""
            self.draft.saved = error == nil
        }
    }
    func showCredits(_ provider: Provider) {
        guard (provider.resetCredits?.available ?? 0) > 0 else { return }
        page = .credits(provider.id)
        changed?()
    }
    func showAbout() { page = .about; changed?() }
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
        page = page == .about ? .settings : .usage
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
        .background(RoundedRectangle(cornerRadius: 6).fill(hovering && enabled ? hoverColor : .clear))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(bordered ? Palette.border : .clear))
        .opacity(enabled ? 1 : 0.4)
        .onHover { hovering = $0 }
    }
}

struct ControlButton: View {
    let symbol: String
    let help: String
    var spinning = false
    let action: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var body: some View {
        Button(action: action) {
            Image(systemName: symbol).font(.system(size: 14)).rotationEffect(.degrees(spinning && !reduceMotion ? 360 : 0))
                .animation(spinning && !reduceMotion ? .linear(duration: 1).repeatForever(autoreverses: false) : nil, value: spinning)
                .frame(width: 28, height: 28).contentShape(Rectangle())
        }.buttonStyle(.plain).help(help).accessibilityLabel(help)
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
                    if let credits = provider.resetCredits, credits.available > 0 {
                        HoverButton(action: { model.showCredits(provider) }) {
                            HStack {
                                Text("Reset credits: \(credits.available) available")
                                Spacer()
                                Image(systemName: "arrow.right")
                            }
                        }.padding(.leading, 18)
                    }
                }
            }
        }
    }
}

struct SettingsPage: View {
    @ObservedObject var model: Model
    private let fields = [("show_provider", "Provider name"), ("show_model", "Model / plan"),
                          ("show_metric", "Limit name"), ("show_pct", "Usage value")]
    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Active provider & limit").foregroundColor(Palette.bright)
                Picker("Active provider & limit", selection: Binding(get: { model.draft.selected }, set: {
                    model.draft.selected = $0; model.draft.saved = false
                })) {
                    if model.choices.isEmpty { Text("Choose a provider and limit").tag(Selection()) }
                    ForEach(model.choices) { choice in
                        Label { Text(choice.label) } icon: { ProviderLogo(provider: choice.provider, path: choice.logoPath) }
                            .tag(choice.selection)
                    }
                }.labelsHidden().pickerStyle(.menu).frame(maxWidth: .infinity, alignment: .leading)
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Bar display").foregroundColor(Palette.bright)
                ForEach(fields, id: \.0) { key, label in
                    Toggle(label, isOn: Binding(get: { model.draft.display[key] ?? false }, set: {
                        model.draft.display[key] = $0; model.draft.saved = false
                    })).toggleStyle(.checkbox)
                }
                Picker("Icon", selection: Binding(get: { model.draft.iconMode }, set: {
                    model.draft.iconMode = $0; model.draft.saved = false
                })) {
                    Text("None").tag("off")
                    Text("Bot").tag("bot")
                    Text("Provider logo").tag("logo")
                }.pickerStyle(.menu).frame(maxWidth: .infinity, alignment: .leading)
            }
            VStack(alignment: .leading, spacing: 6) {
                Text("Providers").foregroundColor(Palette.bright)
                Text("Enable providers and set their order in the usage page.").font(.custom("GeistMono-Regular", size: 11))
                ForEach(model.draft.order, id: \.self) { provider in
                    HStack(spacing: 4) {
                        Toggle(isOn: Binding(get: { model.draft.enabled.contains(provider) }, set: { _ in model.toggleProvider(provider) })) {
                            HStack(spacing: 6) {
                                ProviderLogo(provider: model.logoProviderID(provider))
                                Text(model.providerName(provider))
                            }
                        }.toggleStyle(.checkbox)
                        Spacer(minLength: 0)
                        ControlButton(symbol: "arrow.up", help: "Move \(model.providerName(provider)) up",
                                      action: { model.moveProvider(provider, -1) }).disabled(model.draft.order.first == provider)
                        ControlButton(symbol: "arrow.down", help: "Move \(model.providerName(provider)) down",
                                      action: { model.moveProvider(provider, 1) }).disabled(model.draft.order.last == provider)
                    }.padding(.vertical, 3)
                }
            }
            if !model.settingsError.isEmpty || !model.settingsValid {
                Text(model.settingsError.isEmpty ? "Enable a provider and at least one bar text field, then choose a limit." : model.settingsError)
                    .font(.custom("GeistMono-Regular", size: 11)).foregroundColor(.orange)
            }
            HoverButton(bordered: true, action: model.showAbout) {
                HStack { Text("About AI Status"); Spacer(); Image(systemName: "arrow.right") }
            }
        }.disabled(model.settingsSaving)
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
                    Text("Available \(credits.available)").foregroundColor(Palette.bright).padding(12)
                    Divider()
                    HStack { Text("Reset type").frame(maxWidth: .infinity, alignment: .leading); Text("Expires").frame(maxWidth: .infinity, alignment: .leading) }
                        .font(.custom("GeistMono-Regular", size: 11)).padding(12)
                    ForEach(Array(credits.rows.enumerated()), id: \.offset) { _, row in
                        Divider()
                        HStack(alignment: .top, spacing: 12) {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(row.title).foregroundColor(Palette.bright)
                                Text("\(row.count) \(row.count == 1 ? "credit" : "credits")").font(.custom("GeistMono-Regular", size: 11))
                            }.frame(maxWidth: .infinity, alignment: .leading)
                            VStack(alignment: .leading, spacing: 5) {
                                Text(row.expires).foregroundColor(Palette.bright)
                                Text(row.remaining + (row.timezone.isEmpty ? "" : "\n" + row.timezone)).font(.custom("GeistMono-Regular", size: 11))
                            }.frame(maxWidth: .infinity, alignment: .leading)
                        }.padding(12)
                    }
                }.overlay(RoundedRectangle(cornerRadius: 8).stroke(Palette.border))
                if credits.undetailed > 0 { Text("Some reset details haven't been provided yet.").font(.custom("GeistMono-Regular", size: 11)) }
            } else { Text("No reset credits available.") }
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
                        Image(systemName: "arrow.right")
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
                        ControlButton(symbol: copiedCommand ? "checkmark" : "doc.on.doc",
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
                    HStack { Text("Release notes"); Spacer(); Image(systemName: "arrow.right") }
                }
                HoverButton(action: { open(guide.guideUrl) }) {
                    HStack { Text("Installation guide"); Spacer(); Image(systemName: "arrow.right") }
                }
            }
            Text("Updating is optional. You can return to usage and update later.")
                .font(.custom("GeistMono-Regular", size: 11))
        }
    }
}

struct AboutPage: View {
    let info: ProjectInfo
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            if let image = Assets.image() { Image(nsImage: image).resizable().scaledToFit().frame(width: 40, height: 40) }
            Text(info.name).font(.custom("GeistMono-Medium", size: 16)).foregroundColor(Palette.bright)
            Text(info.description)
            Text("Version: v\(info.version)\nCommit: \(info.commit)\nLicense: \(info.license)\nAuthor: \(info.author)")
                .font(.custom("GeistMono-Regular", size: 11))
            VStack(spacing: 6) {
                ForEach([(name: "GitHub", url: info.github), (name: "Documentation", url: info.documentation),
                         (name: "Report a bug", url: info.issues)], id: \.name) { link in
                    HoverButton(bordered: true, action: { if let url = URL(string: link.url), url.scheme == "https" { NSWorkspace.shared.open(url) } }) {
                        HStack { Text(link.name); Spacer(); Image(systemName: "arrow.right") }
                    }
                }
            }
            VStack(alignment: .leading, spacing: 10) {
                Text("Quick guide").foregroundColor(Palette.bright)
                Text("Menu bar: click to show usage; right-click for settings and other actions.")
                Text("Usage: click a limit to show it in the bar. Refresh checks now; Reset credits shows the available resets. Update available opens the update guide.")
                Text("Settings: pick a limit, text and icon. Enable providers and reorder them with the arrows. Save applies changes and keeps settings open.")
                Text("Keyboard: R refreshes, C opens settings, Esc goes back. Tab moves between controls.")
            }.font(.custom("GeistMono-Regular", size: 11))
        }
    }
}

struct PanelView: View {
    @ObservedObject var model: Model
    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                if model.page != .usage {
                    ControlButton(symbol: "arrow.left", help: model.page == .about ? "Back to settings (Esc)" : "Back to usage (Esc)", action: model.back)
                        .disabled(model.settingsSaving)
                        .padding(.trailing, 4)
                }
                Text(model.page == .about ? "About" : model.page == .settings ? "Settings" : model.page == .update ? "Update AI Status" : "AI Status").foregroundColor(Palette.bright)
                Spacer(minLength: 0)
                Text(model.snapshot.map { "v" + $0.version.current } ?? "").font(.custom("GeistMono-Regular", size: 11))
                if model.page != .settings && model.page != .about && model.page != .update {
                    ControlButton(symbol: "arrow.clockwise", help: "Refresh usage (R)",
                                  spinning: model.snapshot?.loading == true && model.isPresented, action: model.refresh)
                        .disabled(model.snapshot?.loading == true)
                    if model.page == .usage { ControlButton(symbol: "gearshape", help: "Configure (C)", action: model.showSettings) }
                }
            }.padding(.horizontal, 16).frame(height: 49)
            Divider().overlay(Palette.border)
            ScrollViewReader { scroll in
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        if !model.error.isEmpty { Text(model.error).font(.custom("GeistMono-Regular", size: 11)).foregroundColor(.orange) }
                        if model.page == .usage && model.snapshot?.version.hasUpdate == true {
                            HoverButton(hoverColor: Palette.update.opacity(0.10), action: model.showUpdate) {
                                HStack {
                                    Text("Update available: v" + (model.snapshot?.version.latest ?? ""))
                                    Spacer()
                                    Image(systemName: "arrow.right")
                                }.foregroundColor(Palette.update)
                            }.help("Show update instructions")
                        }
                        switch model.page {
                        case .usage: UsagePage(model: model)
                        case .settings: SettingsPage(model: model)
                        case .about: if let info = model.snapshot?.about { AboutPage(info: info) }
                        case .update: UpdatePage(model: model)
                        case .credits: if let provider = model.creditProvider { ResetCreditsPage(provider: provider) }
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 16).padding(.vertical, 18)
                        .id("page-top")
                }.onChange(of: model.page) { page in
                    if page == .update { scroll.scrollTo("page-top", anchor: .top) }
                }
            }
            if model.page == .settings {
                HStack(spacing: 8) {
                    Spacer()
                    if model.draft.saved { Text("Saved").font(.custom("GeistMono-Regular", size: 11)) }
                    Button("Cancel", action: model.back).buttonStyle(.plain).padding(6).disabled(model.settingsSaving)
                    Button(model.settingsSaving ? "Saving…" : "Save", action: model.saveSettings)
                        .buttonStyle(.plain).padding(6).overlay(RoundedRectangle(cornerRadius: 6).stroke(Palette.border))
                        .disabled(!model.settingsValid || model.settingsSaving)
                }.padding(.horizontal, 16).padding(.bottom, 12)
            }
        }
        .frame(width: 380).frame(maxHeight: .infinity)
        .font(Assets.font).foregroundColor(Palette.dim).background(Palette.surface)
        .preferredColorScheme(.dark)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSPopoverDelegate {
    private let model: Model
    private var statusItem: NSStatusItem!
    private let popover = NSPopover()
    private var keyMonitor: Any?
    private var signalSources: [DispatchSourceSignal] = []
    private var spinnerTimer: Timer?
    private var spinnerFrame = 0
    private let showSettingsOnLaunch: Bool

    init(runtime: RuntimeConfig, settings: Bool) {
        model = Model(runtime: runtime)
        showSettingsOnLaunch = settings
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
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
            if self.showSettingsOnLaunch && self.model.snapshot != nil && !self.didShowInitialSettings {
                self.didShowInitialSettings = true
                self.configure(nil)
            }
        }
        DistributedNotificationCenter.default().addObserver(self, selector: #selector(receiveCommand(_:)), name: commandNotification, object: nil)
        keyMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self = self else { return event }
            return self.handleKey(event)
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
    @objc private func about(_ sender: Any?) { model.showSettings(); model.showAbout(); show() }
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
        if model.page != .settings && model.page != .about && model.page != .update {
            switch event.charactersIgnoringModifiers?.lowercased() {
            case "r": model.refresh(); return nil
            case "c": configure(nil); return nil
            default: break
            }
        }
        return event
    }
    func popoverDidClose(_ notification: Notification) {
        model.isPresented = false
        if !model.settingsSaving { model.page = .usage }
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { openUsage(nil); return false }
    func applicationWillTerminate(_ notification: Notification) {
        spinnerTimer?.invalidate()
        if let monitor = keyMonitor { NSEvent.removeMonitor(monitor) }
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
         "resetCredits":{"available":3,"undetailed":0,"rows":[{"title":"5-hour + weekly reset","count":2,"expires":"Oct 15, 14:00","remaining":"5d left","timezone":"UTC+00:00"},
         {"title":"Weekly reset","count":1,"expires":"Oct 20, 14:00","remaining":"10d left","timezone":"UTC+00:00"}]}},
         {"id":"claude","idx":0,"name":"Claude (Max)","logoPath":"","loading":false,"cached":false,"error":"",
         "metrics":[{"key":"rolling","name":"Rolling Usage","percentage":9,"detail":"Resets in 34m"},
         {"key":"weekly","name":"Weekly Usage","percentage":46,"detail":"Resets in 3d 12h"},
         {"key":"weekly:Fable","name":"Weekly Usage","percentage":0,"detail":"Fable · Resets in 3d 12h"}],
         "resetCredits":{"available":1,"undetailed":0,"rows":[{"title":"Usage reset","count":1,"expires":"Oct 15, 14:00","remaining":"5d left","timezone":"UTC+00:00"}]}}],
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
        let model = Model()
        model.accept(Data(sample.utf8))
        guard let snapshot = model.snapshot, snapshot.providers.count == 2,
              model.selectedProvider?.providerID == "codex" else { throw AppError.message("Legacy snapshot decoding failed.") }
        guard !model.updateGuide.canUpdate, !model.updateGuide.command.isEmpty else {
            throw AppError.message("Legacy update guide fallback failed.")
        }
        model.showSettings()
        guard model.settingsValid, model.choices.count == 4 else { throw AppError.message("Settings model failed.") }
        model.draft.display["show_provider"] = false
        model.accept(Data(sample.utf8))
        guard model.draft.display["show_provider"] == false else { throw AppError.message("A refresh replaced the settings draft.") }
        let malformed = Data(sample.replacingOccurrences(of: "\"schemaVersion\":1", with: "\"schemaVersion\":2").utf8)
        model.accept(malformed)
        guard model.snapshot?.schemaVersion == 1 else { throw AppError.message("Invalid snapshot replaced usable data.") }
        try smokeAccounts(sample: sample, directory: previewDirectory)
        try smokeUpdate(sample: sample, directory: previewDirectory)
        model.isPresented = true
        let pages: [(String, Page)] = [("usage", .usage), ("settings", .settings),
                                      ("reset-credits", .credits(snapshot.providers[0].id)), ("about", .about)]
        for (name, page) in pages {
            model.page = page
            try renderSmokePage(model, name: name, directory: previewDirectory)
        }
        print("AI Status macOS smoke OK: usage, settings, reset credits, update guide, about, accounts, metered values, resources, snapshot validation")
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
            // Let SwiftUI mount once with animations disabled for deterministic fills.
            RunLoop.current.run(until: Date().addingTimeInterval(0.1))
            host.view.layoutSubtreeIfNeeded()
            host.view.displayIfNeeded()
            guard let bitmap = host.view.bitmapImageRepForCachingDisplay(in: host.view.bounds) else {
                throw AppError.message("Unable to render the \(name) preview.")
            }
            host.view.cacheDisplay(in: host.view.bounds, to: bitmap)
            guard let png = bitmap.representation(using: .png, properties: [:]) else {
                throw AppError.message("Unable to encode the \(name) preview.")
            }
            try png.write(to: directory.appendingPathComponent(name + ".png"), options: .atomic)
            window.close()
        }
    }
}
