using System.Runtime.InteropServices;
using System.Text;

namespace WindowResizer.Infrastructure.Windowing;

/// <summary>user32 / kernel32 선언. 이 계층 밖에서는 쓰지 않는다.</summary>
internal static class NativeMethods
{
    public const int SW_SHOWMAXIMIZED = 3;
    public const int SW_MINIMIZE = 6;
    public const int SW_RESTORE = 9;

    public const int GWL_EXSTYLE = -20;
    public const int WS_EX_TOPMOST = 0x00000008;

    public const uint SWP_NOSIZE = 0x0001;
    public const uint SWP_NOMOVE = 0x0002;
    public const uint SWP_NOACTIVATE = 0x0010;

    public static readonly nint HWND_TOPMOST = -1;
    public static readonly nint HWND_NOTOPMOST = -2;

    /// <summary>DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2</summary>
    public static readonly nint DpiAwarenessPerMonitorV2 = -4;

    public const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;
    public const uint MONITORINFOF_PRIMARY = 0x1;
    public const uint WM_CLOSE = 0x0010;

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left, Top, Right, Bottom;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct MONITORINFOEX
    {
        public int cbSize;
        public RECT rcMonitor;
        public RECT rcWork;
        public uint dwFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string szDevice;
    }

    public delegate bool EnumWindowsProc(nint hwnd, nint lParam);
    public delegate bool MonitorEnumProc(nint monitor, nint hdc, ref RECT rect, nint lParam);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool EnumWindows(EnumWindowsProc callback, nint lParam);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool EnumDisplayMonitors(nint hdc, nint clip, MonitorEnumProc callback, nint lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetMonitorInfoW(nint monitor, ref MONITORINFOEX info);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int GetWindowTextW(nint hwnd, StringBuilder text, int maxCount);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowTextLengthW(nint hwnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int GetClassNameW(nint hwnd, StringBuilder className, int maxCount);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetWindowRect(nint hwnd, out RECT rect);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool MoveWindow(nint hwnd, int x, int y, int width, int height, [MarshalAs(UnmanagedType.Bool)] bool repaint);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetWindowPos(nint hwnd, nint insertAfter, int x, int y, int cx, int cy, uint flags);

    /// <summary>반환값은 성공 여부가 아니라 "호출 전에 보였는가"다. 성공 판정에 쓰지 않는다.</summary>
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool ShowWindow(nint hwnd, int command);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindow(nint hwnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindowVisible(nint hwnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsIconic(nint hwnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsZoomed(nint hwnd);

    [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")]
    public static extern nint GetWindowLongPtr(nint hwnd, int index);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(nint hwnd, out uint processId);

    [DllImport("user32.dll")]
    public static extern nint SetThreadDpiAwarenessContext(nint context);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool PostMessageW(nint hwnd, uint message, nint wParam, nint lParam);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern nint OpenProcess(uint access, [MarshalAs(UnmanagedType.Bool)] bool inherit, uint processId);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool QueryFullProcessImageNameW(nint process, uint flags, StringBuilder path, ref int size);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool CloseHandle(nint handle);

    // --- 메시지 루프 ---------------------------------------------------------

    public const uint WM_QUIT = 0x0012;
    public const uint WM_HOTKEY = 0x0312;
    public const uint WM_APP = 0x8000;
    public const uint PM_NOREMOVE = 0x0000;

    [StructLayout(LayoutKind.Sequential)]
    public struct MSG
    {
        public nint hwnd;
        public uint message;
        public nint wParam;
        public nint lParam;
        public uint time;
        public int ptX, ptY;
        public uint lPrivate;
    }

    [DllImport("user32.dll")]
    public static extern int GetMessageW(out MSG msg, nint hwnd, uint filterMin, uint filterMax);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool PeekMessageW(out MSG msg, nint hwnd, uint filterMin, uint filterMax, uint remove);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool TranslateMessage(ref MSG msg);

    [DllImport("user32.dll")]
    public static extern nint DispatchMessageW(ref MSG msg);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool PostThreadMessageW(uint threadId, uint message, nint wParam, nint lParam);

    [DllImport("kernel32.dll")]
    public static extern uint GetCurrentThreadId();

    // --- 단축키 ---------------------------------------------------------------

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool RegisterHotKey(nint hwnd, int id, uint modifiers, uint virtualKey);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool UnregisterHotKey(nint hwnd, int id);

    // --- 창 이벤트 --------------------------------------------------------------

    public const uint EVENT_SYSTEM_FOREGROUND = 0x0003;
    public const uint EVENT_OBJECT_LOCATIONCHANGE = 0x800B;
    public const uint WINEVENT_OUTOFCONTEXT = 0x0000;
    public const uint WINEVENT_SKIPOWNPROCESS = 0x0002;
    public const int OBJID_WINDOW = 0;
    public const int CHILDID_SELF = 0;

    public delegate void WinEventProc(nint hook, uint eventType, nint hwnd, int idObject, int idChild, uint thread, uint time);

    [DllImport("user32.dll")]
    public static extern nint SetWinEventHook(uint eventMin, uint eventMax, nint module, WinEventProc callback, uint processId, uint threadId, uint flags);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool UnhookWinEvent(nint hook);

    // --- 커서 -----------------------------------------------------------------

    public const int SM_XVIRTUALSCREEN = 76;
    public const int SM_YVIRTUALSCREEN = 77;
    public const int SM_CXVIRTUALSCREEN = 78;
    public const int SM_CYVIRTUALSCREEN = 79;

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool ClipCursor(ref RECT rect);

    /// <summary>null 을 넘겨 제한을 푼다.</summary>
    [DllImport("user32.dll", EntryPoint = "ClipCursor", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool ClipCursorRelease(nint none);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetClipCursor(out RECT rect);

    [DllImport("user32.dll")]
    public static extern int GetSystemMetrics(int index);
}
