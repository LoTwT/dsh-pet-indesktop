# DLC AI 包窗口通知与设置回调

> 基线：`f824289e8facb725f552b1b2168bf3400b38e9c8`（`upstream/dlc/mod-center-port`）。
> 分支：`dlc/ai-runtime-callbacks`。日期：2026-10-15。
> 范围：[交接文档 §6.2 第 1 项](DLC-HANDOFF-2026-10-15.md#62-小包接线三件同源后续片可一起做建议作为上手第一批)。
> 状态：实现与证据完成；最终全量 8494 passed / 20 failed / 73 skipped，全部失败均见于基线，未满足默认发布门。没有合并上游的授权。

## 一、核心特性

AI 扩展未保存 Key 时，发送前保留输入和会话，在原状态标签显示「打开 API 设置」。
鼠标或键盘可进入 `official.ai-chat` 自己的设置面板。后台请求认证失败时使用 Core
现有桌面通知；点击进入同一面板。停用、卸载或关闭运行时后，旧通知不能重新开窗。

重复导航保留当前面板及未保存草稿。设置进程使用全局配置身份创建扩展宿主，避免
从槽位页保存的凭据引用被进程级 AI 运行时以 `scope_denied` 拒绝。
内置 `pet/chat/`、内置 `open_chat*` 和内置配置/凭据不变；不新增持久设置。
本次没有涉及包 UI 整体对齐、文件解读、官方包安装按钮或 5A 的方向决策。

## 二、修改文件说明

基于 `git diff --numstat f824289e8facb725f552b1b2168bf3400b38e9c8`；新增文件另列。

| 文件 | 增删 | 修改及原因 |
|---|---|---|
| `features/ai-chat/host/runtime_mount.py` | +37 / −1 | 惰性取 Core 回调，传给 `AiRuntime.create_window`；派发与通知点击均检查包生命周期。 |
| `features/ai-chat/host/chat/request_config.py` | +3 / −1 | 仅可通过设置恢复的配置错误可产生本地链接，其他错误保留原因。 |
| `features/ai-chat/host/chat/widgets.py` | +8 / −2 | 包内现代窗口的鼠标/键盘链接、原错误 tooltip、停用守卫。 |
| `features/ai-chat/host/chat/legacy_widgets.py` | +8 / −2 | 包内经典窗口遵守同一回调契约。 |
| `pet/ai_bindings.py` | +15 / −8 | 呈现提供方同时注册/清除两条窄回调；不添加 API 凭据端口。 |
| `pet/app.py` | +7 / −1 | 仅在 DLC 装配处注册通知和固定 AI owner 导航。 |
| `pet/modern_settings_dialog.py` | +2 / −0 | 两行 `extension:<owner>` 分派，复用现有独立设置进程参数。 |
| `pet/settings_mod_domain.py` | +34 / −2 | owner 深链接、草稿门、面板可见性、一次布局后的滚动；独立设置宿主使用现有全局配置视图。 |
| `tests/test_ai_window_callbacks.py`（新增） | +210 / −0 | 真打包、真 Qt、真实本地 HTTP 401、独立子进程的 6 项回归；只替换系统凭据边界。 |
| `tests/test_mod_center_end_to_end.py` | +2 / −0 | 原装配测试桩补上新增的真实回调方法。 |
| `tests/test_architecture.py` | +2 / −1 | 主设置文件仅新增两行 DLC 分派，按规范将实测行数预算 2413 校准到 2415。 |
| 本报告（新增） | +382 / −0 | 逐文件、性能、实机、测试与复现探针。 |
| `docs/INDEX.md` | +1 / −0 | 登记本报告及必读场景。 |
| `docs/modding/PORT-STATUS.md` | +13 / −1 | 保留第四片历史边界，在 §十记录接线事实和验收状态。 |
| `docs/screenshots/ai-window-callbacks-2026-10-15/missing-key.png`（新增） | 二进制 `- / -`；109,008 B | 原始 Cocoa 聊天入口截图。 |
| `docs/screenshots/ai-window-callbacks-2026-10-15/settings.png`（新增） | 二进制 `- / -`；160,528 B | 原始 Cocoa owner 设置页截图。 |

没有删除文件。未修改 requirements、构建、内置聊天或已知生命周期 flake。

## 三、实现要点与边界

回调在每次开窗/操作时惰性解析；未注册时维持无通知的独立包宿主形态。
`register_ai_pet_view(None)` 同时清掉回调引用，沿用既有退出收口。
通知回调检查 `AiPackageRuntime` 与 `AiRuntime.accepting`，不引入线程或常驻计时器。
设置页只增加 `extension:` 路由；正常侧栏标题选择保持原路径。
切换到其他 owner 前复用保存/放弃/取消草稿门，同一 owner 不重建面板。

默认独立设置进程的冷启动已覆盖。若另一个独立设置窗口已经打开，仍沿用 Core
现有的单实例提示，由用户切换到该窗口；本次没有新增跨进程导航通道。
`FeatureHostContext.api` 仍为 `None`；包与内置聊天的配置、会话、凭据作用域独立。

## 四、性能分析

环境：macOS 27.0.1 arm64，10 个逻辑核，Python 3.13.7，PySide6 6.11.2。
在相同 Core 下分别装载改动前保存的真实包和当前真实包；测量时未运行 CPU 负载。
`perf_probe.py` 完整内容在附录。基线包由改动前 `build_package` 构建，源码 SHA 如页首。

```sh
QT_QPA_PLATFORM=offscreen PET_RENDER_TOPOLOGY=legacy .venv/bin/python .scratch/dlc-ai-runtime-callbacks/perf_probe.py base
QT_QPA_PLATFORM=offscreen PET_RENDER_TOPOLOGY=legacy .venv/bin/python .scratch/dlc-ai-runtime-callbacks/perf_probe.py current
```

| 路径 / 样本 | 基线 | 本次 |
|---|---:|---:|
| 首次聊天窗口，n=1，含模块/字体初始化 | 456.01 ms | 523.98 ms |
| 缺 Key 发送，n=300，中位 / P95 | 3.2793 / 3.7715 ms | 3.2861 / 4.2761 ms |
| 未开设置的静置采样：CPU 时间 / 墙钟 | 0.005977 / 5.0602 s | 0.004409 / 4.7503 s |
| 首开扩展设置，n=1 | 无此跳转 | 731.25 ms |
| 重复跳转，n=100，中位 / P95 | 无此跳转 | 2.7225 / 3.9654 ms |
| 已热身后再跳转 500 次，开启 tracemalloc | — | Python 保留量 +14,416 B；RSS +98,304 B |
| 600 次跳转后面板身份 | — | 同一对象 |
| OS 线程数：开设置前 / 重复跳转后 | 7 / — | 7 / 6 |

稳态静置 CPU 折合单核约 0.118% / 0.093%，是一次短采样，不能据此声称提速。
缺 Key 路径中位增加 0.0068 ms；P95 有波动。冷启动各只有一次样本，也不能推断
稳定的启动差异。首次设置导航是用户点击触发，复用既有设置窗口构造和配置读取；
它仍有约 731 ms 的首开成本，不应描述成零开销。

代码路径审计：回调注册/查询只有进程内引用操作。首次设置导航会触发已有配置
读取和窗口系统调用；默认隔离开关下还会启动一个既有类型的设置子进程。保存 Key
使用既有钥匙串操作，通知使用已有窗口绘制；无额外常驻轮询或网络请求，缺 Key
发送也未启动请求。新增滚动只排一次 Qt 零延时回调，线程实测没有增长。
首次打开设置后的 RSS 为 231,374,848 B，未打开
设置的基线为 162,856,960 B，包含既有设置模块、字体和控件缓存，不能归因于两条
回调本身；500 次重复跳转的增量已单列，未声称长期零增长。

## 五、实机运行记录

2026-10-15，在本机 Cocoa 平台运行真实包安装/启用/窗口/设置/停用路径，临时配置
与用户配置隔离。使用真实 AppShell 装配包窗口，未启动动画/托盘子系统。
该探针没有 mock；未填写或发送真实服务商 Key。完整探针见附录。

```sh
QT_QPA_PLATFORM=cocoa PET_RENDER_TOPOLOGY=legacy .venv/bin/python .scratch/dlc-ai-runtime-callbacks/native_probe.py base
QT_QPA_PLATFORM=cocoa PET_RENDER_TOPOLOGY=legacy .venv/bin/python .scratch/dlc-ai-runtime-callbacks/native_probe.py current
```

基线真实输出：`platform=cocoa`、`window_visible=true`、
`hint=尚未保存 API Key，请打开 API 设置。`、`request_started=false`，没有链接。
本次真实输出节选：

```json
{
  "platform": "cocoa",
  "hint": "<a href=\"api-settings\">打开 API 设置</a>",
  "input_retained": "没有保存 Key，这条消息应保留。",
  "request_started": false,
  "owner": "official.ai-chat",
  "key_visible": true,
  "key_inside_viewport": true,
  "credentials_scope_matches": true,
  "draft_retained": true,
  "notification_visible": true,
  "late_click_stayed_closed": true
}
```

Agent 实际检查了 [聊天入口截图](screenshots/ai-window-callbacks-2026-10-15/missing-key.png)
与 [扩展设置截图](screenshots/ai-window-callbacks-2026-10-15/settings.png)：链接完整可读、
原消息保留、Key 输入框落在当前视口。通知使用包的公开授权提示入口；HTTP 401 到
通知的整条网络链另由真实 loopback HTTP 服务回归测试覆盖，凭据后端在该测试中为内存替身。
失败边界实机验证为停用后点击旧通知，包窗口保持关闭。

Qt 日志仍出现原有 `_WrappingActionButton` 的负最小尺寸警告和 macOS IMK mach
port 日志；窗口及所有探针断言通过。Windows/Linux 的原生窗口行为本机不能实测
（`sys.platform=darwin`，Qt 平台为 `cocoa`）；没有声明已验证跨平台截图或真实模型回复。
没有新增设置键、默认值、迁移、重置语义或搜索行；本次相关设置门为导航、草稿、
凭据隔离与可见性。UI 整体对齐仍属于后续决策。

## 六、测试与验证

| 门 | 命令 / 选择 | 结果 |
|---|---|---|
| 初始全量 | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -p no:randomly` | 8480 passed / 26 failed / 73 skipped，1238.88 s |
| 基线隔离复跑 | 同命令指定 26 个失败 node，进程内设置规范化 `TMPDIR` | 9 passed / 17 failed，4.64 s |
| test-first | 符号选择 `test_missing_key_opens_its_own_settings\|test_authentication_notification_routes\|test_settings_process_cold_start_selects` | 原产品 6 failed，6.69 s；后续聚焦中全部通过 |
| 相关族 | `rg -l 'AiRuntime\|AiPackageRuntime\|ai_bindings\|settings_mod_domain\|OwnerSettingsPanel\|select_page' tests -g 'test_*.py'`，排序后运行 | 360 passed / 2 failed，121.85 s；旧 Shell 桩补齐后在最终全量中通过，另一条为基线 screen menu 失败 |
| ruff | `.venv/bin/python -m ruff check pet tests scripts` 加本次 4 个包内 Python 文件 | 通过 |
| 受影响时序族满载 3 遍 | `rg -l 'AiRuntime\|AiPackageRuntime\|ai_bindings' tests -g 'test_*.py'`，10 个 CPU 负载进程 | 每轮 74 passed，17.15 / 17.14 / 18.03 s；107 个 CPU 样本平均 94.89%，峰值 100% |
| 最终全量 | 规范化 `TMPDIR` 后完整 pytest，不跳过既有失败 | 8494 passed / 20 failed / 73 skipped，1236.58 s；失败集合是原基线的子集，没有新增失败 |

基线额外失败的定位证据：默认 macOS 临时目录 `/var/folders/...` 被 `safe_path`
拒绝；解析为 `/private/var/folders/...` 则通过，6 条相关用例恢复。已知 3 条
workers lifecycle flake 隔离复跑通过，未修改。剩余 17 条包括：

- `test_frozen_runtime_paths.py` 5 条：把 `sys.platform` 设成 Windows 后仍传 POSIX
  临时路径，被 Windows 本机盘符校验以 `frozen_runtime_layout` 拒绝。
- `test_proactive_worker_adapter.py` 9 条：macOS 实际没有 `msvcrt` 模块。
- `test_workers_lifecycle.py::test_destroying_a_running_supervisor_kills_the_child_without_stderr_tracebacks`：子进程调用不存在的 `tasklist`。
- `test_island_bevel_fade.py::test_sample_value_change_never_fades`：取样 36，断言至少 60。
- `test_screen_package_e2e.py::test_enable_mounts_the_screen_menus_and_manual_look_runs`：预期的主动识屏子菜单为 None。

这些失败已在修改产品代码前观察并隔离复现。本任务没有修它们，也没有删测试、
添加 skip 或伪称全量通过。最终全量再次出现上述 17 条及原有 3 条生命周期 flake；
原定“全量必过”的发布门尚未满足，推送和 PR 需要用户明确接受本次基线例外。

## 七、风险与回滚

变化集中在 DLC 呈现回调和扩展设置装配；没有新数据格式。回滚该提交恢复无跳转
入口的旧行为，已由扩展设置保存的数据仍使用既有格式。已打开的独立设置进程
维持原单实例限制。已有错误槽位作用域的凭据引用不会自动迁移；若遇到此类引用，
需在扩展设置重新保存 Key，旧钥匙串条目不会被擅自删除。
既有全量失败的发布处理须由用户/维护者明确决定。

导航：[PORT-STATUS](modding/PORT-STATUS.md) · [全文档索引](INDEX.md)

## 附录：本次临时验收探针

将下列代码分别保存为报告命令所示的临时文件。探针未接入构建或 CI。

在新的临时目录重建基线包（当前包由探针直接构建）：

```sh
mkdir -p .scratch/dlc-ai-runtime-callbacks/base-source
git archive f824289e8facb725f552b1b2168bf3400b38e9c8 features/ai-chat | tar -x -C .scratch/dlc-ai-runtime-callbacks/base-source
.venv/bin/python - <<'PY'
from pathlib import Path
from scripts.build_ai_chat_package import build_package
root = Path('.scratch/dlc-ai-runtime-callbacks').resolve()
build_package(root / 'base-source/features/ai-chat', root / 'base-package')
PY
```

<details>
<summary>native_probe.py</summary>

```python
from pathlib import Path
import json
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget
from pet.app import AppShell
from pet.config import Config
from tests.ai_package_fakes import OWNER, build_package, dispose_qobject
from pet.settings_mod_domain import close_extension_settings

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
stage = sys.argv[1] if len(sys.argv) > 1 else "current"
out = ROOT / ".scratch/dlc-ai-runtime-callbacks"

def pump(check, timeout=30):
    deadline = time.monotonic() + timeout
    while not check() and time.monotonic() < deadline:
        loop = QEventLoop()
        QTimer.singleShot(10, loop.quit)
        loop.exec()
    assert check()

with tempfile.TemporaryDirectory(prefix="native-", dir=out) as data:
    cfg = Config(base=Path(data).resolve())
    cfg.set("settings_process_isolation", False)
    shell = AppShell(app, cfg, enable_chat=False)
    manager = shell.feature_runtime.attach_official(OWNER)
    package = out / "base-package" if stage == "base" else build_package(Path(data) / "built")
    assert manager.submit("import_disabled", package, auto_apply=True)
    pump(lambda: not manager.busy)
    assert manager.submit("enable", True, expected_revision=manager.service.inspect().revision)
    pump(lambda: not manager.busy)
    mount = shell.feature_runtime.mounts.runtimes[OWNER]
    window = mount.chat()
    window.input.setPlainText("没有保存 Key，这条消息应保留。")
    window.send_message()
    window.activateWindow()
    pump(window.isActiveWindow)
    app.processEvents()
    window.grab().save(str(out / f"native-{stage}-missing-key.png"))
    result = {"platform": app.platformName(), "stage": stage,
              "window_visible": window.isVisible(), "hint": window.provider_label.text(),
              "input_retained": window.input.toPlainText(), "request_started": window.service.busy}
    if stage != "base":
        QTest.mouseClick(window.provider_label, Qt.MouseButton.LeftButton)
        pump(lambda: shell.instance.modern_settings_dialog is not None)
        dialog = shell.instance.modern_settings_dialog
        pump(dialog.isVisible)
        app.processEvents()
        panel = dialog.mod_panel
        key = panel.component.page.key
        scroll = dialog.pages.currentWidget().findChild(QScrollArea, "settingsScroll")
        from PySide6.QtCore import QPoint, QRect
        in_view = QRect(key.mapTo(scroll.viewport(), QPoint()), key.size())
        result.update(owner=panel.owner, key_visible=key.isVisibleTo(dialog),
                      key_inside_viewport=scroll.viewport().rect().contains(in_view),
                      credentials_scope_matches=panel.component.config.context.credentials.scope == mount.runtime.config.context.credentials.scope)
        dialog.grab().save(str(out / "native-current-settings.png"))
        key.setText("unsaved-native-draft")
        QTest.mouseClick(window.provider_label, Qt.MouseButton.LeftButton)
        result["draft_retained"] = dialog.mod_panel is panel and key.text() == "unsaved-native-draft"
        panel.discard_changes()
        close_extension_settings(dialog)
        dialog.mod_host.shutdown()
        dialog.hide()
        dialog.deleteLater()
        shell.instance.modern_settings_dialog = None
        background = QWidget()
        background.show()
        background.activateWindow()
        pump(background.isActiveWindow)
        window.hide()
        window.notify_authorization_required("本机 DLC 通知验收：点击返回包窗口。")
        pump(lambda: bool(shell._toast_windows))
        toast = shell._toast_windows[-1]
        toast.grab().save(str(out / "native-current-notification.png"))
        result["notification_visible"] = toast.isVisible()
        assert manager.submit("enable", False, expected_revision=manager.service.inspect().revision)
        pump(lambda: not manager.busy)
        QTest.mouseClick(toast, Qt.MouseButton.LeftButton)
        result["late_click_stayed_closed"] = not window.isVisible() and shell.instance.modern_settings_dialog is None
        background.close()
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    dispose_qobject(mount)
    shell.feature_runtime.close()
    AppShell._shutdown_live_for_tests()
    app.processEvents()

```

</details>

<details>
<summary>perf_probe.py</summary>

```python
from pathlib import Path
import gc
import json
import statistics
import sys
import tempfile
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import psutil
from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from pet.app import AppShell
from pet.config import Config
from tests.ai_package_fakes import OWNER, build_package, dispose_qobject
from pet.settings_mod_domain import close_extension_settings

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
stage = sys.argv[1]
out = ROOT / ".scratch/dlc-ai-runtime-callbacks"
process = psutil.Process()

def pump(check, timeout=30):
    deadline=time.monotonic()+timeout
    while not check() and time.monotonic()<deadline:
        loop=QEventLoop();QTimer.singleShot(10,loop.quit);loop.exec()
    assert check()

def measure(fn,n):
    values=[]
    for _ in range(n):
        start=time.perf_counter_ns();fn();values.append((time.perf_counter_ns()-start)/1e6)
    return {"n":n,"median_ms":round(statistics.median(values),4),"p95_ms":round(sorted(values)[int(n*.95)-1],4)}

with tempfile.TemporaryDirectory(prefix="perf-",dir=out) as data:
    config=Config(base=Path(data).resolve());config.set("settings_process_isolation",False)
    shell=AppShell(app,config,enable_chat=False)
    manager=shell.feature_runtime.attach_official(OWNER)
    package=out/"base-package" if stage=="base" else build_package(Path(data)/"built")
    assert manager.submit("import_disabled",package,auto_apply=True);pump(lambda:not manager.busy)
    assert manager.submit("enable",True,expected_revision=manager.service.inspect().revision);pump(lambda:not manager.busy)
    mount=shell.feature_runtime.mounts.runtimes[OWNER]
    result={"stage":stage,"platform":app.platformName()}
    start=time.perf_counter_ns();window=mount.chat();app.processEvents()
    result["first_window_ms"]=(time.perf_counter_ns()-start)/1e6
    window.input.setPlainText("missing key performance probe")
    window.send_message()
    result["missing_key"]=measure(window.send_message,300)
    result["threads_before_settings"]=process.num_threads()
    loop=QEventLoop();QTimer.singleShot(5000,loop.quit)
    start_wall=time.monotonic();start_cpu=time.process_time();loop.exec()
    result["idle_before_settings_wall_s"]=time.monotonic()-start_wall
    result["idle_before_settings_cpu_s"]=time.process_time()-start_cpu
    if stage!="base":
        def open_settings():
            QTest.mouseClick(window.provider_label,Qt.MouseButton.LeftButton);app.processEvents()
        start=time.perf_counter_ns();open_settings()
        result["first_settings_ms"]=(time.perf_counter_ns()-start)/1e6
        dialog=shell.instance.modern_settings_dialog
        assert dialog.mod_panel.owner==OWNER
        result["repeated_settings"]=measure(open_settings,100)
        panel=dialog.mod_panel
        tracemalloc.start();gc.collect()
        before_py=tracemalloc.get_traced_memory()[0];before_rss=process.memory_info().rss
        result["repeated_settings_memory_batch"]=measure(open_settings,500)
        gc.collect()
        result["python_retained_delta_bytes"]=tracemalloc.get_traced_memory()[0]-before_py
        result["rss_delta_bytes"]=process.memory_info().rss-before_rss
        result["same_panel_after_600_clicks"]=dialog.mod_panel is panel
        result["threads_after_settings"]=process.num_threads()
        tracemalloc.stop()
        close_extension_settings(dialog);dialog.mod_host.shutdown();dialog.hide();dialog.deleteLater()
        shell.instance.modern_settings_dialog=None
    loop=QEventLoop();QTimer.singleShot(5000,loop.quit)
    start_wall=time.monotonic();start_cpu=time.process_time();loop.exec()
    result["idle_wall_s"]=time.monotonic()-start_wall
    result["idle_cpu_s"]=time.process_time()-start_cpu
    result["rss_end_bytes"]=process.memory_info().rss
    print(json.dumps(result,indent=2),flush=True)
    dispose_qobject(mount);shell.feature_runtime.close();AppShell._shutdown_live_for_tests();app.processEvents()

```

</details>
