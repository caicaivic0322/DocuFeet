import AppKit
import Foundation
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var backendProcess: Process?
    private var frontendProcess: Process?
    private var logHandles: [FileHandle] = []

    func applicationDidFinishLaunching(_ notification: Notification) {
        let repoRoot = readRepoRoot()
        startServices(repoRoot: repoRoot)
        showWindow()

        DispatchQueue.main.asyncAfter(deadline: .now() + 2.2) { [weak self] in
            self?.loadApp()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        backendProcess?.terminate()
        frontendProcess?.terminate()
        logHandles.forEach { $0.closeFile() }
    }

    private func readRepoRoot() -> URL {
        guard
            let resourceURL = Bundle.main.resourceURL,
            let contents = try? String(
                contentsOf: resourceURL.appendingPathComponent("repo-root.txt"),
                encoding: .utf8
            )
        else {
            return URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        }

        return URL(fileURLWithPath: contents.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    private func showWindow() {
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true

        let webView = WKWebView(frame: .zero, configuration: configuration)
        self.webView = webView

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1280, height: 860),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.center()
        window.title = "赤脚医生"
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        self.window = window
    }

    private func loadApp() {
        guard let url = URL(string: "http://127.0.0.1:5173/") else {
            return
        }
        webView?.load(URLRequest(url: url))
    }

    private func startServices(repoRoot: URL) {
        if !isPortListening(8001) {
            backendProcess = launch(
                executable: URL(fileURLWithPath: "/usr/bin/env"),
                arguments: [
                    "bash",
                    "-lc",
                    "source .venv/bin/activate && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001",
                ],
                workingDirectory: repoRoot.appendingPathComponent("backend"),
                logName: "docufeet-backend.log"
            )
        }

        if !isPortListening(5173) {
            frontendProcess = launch(
                executable: URL(fileURLWithPath: "/usr/bin/env"),
                arguments: [
                    "bash",
                    "-lc",
                    "npm run preview -- --host 127.0.0.1 --port 5173",
                ],
                workingDirectory: repoRoot.appendingPathComponent("frontend"),
                logName: "docufeet-frontend.log"
            )
        }
    }

    private func launch(
        executable: URL,
        arguments: [String],
        workingDirectory: URL,
        logName: String
    ) -> Process? {
        let process = Process()
        process.executableURL = executable
        process.arguments = arguments
        process.currentDirectoryURL = workingDirectory
        process.environment = [
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": NSHomeDirectory(),
        ]

        if let logHandle = openLogHandle(name: logName) {
            process.standardOutput = logHandle
            process.standardError = logHandle
            logHandles.append(logHandle)
        }

        do {
            try process.run()
            return process
        } catch {
            NSLog("Failed to launch %@: %@", arguments.joined(separator: " "), "\(error)")
            return nil
        }
    }

    private func openLogHandle(name: String) -> FileHandle? {
        let url = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent(name)
        FileManager.default.createFile(atPath: url.path, contents: nil)
        return try? FileHandle(forWritingTo: url)
    }

    private func isPortListening(_ port: Int32) -> Bool {
        let process = Process()
        let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        process.arguments = ["-tiTCP:\(port)", "-sTCP:LISTEN"]
        process.standardOutput = pipe
        process.standardError = Pipe()

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return false
        }

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        return !data.isEmpty
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.activate(ignoringOtherApps: true)
app.run()
