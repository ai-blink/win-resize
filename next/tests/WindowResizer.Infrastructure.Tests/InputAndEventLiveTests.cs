using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using WindowResizer.Core.Hotkeys;
using WindowResizer.Core.Windowing;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.Infrastructure.Tests;

/// <summary>
/// S3c 라이브 게이트: 단축키, 창 이벤트, 마우스 제한이 실제 OS 에서 동작하는가.
/// 전부 시스템 전역 자원이라 병렬로 돌리지 않는다.
/// </summary>
[TestClass]
[DoNotParallelize]
public sealed class InputAndEventLiveTests
{
    private static readonly Win32Windows Windows = new();

    /// <summary>다른 프로그램이 쓸 일이 거의 없는 조합.</summary>
    private static readonly HotkeyCombination Probe =
        HotkeyCombination.Parse("Ctrl+Alt+Shift+F24");

    [TestMethod]
    [TestCategory("Live")]
    public void Registered_hotkey_fires_on_real_key_input_and_conflicts_are_reported()
    {
        using var hotkeys = new GlobalHotkeys();
        var fired = new ManualResetEventSlim();
        hotkeys.Pressed += (_, combination) => { if (combination == Probe) fired.Set(); };

        var id = hotkeys.Register(Probe, out var error);
        if (id is null && error == 1409)
            Assert.Inconclusive("다른 프로그램이 이미 Ctrl+Alt+Shift+F24 를 잡고 있다");
        Assert.IsNotNull(id, "등록 실패, Win32 오류 " + error);

        // 같은 조합을 두 번째로 잡으면 충돌이 오류 코드로 보여야 한다.
        using (var second = new GlobalHotkeys())
        {
            Assert.IsNull(second.Register(Probe, out var conflict));
            Assert.AreEqual(1409, conflict, "ERROR_HOTKEY_ALREADY_REGISTERED 여야 한다");
        }

        // 실제 키 입력. 끝에 반드시 전부 뗀다.
        var keys = new ushort[] { 0x11, 0x12, 0x10, (ushort)Probe.VirtualKey }; // Ctrl Alt Shift F24
        try
        {
            SendKeys(keys, up: false);
        }
        finally
        {
            SendKeys(keys.Reverse().ToArray(), up: true);
        }

        Assert.IsTrue(fired.Wait(TimeSpan.FromSeconds(2)), "단축키를 눌렀는데 Pressed 가 오지 않았다");
        Assert.IsTrue(hotkeys.Unregister(id.Value));
    }

    [TestMethod]
    [TestCategory("Live")]
    public void Location_change_of_a_real_window_is_reported()
    {
        using var watcher = new WindowEventWatcher();
        var moved = new ConcurrentBag<nint>();
        var arrived = new ManualResetEventSlim();
        nint target = 0;
        watcher.LocationChanged += hwnd =>
        {
            moved.Add(hwnd);
            if (hwnd == Volatile.Read(ref target)) arrived.Set();
        };

        using var notepad = OwnNotepad.Launch(Windows);
        Volatile.Write(ref target, notepad.Handle);
        var primary = Windows.EnumerateMonitors().Single(m => m.IsPrimary);

        Assert.IsTrue(Windows.Move(notepad.Handle, new PixelRect(primary.WorkArea.X + 200, primary.WorkArea.Y + 150, 700, 500)));

        Assert.IsTrue(arrived.Wait(TimeSpan.FromSeconds(2)),
            $"창을 옮겼는데 위치 이벤트가 오지 않았다(다른 창 이벤트 {moved.Count}건)");
    }

    [TestMethod]
    [TestCategory("Live")]
    public void Cursor_is_confined_and_released_as_measured_by_get_clip_cursor()
    {
        using var marker = new TemporaryMarker();
        var primary = Windows.EnumerateMonitors().Single(m => m.IsPrimary);
        var area = new PixelRect(primary.WorkArea.X + 50, primary.WorkArea.Y + 50,
            primary.WorkArea.Width - 100, primary.WorkArea.Height - 100);

        try
        {
            Assert.IsTrue(CursorClip.Confine(area), "제한이 걸리지 않았다: " + CursorClip.Current());
            Assert.IsTrue(CursorClip.IsConfined);
            Assert.IsTrue(File.Exists(CursorClip.MarkerPath), "강제 종료 대비 표식이 없다");
        }
        finally
        {
            Assert.IsTrue(CursorClip.Release(), "해제 뒤에도 범위가 가상 화면 전체가 아니다: " + CursorClip.Current());
        }

        Assert.IsFalse(File.Exists(CursorClip.MarkerPath));
        Assert.IsFalse(CursorClip.IsConfined);
    }

    /// <summary>강제 종료 복구: 표식이 남아 있으면 다음 실행이 푼다.</summary>
    [TestMethod]
    [TestCategory("Live")]
    public void Stale_marker_from_a_killed_run_releases_the_clip()
    {
        using var marker = new TemporaryMarker();
        var primary = Windows.EnumerateMonitors().Single(m => m.IsPrimary);

        try
        {
            // "죽은 이전 실행"을 흉내낸다: 제한과 표식만 남기고 정상 해제를 하지 않는다.
            Assert.IsTrue(CursorClip.Confine(primary.WorkArea));

            Assert.IsTrue(CursorClip.ReleaseStale());
            Assert.IsFalse(CursorClip.IsConfined);
            Assert.IsFalse(CursorClip.ReleaseStale(), "두 번째 호출은 할 일이 없어야 한다");
        }
        finally
        {
            CursorClip.Release();
        }
    }

    /// <summary>표식이 없으면 다른 프로그램이 건 제한은 건드리지 않는다.</summary>
    [TestMethod]
    [TestCategory("Live")]
    public void Clip_owned_by_someone_else_is_left_alone()
    {
        using var marker = new TemporaryMarker();
        var primary = Windows.EnumerateMonitors().Single(m => m.IsPrimary);
        var foreign = new ClipRect { Left = primary.WorkArea.X + 10, Top = primary.WorkArea.Y + 10,
            Right = primary.WorkArea.Right - 10, Bottom = primary.WorkArea.Bottom - 10 };

        try
        {
            // 표식 없이 직접 건다 - 다른 프로그램이 건 것과 같다.
            ForeignClip(ref foreign);
            Assert.IsTrue(CursorClip.IsConfined);

            Assert.IsFalse(CursorClip.ReleaseStale());
            Assert.IsTrue(CursorClip.IsConfined, "남의 제한을 풀었다");
        }
        finally
        {
            CursorClip.Release();
        }
    }

    // --- 테스트 전용 입력 주입 ------------------------------------------------------

    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public nint dwExtraInfo; }

    [StructLayout(LayoutKind.Explicit, Size = 40)]
    private struct INPUT
    {
        [FieldOffset(0)] public uint type;
        [FieldOffset(8)] public KEYBDINPUT ki;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ClipRect { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint count, INPUT[] inputs, int size);

    [DllImport("user32.dll", EntryPoint = "ClipCursor")]
    private static extern bool ClipCursorRaw(ref ClipRect rect);

    [DllImport("user32.dll")]
    private static extern nint SetThreadDpiAwarenessContext(nint context);

    private static void ForeignClip(ref ClipRect rect)
    {
        var previous = SetThreadDpiAwarenessContext(-4);
        try { Assert.IsTrue(ClipCursorRaw(ref rect)); }
        finally { SetThreadDpiAwarenessContext(previous); }
    }

    private static void SendKeys(ushort[] keys, bool up)
    {
        const uint KEYEVENTF_KEYUP = 0x0002;
        var inputs = keys.Select(k => new INPUT
        {
            type = 1,
            ki = new KEYBDINPUT { wVk = k, dwFlags = up ? KEYEVENTF_KEYUP : 0 },
        }).ToArray();
        var sent = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<INPUT>());
        Assert.AreEqual((uint)inputs.Length, sent, "SendInput 이 입력을 다 보내지 못했다(UIPI 차단일 수 있다)");
    }

    /// <summary>테스트가 실제 사용자 표식 파일을 건드리지 않게 임시 경로로 바꾼다.</summary>
    private sealed class TemporaryMarker : IDisposable
    {
        private readonly string _original = CursorClip.MarkerPath;

        public TemporaryMarker() =>
            CursorClip.MarkerPath = Path.Combine(Path.GetTempPath(), "wr-clip-" + Guid.NewGuid().ToString("N"), "marker");

        public void Dispose()
        {
            var dir = Path.GetDirectoryName(CursorClip.MarkerPath)!;
            if (Directory.Exists(dir)) Directory.Delete(dir, recursive: true);
            CursorClip.MarkerPath = _original;
        }
    }
}
