// UpdateCheck.swift — drop into any ad hoc (install.html) app.
//
// Sideloaded builds never update on their own: iOS does not check, and neither does TestFlight
// (blocked by the billing hold). This asks the app's own GitHub Pages install site what build is
// published, and if it is newer than CFBundleVersion, shows a banner whose button opens the
// itms-services link. iOS installs over the top (same bundle id), data is kept.
//
// Use:   .updateCheck(site: "https://assiamahs.github.io/<repo>")   on the root view.
// Reads  <site>/ipa/version.json  {"build":123,"version":"1.2"}  when CI writes it (newer lanes),
// else   <site>/install.html      and finds "Build 123" in the page (every existing lane).

import SwiftUI

struct PublishedBuild: Decodable { let build: Int; let version: String? }

@MainActor
final class UpdateChecker: ObservableObject {
    @Published var available: PublishedBuild?
    let site: String
    init(site: String) { self.site = site }

    var installURL: URL { URL(string: "itms-services://?action=download-manifest&url=\(site)/ipa/manifest.plist")! }
    var currentBuild: Int { Int(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "") ?? 0 }

    func check() async {
        guard let latest = await fetchLatest(), latest.build > currentBuild else { return }
        available = latest
    }

    private func fetchLatest() async -> PublishedBuild? {
        var req = URLRequest(url: URL(string: "\(site)/ipa/version.json")!)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        if let (data, resp) = try? await URLSession.shared.data(for: req),
           (resp as? HTTPURLResponse)?.statusCode == 200,
           let v = try? JSONDecoder().decode(PublishedBuild.self, from: data) { return v }
        // Fallback: the install page stamps "Build N (vX) · date".
        var page = URLRequest(url: URL(string: "\(site)/install.html")!)
        page.cachePolicy = .reloadIgnoringLocalCacheData
        guard let (data, _) = try? await URLSession.shared.data(for: page),
              let html = String(data: data, encoding: .utf8),
              let m = html.firstMatch(of: #/Build (\d+)(?: \(v([\d.]+)\))?/#) else { return nil }
        return PublishedBuild(build: Int(m.1) ?? 0, version: m.2.map(String.init))
    }
}

struct UpdateBanner: ViewModifier {
    @StateObject private var checker: UpdateChecker
    @Environment(\.openURL) private var openURL
    @Environment(\.scenePhase) private var phase
    init(site: String) { _checker = StateObject(wrappedValue: UpdateChecker(site: site)) }

    func body(content: Content) -> some View {
        content
            .safeAreaInset(edge: .top) {
                if let b = checker.available {
                    HStack(spacing: 12) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Update available").font(.headline)
                            Text("Build \(b.build)\(b.version.map { " · v\($0)" } ?? "") · you have \(checker.currentBuild)")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("Install") { openURL(checker.installURL) }.buttonStyle(.borderedProminent)
                        Button { checker.available = nil } label: { Image(systemName: "xmark") }.buttonStyle(.plain)
                    }
                    .padding(12)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14))
                    .padding(.horizontal, 12)
                    .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
            .task { await checker.check() }
            .onChange(of: phase) { _, p in if p == .active { Task { await checker.check() } } }
            .animation(.snappy, value: checker.available?.build)
    }
}

extension View {
    /// Shows an "Update available → Install" banner when the Pages install site has a newer build.
    func updateCheck(site: String) -> some View { modifier(UpdateBanner(site: site)) }
}
