import AppKit
import Foundation
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var backendProcess: Process?
    private var logHandles: [FileHandle] = []

    func applicationDidFinishLaunching(_ notification: Notification) {
        let repoRoot = readRepoRoot()
        startServices(repoRoot: repoRoot)
        showWindow()
        showBootScreen(message: "正在启动本地医疗助手服务...")
        waitForBackend(remainingAttempts: 45)
    }

    func applicationWillTerminate(_ notification: Notification) {
        backendProcess?.terminate()
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
        let windowRect = NSRect(x: 0, y: 0, width: 1280, height: 860)
        let window = NSWindow(
            contentRect: windowRect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )

        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true

        let webView = WKWebView(frame: window.contentView?.bounds ?? windowRect, configuration: configuration)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        self.webView = webView

        window.center()
        window.title = "赤脚医生"
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        self.window = window
    }

    private func loadApp() {
        guard let url = URL(string: "http://127.0.0.1:8001/app/") else {
            showBootScreen(message: "本地前端地址无效。")
            return
        }
        webView?.load(URLRequest(url: url))
    }

    private func waitForBackend(remainingAttempts: Int) {
        guard remainingAttempts > 0 else {
            showBootScreen(
                message: "后端服务启动超时。请检查 /tmp/docufeet-backend.log。"
            )
            return
        }

        guard let url = URL(string: "http://127.0.0.1:8001/api/health") else {
            showBootScreen(message: "本地后端地址无效。")
            return
        }

        var request = URLRequest(url: url)
        request.timeoutInterval = 1.0
        URLSession.shared.dataTask(with: request) { [weak self] _, response, _ in
            DispatchQueue.main.async {
                if let httpResponse = response as? HTTPURLResponse,
                   (200..<500).contains(httpResponse.statusCode) {
                    self?.loadApp()
                    return
                }

                self?.showBootScreen(message: "正在等待后端服务启动...")
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                    self?.waitForBackend(remainingAttempts: remainingAttempts - 1)
                }
            }
        }.resume()
    }

    private func showBootScreen(message: String) {
        let html = """
        <!doctype html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8">
          <style>
            body {
              margin: 0;
              min-height: 100vh;
              display: grid;
              place-items: center;
              font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
              color: #182021;
              background:
                radial-gradient(circle at 20% 10%, rgba(31, 107, 85, .18), transparent 32%),
                linear-gradient(135deg, #edf1ef, #f8faf7);
            }
            main {
              width: min(520px, calc(100vw - 48px));
              padding: 30px;
              border: 1px solid #d8dfdc;
              border-radius: 28px;
              background: rgba(251, 252, 250, .94);
              box-shadow: 0 18px 48px rgba(24, 32, 33, .08);
            }
            h1 { margin: 0 0 12px; font-size: 28px; }
            p { margin: 0; color: #657071; line-height: 1.7; }
          </style>
        </head>
        <body>
          <main>
            <h1>赤脚医生</h1>
            <p>\(message)</p>
          </main>
        </body>
        </html>
        """
        webView?.loadHTMLString(html, baseURL: nil)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        showBootScreen(message: "页面加载失败：\(error.localizedDescription)")
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        showBootScreen(message: "页面加载失败：\(error.localizedDescription)")
    }

    private func startServices(repoRoot: URL) {
        if !isPortListening(8001) {
            let webDistPath = Bundle.main.resourceURL?
                .appendingPathComponent("web", isDirectory: true)
                .standardizedFileURL
                .path
            backendProcess = launch(
                executable: URL(fileURLWithPath: "/usr/bin/env"),
                arguments: [
                    "bash",
                    "-lc",
                    "source .venv/bin/activate && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001",
                ],
                workingDirectory: repoRoot.appendingPathComponent("backend"),
                logName: "docufeet-backend.log",
                extraEnvironment: webDistPath.map { ["DOCUFEET_WEB_DIST": $0] } ?? [:]
            )
        }

    }

    private func launch(
        executable: URL,
        arguments: [String],
        workingDirectory: URL,
        logName: String,
        extraEnvironment: [String: String] = [:]
    ) -> Process? {
        let process = Process()
        process.executableURL = executable
        process.arguments = arguments
        process.currentDirectoryURL = workingDirectory
        var environment = [
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": NSHomeDirectory(),
        ]
        extraEnvironment.forEach { environment[$0.key] = $0.value }
        process.environment = environment

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
