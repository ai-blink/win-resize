using System.Globalization;
using Microsoft.Win32;
using WindowResizer.Core.Overlay;

namespace WindowResizer.Infrastructure.Settings;

/// <summary>
/// 오버레이 설정을 HKCU 레지스트리에 읽고 쓴다(D-023).
///
/// 새 앱은 <c>Software\WindowResizer\Next\Overlay</c> 에 물리 픽셀로 쓴다. PyQt5 의
/// <c>Software\WindowResizer\Overlay</c> 는 Qt 논리 픽셀이고 Qt5 가 배율을 정수로 반올림하므로 단위를 확정할 수
/// 없다 - 같은 키를 쓰면 한쪽 앱의 버튼이 화면 밖으로 간다. 그래서 새 키가 아직 없을 때만 옛 키에서 단위 없는
/// 다섯 값(발동 방식, 드웰, 감추기, 스위치 표시, 잠금)을 가져오고 좌표는 버린다. 옛 키는 읽기만 한다.
///
/// 키 경로는 생성자에서 받는다 - 테스트가 사용자 설정을 건드리지 않게(PyQt5 는 테스트가 실제 레지스트리를 썼다).
/// </summary>
public sealed class OverlaySettingsStore(string keyPath = OverlaySettingsStore.DefaultKeyPath, string? legacyKeyPath = OverlaySettingsStore.LegacyKeyPath)
{
    public const string DefaultKeyPath = @"Software\WindowResizer\Next\Overlay";
    public const string LegacyKeyPath = @"Software\WindowResizer\Overlay";

    public string KeyPath { get; } = keyPath;

    public OverlaySettings Load()
    {
        var current = ReadValues(KeyPath);
        if (current is not null) return OverlaySettings.FromValues(current);

        var legacy = legacyKeyPath is null ? null : ReadValues(legacyKeyPath);
        return legacy is null ? new OverlaySettings() : OverlaySettings.FromValues(legacy, includePositions: false);
    }

    /// <summary>저장한다. 실패하면 false 와 원인 - 설정 저장 실패로 앱이 멈추지는 않는다.</summary>
    public bool TrySave(OverlaySettings settings, out Exception? error)
    {
        error = null;
        try
        {
            using var key = Registry.CurrentUser.CreateSubKey(KeyPath, writable: true);
            var values = settings.ToValues();
            foreach (var (name, value) in values) key.SetValue(name, value, RegistryValueKind.String);

            // 스위치 위치를 지웠으면 옛 값도 지운다.
            foreach (var stale in new[] { "toggle_x", "toggle_y" }.Where(n => !values.ContainsKey(n)))
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
            var value = key.GetValue(name);
            var text = value switch
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
