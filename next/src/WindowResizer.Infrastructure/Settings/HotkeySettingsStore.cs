using Microsoft.Win32;
using WindowResizer.Core.Hotkeys;

namespace WindowResizer.Infrastructure.Settings;

/// <summary>
/// 전체 적용 단축키를 HKCU 레지스트리에 읽고 쓴다(D-026). 오버레이 설정(D-023)과 같은 규율이다.
///
/// 새 앱은 <c>Software\WindowResizer\Next\Hotkeys</c> 에 쓴다. PyQt5 의 <c>application_hotkeys.json</c> 은 두 앱이
/// 서로 덮어쓰지 않게 읽기만 한다 - 새 키가 아직 없을 때 <b>한 번만</b> 가져와 새 키에 저장하고, 그 뒤로는 보지 않는다.
///
/// 경로는 생성자에서 받는다 - 테스트와 라이브 검증이 사용자 설정을 건드리지 않게.
/// </summary>
public sealed class HotkeySettingsStore(
    string keyPath = HotkeySettingsStore.DefaultKeyPath,
    string? legacyFilePath = "")
{
    public const string DefaultKeyPath = @"Software\WindowResizer\Next\Hotkeys";

    /// <summary>PyQt5 파일 위치. 빈 문자열이면 기본 위치, null 이면 가져오지 않는다.</summary>
    public static string LegacyFilePath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "WindowResizer", "application_hotkeys.json");

    public string KeyPath { get; } = keyPath;

    public ApplyAllHotkey Load()
    {
        using (var key = Registry.CurrentUser.OpenSubKey(KeyPath, writable: false))
        {
            if (key is not null)
            {
                return new ApplyAllHotkey(
                    (key.GetValue("apply_all_enabled") as string) is "true" or "True" or "1",
                    (key.GetValue("apply_all_combination") as string) ?? "");
            }
        }

        var imported = ReadLegacy();
        if (imported is null) return ApplyAllHotkey.Off;

        // 한 번만 가져오려면 가져온 값을 새 키에 남겨야 한다. 저장이 실패하면 다음 실행이 다시 가져온다.
        TrySave(imported, out _);
        return imported;
    }

    /// <summary>저장한다. 실패하면 false 와 원인 - 설정 저장 실패로 앱이 멈추지는 않는다.</summary>
    public bool TrySave(ApplyAllHotkey hotkey, out Exception? error)
    {
        error = null;
        try
        {
            using var key = Registry.CurrentUser.CreateSubKey(KeyPath, writable: true);
            key.SetValue("apply_all_enabled", hotkey.Enabled ? "true" : "false", RegistryValueKind.String);
            key.SetValue("apply_all_combination", hotkey.Combination, RegistryValueKind.String);
            return true;
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException or System.Security.SecurityException or IOException)
        {
            error = ex;
            return false;
        }
    }

    private ApplyAllHotkey? ReadLegacy()
    {
        if (legacyFilePath is null) return null;
        var path = legacyFilePath.Length == 0 ? LegacyFilePath : legacyFilePath;
        try
        {
            return File.Exists(path) ? ApplyAllHotkey.FromLegacyJson(File.ReadAllText(path)) : null;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }
}
