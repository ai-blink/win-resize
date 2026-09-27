using System.Diagnostics;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.Infrastructure.Tests;

/// <summary>
/// 라이브 테스트용 Notepad 창. <b>이 테스트가 띄운 창만</b> 돌려준다 - 실행 전 창 목록을 떠 두고
/// 새로 생긴 Notepad 창만 고른다. Win11 Notepad 가 기존 창에 탭으로 열어 새 창이 없으면
/// 기존 창을 건드리지 않고 Inconclusive 로 끝낸다. 닫을 때도 그 창에만 요청한다.
/// </summary>
internal sealed class OwnNotepad : IDisposable
{
    private OwnNotepad(DesktopWindow window) => Window = window;

    public DesktopWindow Window { get; }
    public nint Handle => Window.Handle;

    public static OwnNotepad Launch(Win32Windows windows)
    {
        var before = windows.EnumerateWindows().Select(w => w.Handle).ToHashSet();

        try
        {
            Process.Start(new ProcessStartInfo("notepad.exe") { UseShellExecute = true })?.Dispose();
        }
        catch (Exception ex)
        {
            Assert.Inconclusive("Notepad 를 띄우지 못했다: " + ex.Message);
        }

        var deadline = DateTime.UtcNow.AddSeconds(10);
        while (DateTime.UtcNow < deadline)
        {
            var fresh = windows.EnumerateWindows()
                .Where(w => !before.Contains(w.Handle))
                .FirstOrDefault(w => w.Info.ProcessName.Equals("notepad.exe", StringComparison.OrdinalIgnoreCase));
            if (fresh is not null) return new OwnNotepad(fresh);
            Thread.Sleep(100);
        }

        Assert.Inconclusive("새 Notepad 창이 생기지 않았다(기존 창에 탭으로 열렸을 수 있다). 기존 창은 건드리지 않았다.");
        return null!;
    }

    /// <summary>
    /// 닫기를 요청하고 <b>창과 프로세스가 실제로 사라질 때까지</b> 기다린다. 요청만 하고 돌아가면 다음 테스트가
    /// 띄운 Notepad 가 아직 끝나는 중인 프로세스에 넘겨져 같이 사라지고, 그 사이 전경이 바뀌어 커서 제한도 풀린다
    /// (2026-09-27 실측: 이 테스트 뒤에 붙은 Notepad 게이트와 커서 게이트가 두 번 연속 실패).
    /// </summary>
    public void Dispose()
    {
        Win32Windows.RequestClose(Handle);
        var windows = new Win32Windows();
        for (var i = 0; i < 50 && windows.IsWindow(Handle); i++) Thread.Sleep(100);

        try
        {
            using var process = Process.GetProcessById((int)Window.ProcessId);
            // 다른 창(사용자의 Notepad)이 같은 프로세스에 있으면 프로세스는 남는다. 창이 없어진 것으로 충분하다.
            process.WaitForExit(3000);
        }
        catch (ArgumentException)
        {
            // 이미 끝났다.
        }
    }
}
