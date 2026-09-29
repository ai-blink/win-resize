using Microsoft.Win32;

namespace WindowResizer.Infrastructure.Settings;

/// <summary>
/// "Windows 시작 때 자동 실행"(현재 사용자). <c>HKCU\Software\Microsoft\Windows\CurrentVersion\Run</c> 에 값 하나를 넣고
/// 뺀다 - 관리자 권한이 필요 없다. 켜져 있는지는 우리 설정이 아니라 이 값이 정한다(사용자가 작업 관리자의 시작 앱에서
/// 끌 수도 있고, 그러면 <c>StartupApproved</c> 가 바뀐다 - 그 경우는 Windows 가 실행을 막을 뿐이라 등록은 그대로 본다).
///
/// PyQt5 <c>startup_manager.py</c> 는 GUI 에 연결된 적이 없어 이 PC 에는 옛 등록이 없다. 그래서 가져올 값이 없다.
/// 키 경로와 값 이름은 생성자에서 받는다 - 테스트와 라이브 검증이 실제 시작 목록을 건드리지 않게.
/// </summary>
public sealed class StartupRegistration(
    string keyPath = StartupRegistration.DefaultKeyPath,
    string valueName = StartupRegistration.DefaultValueName)
{
    public const string DefaultKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
    public const string DefaultValueName = "WindowResizer";

    /// <summary>시작할 때 트레이로만 뜨게 하는 실행 인자(App 이 읽는다).</summary>
    public const string MinimizedArgument = "--minimized";

    public string KeyPath { get; } = keyPath;

    public bool IsEnabled()
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(KeyPath, writable: false);
            return key?.GetValue(valueName) is string { Length: > 0 };
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException or System.Security.SecurityException or IOException)
        {
            return false;
        }
    }

    /// <summary>
    /// 켜고 끈다. 성공하면 null, 실패하면 원인. 등록하는 명령은 <c>"실행 파일" --minimized</c> 다 - 로그인할 때마다
    /// 큰 창이 뜨는 것을 막는다(창을 닫으면 트레이로 숨는 앱이라 원래 그렇게 쓰인다).
    /// </summary>
    public string? Set(bool enabled, string executablePath)
    {
        try
        {
            if (enabled)
            {
                using var key = Registry.CurrentUser.CreateSubKey(KeyPath, writable: true);
                key.SetValue(valueName, $"\"{executablePath}\" {MinimizedArgument}", RegistryValueKind.String);
            }
            else
            {
                using var key = Registry.CurrentUser.OpenSubKey(KeyPath, writable: true);
                key?.DeleteValue(valueName, throwOnMissingValue: false);
            }
            return null;
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException or System.Security.SecurityException or IOException)
        {
            return ex.Message;
        }
    }

    /// <summary>등록된 명령 그대로(라이브 검증과 진단용). 없으면 null.</summary>
    public string? Command()
    {
        using var key = Registry.CurrentUser.OpenSubKey(KeyPath, writable: false);
        return key?.GetValue(valueName) as string;
    }
}
