using System.Globalization;
using Microsoft.Win32;
using WindowResizer.Core.Settings;

namespace WindowResizer.Infrastructure.Settings;

/// <summary>
/// 앱 설정(테마, 화면 크기, 언어, 창 기억)을 HKCU 레지스트리에 읽고 쓴다. 오버레이(D-023)와 단축키(D-026)와 같은 규율이다.
///
/// 새 앱은 <c>Software\WindowResizer\Next\Settings</c> 에 쓴다. PyQt5 의 <c>ThemeManager</c> 와 <c>UiScale</c> 키는
/// 두 앱이 서로 덮어쓰지 않게 읽기만 한다 - 새 키가 아직 없을 때 <b>한 번만</b> 가져와 새 키에 저장하고 그 뒤로는 보지
/// 않는다. 가져오는 값의 범위는 <see cref="AppSettings.FromPyQt5"/> 가 정한다.
///
/// 경로는 생성자에서 받는다 - 테스트와 라이브 검증이 사용자 설정을 건드리지 않게.
/// </summary>
public sealed class AppSettingsStore(
    string keyPath = AppSettingsStore.DefaultKeyPath,
    string? legacyThemeKeyPath = AppSettingsStore.LegacyThemeKeyPath,
    string? legacyScaleKeyPath = AppSettingsStore.LegacyScaleKeyPath)
{
    public const string DefaultKeyPath = @"Software\WindowResizer\Next\Settings";
    public const string LegacyThemeKeyPath = @"Software\WindowResizer\ThemeManager";
    public const string LegacyScaleKeyPath = @"Software\WindowResizer\UiScale";

    public string KeyPath { get; } = keyPath;

    public AppSettings Load()
    {
        var current = ReadValues(KeyPath);
        if (current is not null) return AppSettings.FromValues(current);

        var theme = legacyThemeKeyPath is null ? null : ReadValues(legacyThemeKeyPath);
        var scale = legacyScaleKeyPath is null ? null : ReadValues(legacyScaleKeyPath);
        if (theme is null && scale is null) return new AppSettings();

        // 한 번만 가져오려면 가져온 값을 새 키에 남겨야 한다. 저장이 실패하면 다음 실행이 다시 가져온다.
        var imported = AppSettings.FromPyQt5(theme, scale);
        TrySave(imported, out _);
        return imported;
    }

    /// <summary>저장한다. 실패하면 false 와 원인 - 설정 저장 실패로 앱이 멈추지는 않는다.</summary>
    public bool TrySave(AppSettings settings, out Exception? error)
    {
        error = null;
        try
        {
            using var key = Registry.CurrentUser.CreateSubKey(KeyPath, writable: true);
            var values = settings.ToValues();
            foreach (var (name, value) in values) key.SetValue(name, value, RegistryValueKind.String);

            // 기억하지 않기로 했거나 창 값을 지웠으면 옛 창 값도 지운다.
            foreach (var stale in new[] { "window_left", "window_top", "window_width", "window_height", "window_maximized" }
                         .Where(n => !values.ContainsKey(n)))
                key.DeleteValue(stale, throwOnMissingValue: false);
            return true;
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException or System.Security.SecurityException or IOException)
        {
            error = ex;
            return false;
        }
    }

    /// <summary>키가 없으면 null. DWORD(PyQt5 가 정수를 그렇게 쓴다)와 문자열을 모두 문자열로 읽는다.</summary>
    private static Dictionary<string, string>? ReadValues(string path)
    {
        using var key = Registry.CurrentUser.OpenSubKey(path, writable: false);
        if (key is null) return null;

        var values = new Dictionary<string, string>();
        foreach (var name in key.GetValueNames())
        {
            var text = key.GetValue(name) switch
            {
                string s => s,
                int i => i.ToString(CultureInfo.InvariantCulture),
                long l => l.ToString(CultureInfo.InvariantCulture),
                _ => null,
            };
            if (text is not null) values[name] = text;
        }
        return values;
    }
}
