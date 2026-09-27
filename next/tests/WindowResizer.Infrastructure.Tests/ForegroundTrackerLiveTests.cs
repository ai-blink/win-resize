using System.Runtime.InteropServices;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.Infrastructure.Tests;

/// <summary>
/// 실제 전경 창 추적. 이 테스트가 띄운 Notepad 가 전경이 되면 대상이 되고, 닫히면 대상에서 빠지는가.
/// Windows 가 포커스 가로채기를 막아 Notepad 가 전경이 되지 못하면 Inconclusive 다(판정 불가이지 실패가 아니다).
/// </summary>
[TestClass]
[DoNotParallelize]
public sealed class ForegroundTrackerLiveTests
{
    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [TestMethod]
    [TestCategory("Live")]
    public void The_last_foreground_window_becomes_the_target_and_a_closed_one_does_not_stay()
    {
        using var watcher = new WindowEventWatcher();
        using var tracker = new ForegroundTracker(watcher);
        var notepad = OwnNotepad.Launch(new Win32Windows());
        var handle = notepad.Handle;

        try
        {
            if (!WaitUntil(() => GetForegroundWindow() == handle))
                Assert.Inconclusive("새 Notepad 가 전경이 되지 않았다(포커스 가로채기 방지). 추적을 판정할 수 없다.");

            Assert.IsTrue(WaitUntil(() => tracker.Target == handle), $"전경 Notepad {handle} 가 대상이 아니다: {tracker.Target}");
        }
        finally
        {
            notepad.Dispose();
        }

        Assert.IsTrue(WaitUntil(() => tracker.Target != handle), "닫힌 창이 대상으로 남았다");
    }

    private static bool WaitUntil(Func<bool> condition)
    {
        for (var i = 0; i < 40; i++)
        {
            if (condition()) return true;
            Thread.Sleep(100);
        }
        return false;
    }
}
