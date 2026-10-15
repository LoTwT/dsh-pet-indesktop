"""Packaged AI window → Core notification / owner settings, through real Qt UI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from pet.ai_bindings import register_ai_pet_view
from pet.app import AppShell
from pet.config import Config
from pet.settings_mod_domain import close_extension_settings
from tests.ai_package_fakes import OWNER, MemoryVault, build_package, dispose_qobject

app = QApplication.instance() or QApplication([])


def pump(predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        loop = QEventLoop()
        QTimer.singleShot(10, loop.quit)
        loop.exec()
    assert predicate(), "Qt operation did not converge"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    return build_package(tmp_path_factory.mktemp("ai-callbacks") / "built")


@pytest.fixture
def installed(built, tmp_path, monkeypatch):
    vault = MemoryVault()
    monkeypatch.setattr("pet.credentials.secure_backend", lambda: vault)
    monkeypatch.setenv("PET_RENDER_TOPOLOGY", "legacy")
    quit_policy = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)  # Same policy as the production pet process.
    config = Config(base=tmp_path)
    config.set("settings_process_isolation", False)
    shell = AppShell(app, config, enable_chat=False)
    runtime = shell.feature_runtime
    manager = runtime.attach_official(OWNER)
    assert manager.submit("import_disabled", built, auto_apply=True)
    pump(lambda: not manager.busy)
    assert manager.submit("enable", True, expected_revision=manager.service.inspect().revision)
    pump(lambda: not manager.busy)
    mount = runtime.mounts.runtimes[OWNER]
    try:
        yield shell, manager, mount
    finally:
        dialog = shell.instance.modern_settings_dialog
        if dialog is not None:
            close_extension_settings(dialog)
            dialog.mod_host.shutdown()
            dialog.hide()
            dialog.deleteLater()
        for toast in tuple(shell._toast_windows):
            toast.close()
        dispose_qobject(mount)
        runtime.close()
        register_ai_pet_view(None)
        app.setQuitOnLastWindowClosed(quit_policy)


def click_settings_link(window, *, keyboard=False):
    label = window.provider_label
    assert 'href="api-settings"' in label.text(), label.text()
    if keyboard:
        window.activateWindow()
        pump(lambda: window.isActiveWindow())
        label.setFocus(Qt.FocusReason.TabFocusReason)
        assert label.hasFocus()
        QTest.keyClick(label, Qt.Key.Key_Tab)  # Select the label's link before activating it.
        QTest.keyClick(label, Qt.Key.Key_Return)
    else:
        QTest.mouseClick(label, Qt.MouseButton.LeftButton)


@pytest.mark.parametrize("keyboard", [False, True], ids=["mouse", "keyboard"])
def test_missing_key_opens_its_own_settings_and_preserves_input_and_drafts(installed, keyboard):
    shell, _manager, mount = installed
    before = json.dumps(shell.config.chat_settings().to_dict(), sort_keys=True)
    window = mount.chat()
    window.input.setPlainText("保留这条尚未发送的问题")
    messages = list(window.session.messages)
    window.send_message()
    assert window.input.toPlainText() == "保留这条尚未发送的问题"
    assert window.session.messages == messages
    assert not window.service.busy
    click_settings_link(window, keyboard=keyboard)
    pump(lambda: shell.instance.modern_settings_dialog is not None)
    dialog = shell.instance.modern_settings_dialog
    assert dialog.isVisible()
    assert dialog.sidebar.currentItem().text() == "扩展管理"
    panel = dialog.mod_panel
    assert panel.owner == OWNER
    key = panel.component.page.key
    assert key.isVisibleTo(dialog)
    key.setText("callback-test-secret")
    click_settings_link(window)
    assert dialog.mod_panel is panel
    assert key.text() == "callback-test-secret", "Repeated navigation discarded the draft"
    QTest.mouseClick(panel.save_button, Qt.MouseButton.LeftButton)
    assert not panel.dirty()
    provider = mount.runtime.config.chat_settings().active_config
    assert mount.runtime.config.resolve_provider_secret(provider) == "callback-test-secret"
    assert "callback-test-secret" not in (mount.runtime.config.dir / "configuration.json").read_text()
    assert json.dumps(shell.config.chat_settings().to_dict(), sort_keys=True) == before


@pytest.mark.parametrize("state", ["enabled", "disabled", "closed"])
def test_authentication_notification_routes_to_owner_settings_only_while_live(installed, state):
    shell, manager, mount = installed
    received = threading.Event()

    class Unauthorized(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = b'{"error":{"message":"invalid API key"}}'
            self.send_response(401)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            received.set()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Unauthorized)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        config = mount.runtime.config
        settings = config.chat_settings()
        provider = settings.active_config
        provider.base_url = f"http://127.0.0.1:{server.server_port}"
        provider.api_key_ref = config.save_provider_secret(provider, "test-only-key")
        config.set_chat_settings(settings)
        config.save()
        window = mount.chat()
        background = QWidget()
        background.show()
        background.activateWindow()
        pump(lambda: background.isActiveWindow())
        window.hide()
        window.input.setPlainText("exercise the local 401 endpoint")
        window.send_message()
        pump(received.is_set)
        pump(lambda: window.service.is_drained)
        assert shell._toast_windows, "The package did not reach the Core notifier"
        toast = shell._toast_windows[-1]
        assert toast.isVisible()
        if state == "disabled":
            assert manager.submit("enable", False, expected_revision=manager.service.inspect().revision)
            pump(lambda: not manager.busy)
        elif state == "closed":
            mount.close()
        QTest.mouseClick(toast, Qt.MouseButton.LeftButton)
        if state == "enabled":
            pump(lambda: shell.instance.modern_settings_dialog is not None)
            assert shell.instance.modern_settings_dialog.mod_panel.owner == OWNER
        else:
            assert shell.instance.modern_settings_dialog is None
            assert not window.isVisible()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=10)
        assert not worker.is_alive()


def test_settings_process_cold_start_selects_the_ai_owner_without_importing_pet_app(installed, tmp_path):
    script = textwrap.dedent('''
        import sys, traceback
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from pet.__main__ import _exec_settings
        from pet.config import Config
        app = QApplication([])
        def inspect():
            try:
                dialog = next(w for w in app.topLevelWidgets() if hasattr(w, "mod_panel_owner"))
                assert dialog.mod_panel_owner == "official.ai-chat", dialog.mod_panel_owner
                assert dialog.mod_panel.component.page.key.isVisibleTo(dialog)
                assert "pet.app" not in sys.modules
                print("owner settings visible; pet.app not imported", flush=True)
                app.exit(0)
            except Exception:
                traceback.print_exc()
                app.exit(1)
        QTimer.singleShot(0, inspect)
        raise SystemExit(_exec_settings(app, Config(base=sys.argv[1]), include_ai=False,
                                      initial_page="extension:official.ai-chat"))
    ''')
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)],
                            env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "owner settings visible" in result.stdout
