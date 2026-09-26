using WindowResizer.Core.Windowing;
using static WindowResizer.Infrastructure.Windowing.NativeMethods;

namespace WindowResizer.Infrastructure.Windowing;

/// <summary>
/// 마우스 제한(<c>ClipCursor</c>). 커서 제한은 시스템 전체가 공유하는 자원이라, 건 쪽이 반드시 푼다.
///
/// 해제 성공은 <c>ClipCursor</c> 반환값이 아니라 <c>GetClipCursor</c> 가 가상 화면 전체로 돌아왔는지로 잰다.
/// 다른 프로그램이 제한을 다시 걸 수 있고, Windows 도 전경 창이 바뀌면 제한을 풀 수 있다 -
/// 그래서 PyQt5 는 대상 창이 다시 전경이 될 때 재적용한다. 그 조율은 이 클래스가 아니라 상위 몫이다.
///
/// <b>강제 종료된 프로세스의 제한은 Windows 가 풀지 않는다</b>(2026-09-27 실측: 자식 프로세스가
/// 건 제한이 Stop-Process -Force 뒤에도 남았다). 강제 종료에서는 어떤 코드도 돌 수 없으므로,
/// 걸 때 표식 파일을 남기고 풀 때 지운다. 다음 실행이 <see cref="ReleaseStale"/> 로 남은 표식을 보고 푼다.
/// </summary>
public static class CursorClip
{
    private static int _hooked;

    /// <summary>표식 파일 위치. 테스트가 바꿀 수 있다.</summary>
    public static string MarkerPath { get; set; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "WindowResizer", "cursor-clip.active");

    /// <summary>
    /// 사각형 안에 커서를 가둔다. 처음 호출될 때 프로세스 종료와 처리되지 않은 예외에서
    /// 제한을 푸는 안전장치를 건다. 강제 종료 대비로 표식 파일을 남긴다.
    /// </summary>
    public static bool Confine(PixelRect rect)
    {
        InstallExitRelease();
        WriteMarker();
        var r = new RECT { Left = rect.X, Top = rect.Y, Right = rect.Right, Bottom = rect.Bottom };
        using var _ = new DpiScope();
        return ClipCursor(ref r) && Current() == rect;
    }

    /// <summary>제한을 푼다. 풀린 뒤 커서 범위가 가상 화면 전체인지로 판정한다.</summary>
    public static bool Release()
    {
        using var _ = new DpiScope();
        ClipCursorRelease(0);
        DeleteMarker();
        return Current() == VirtualScreen();
    }

    /// <summary>
    /// 앱 시작 시 부른다. 이전 실행이 제한을 건 채 죽었으면(표식이 남아 있으면) 푼다.
    /// 표식이 없으면 아무것도 하지 않는다 - 다른 프로그램이 건 제한은 건드리지 않는다.
    /// </summary>
    public static bool ReleaseStale()
    {
        if (!File.Exists(MarkerPath)) return false;
        Release();
        return true;
    }

    private static void WriteMarker()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(MarkerPath)!);
            File.WriteAllText(MarkerPath, Environment.ProcessId.ToString());
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    private static void DeleteMarker()
    {
        try { File.Delete(MarkerPath); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    public static PixelRect? Current()
    {
        using var _ = new DpiScope();
        return GetClipCursor(out var r) ? new PixelRect(r.Left, r.Top, r.Right - r.Left, r.Bottom - r.Top) : null;
    }

    public static PixelRect VirtualScreen()
    {
        using var _ = new DpiScope();
        return new PixelRect(
            GetSystemMetrics(SM_XVIRTUALSCREEN), GetSystemMetrics(SM_YVIRTUALSCREEN),
            GetSystemMetrics(SM_CXVIRTUALSCREEN), GetSystemMetrics(SM_CYVIRTUALSCREEN));
    }

    public static bool IsConfined => Current() is { } current && current != VirtualScreen();

    private static void InstallExitRelease()
    {
        if (Interlocked.Exchange(ref _hooked, 1) == 1) return;
        // 우리가 쥐고 있을 때(표식이 있을 때)만 푼다. 다른 프로그램의 제한은 건드리지 않는다.
        AppDomain.CurrentDomain.ProcessExit += (_, _) => ReleaseStale();
        AppDomain.CurrentDomain.UnhandledException += (_, _) => ReleaseStale();
    }
}
