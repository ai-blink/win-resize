using Microsoft.Win32;
using WindowResizer.Core.Overlay;
using WindowResizer.Infrastructure.Settings;

namespace WindowResizer.Infrastructure.Tests;

/// <summary>
/// 레지스트리 저장소(D-023). 테스트마다 HKCU 아래 임시 키 두 개(새 키, 옛 키)를 쓰고 끝나면 지운다 -
/// 실제 사용자 설정(Software\WindowResizer\...)은 읽지도 쓰지도 않는다.
/// </summary>
[TestClass]
public sealed class OverlaySettingsStoreTests
{
    private string _root = "";

    private string NewKey => _root + @"\Next\Overlay";
    private string LegacyKey => _root + @"\Overlay";

    [TestInitialize]
    public void Setup() => _root = @"Software\WindowResizer.Tests\" + Guid.NewGuid().ToString("N");

    [TestCleanup]
    public void Cleanup()
    {
        Registry.CurrentUser.DeleteSubKeyTree(_root, throwOnMissingSubKey: false);
        // 빈 부모 키도 남기지 않는다.
        using var parent = Registry.CurrentUser.OpenSubKey(@"Software\WindowResizer.Tests");
        if (parent is { SubKeyCount: 0, ValueCount: 0 })
            Registry.CurrentUser.DeleteSubKey(@"Software\WindowResizer.Tests", throwOnMissingSubKey: false);
    }

    [TestMethod]
    public void First_run_takes_only_the_unitless_flags_from_the_pyqt5_key()
    {
        using (var legacy = Registry.CurrentUser.CreateSubKey(LegacyKey))
        {
            legacy.SetValue("interaction_mode", "dwell");
            legacy.SetValue("hidden", "true");
            legacy.SetValue("toggle_x", 254, RegistryValueKind.DWord);
            legacy.SetValue("toggle_y", 1021, RegistryValueKind.DWord);
            legacy.SetValue("layout", """[{"profile_id": "a", "x": 385, "y": 959}]""");
        }

        var s = new OverlaySettingsStore(NewKey, LegacyKey).Load();

        Assert.AreEqual(OverlayActivation.Dwell, s.Activation);
        Assert.IsTrue(s.Hidden);
        Assert.IsNull(s.TogglePosition, "Qt 논리 픽셀 좌표는 단위가 달라 가져오지 않는다");
        Assert.IsEmpty(s.Layout);
    }

    [TestMethod]
    public void Saved_settings_win_over_the_legacy_key_and_the_legacy_key_is_never_written()
    {
        using (var legacy = Registry.CurrentUser.CreateSubKey(LegacyKey)) legacy.SetValue("interaction_mode", "dwell");
        var store = new OverlaySettingsStore(NewKey, LegacyKey);

        var settings = new OverlaySettings { Activation = OverlayActivation.Click, DwellMs = 1500, TogglePosition = new ScreenPoint(1, 2) };
        settings.Layout["p"] = new ScreenPoint(-1200, 300);
        Assert.IsTrue(store.TrySave(settings, out var error), error?.Message);

        var loaded = store.Load();
        Assert.AreEqual((OverlayActivation.Click, 1500), (loaded.Activation, loaded.DwellMs));
        Assert.AreEqual(new ScreenPoint(-1200, 300), loaded.Layout["p"]);

        using var legacyAfter = Registry.CurrentUser.OpenSubKey(LegacyKey)!;
        CollectionAssert.AreEquivalent(new[] { "interaction_mode" }, legacyAfter.GetValueNames());
    }

    [TestMethod]
    public void Clearing_the_switch_position_removes_the_stale_values()
    {
        var store = new OverlaySettingsStore(NewKey, LegacyKey);
        store.TrySave(new OverlaySettings { TogglePosition = new ScreenPoint(5, 6) }, out _);
        store.TrySave(new OverlaySettings(), out _);

        Assert.IsNull(store.Load().TogglePosition);
    }

    [TestMethod]
    public void Nothing_anywhere_gives_the_defaults()
    {
        var s = new OverlaySettingsStore(NewKey, LegacyKey).Load();

        Assert.AreEqual((OverlayActivation.Click, OverlaySettings.DefaultDwellMs, false), (s.Activation, s.DwellMs, s.Hidden));
    }
}
