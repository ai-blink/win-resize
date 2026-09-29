using Microsoft.Win32;
using WindowResizer.Core.Settings;
using WindowResizer.Infrastructure.Settings;

namespace WindowResizer.Infrastructure.Tests;

/// <summary>
/// 앱 설정 저장소와 시작 프로그램 등록. 테스트마다 HKCU 아래 임시 키(가짜 PyQt5 키, 가짜 Run 키 포함)를 쓰고 끝나면
/// 지운다 - 실제 사용자 설정과 실제 시작 목록은 읽지도 쓰지도 않는다.
/// </summary>
[TestClass]
public sealed class AppSettingsStoreTests
{
    private string _root = "";

    private string Key => _root + @"\Next\Settings";
    private string LegacyTheme => _root + @"\ThemeManager";
    private string LegacyScale => _root + @"\UiScale";
    private string RunKey => _root + @"\Run";

    [TestInitialize]
    public void Setup() => _root = @"Software\WindowResizer.Tests\" + Guid.NewGuid().ToString("N");

    [TestCleanup]
    public void Cleanup()
    {
        Registry.CurrentUser.DeleteSubKeyTree(_root, throwOnMissingSubKey: false);
        using var parent = Registry.CurrentUser.OpenSubKey(@"Software\WindowResizer.Tests");
        if (parent is { SubKeyCount: 0, ValueCount: 0 })
            Registry.CurrentUser.DeleteSubKey(@"Software\WindowResizer.Tests", throwOnMissingSubKey: false);
    }

    private void WriteLegacy()
    {
        using (var theme = Registry.CurrentUser.CreateSubKey(LegacyTheme))
        {
            theme.SetValue("theme", "dark");
            theme.SetValue("color_scheme", "Dark");
            theme.SetValue("follow_system", "true");
        }
        using var scale = Registry.CurrentUser.CreateSubKey(LegacyScale);
        scale.SetValue("scale_percent", 75, RegistryValueKind.DWord); // PyQt5 는 정수를 DWORD 로 쓴다.
        scale.SetValue("main_window_size", "@Size(920 640)");
    }

    [TestMethod]
    public void Nothing_saved_and_no_pyqt5_keys_means_defaults()
    {
        var settings = new AppSettingsStore(Key, LegacyTheme, LegacyScale).Load();

        Assert.AreEqual(ThemeChoice.System, settings.Theme);
        Assert.AreEqual(100, settings.ScalePercent);
        Assert.AreEqual("ko", settings.Language);
    }

    [TestMethod]
    public void The_pyqt5_keys_are_imported_once_into_the_new_key_and_never_written()
    {
        WriteLegacy();
        var store = new AppSettingsStore(Key, LegacyTheme, LegacyScale);

        var first = store.Load();
        Assert.AreEqual(ThemeChoice.System, first.Theme);
        Assert.AreEqual(75, first.ScalePercent);

        // 가져온 값이 새 키에 남았으니 옛 키가 바뀌어도 새 앱은 자기 값을 쓴다.
        using (var scale = Registry.CurrentUser.CreateSubKey(LegacyScale)) scale.SetValue("scale_percent", 125, RegistryValueKind.DWord);
        Assert.AreEqual(75, store.Load().ScalePercent);

        // 옛 키는 읽기만 했다.
        using var legacy = Registry.CurrentUser.OpenSubKey(LegacyScale)!;
        Assert.AreEqual(125, legacy.GetValue("scale_percent"));
        Assert.AreEqual("@Size(920 640)", legacy.GetValue("main_window_size"));
    }

    [TestMethod]
    public void Saved_values_win_over_the_pyqt5_keys_and_round_trip_with_the_window()
    {
        WriteLegacy();
        var store = new AppSettingsStore(Key, LegacyTheme, LegacyScale);
        var settings = new AppSettings
        {
            Theme = ThemeChoice.Light,
            ScalePercent = 110,
            Language = "en",
            Window = new SavedWindowBounds(10, 20, 1000, 640, Maximized: false),
        };

        Assert.IsTrue(store.TrySave(settings, out var error), error?.Message);
        var read = store.Load();

        Assert.AreEqual(ThemeChoice.Light, read.Theme);
        Assert.AreEqual(110, read.ScalePercent);
        Assert.AreEqual("en", read.Language);
        Assert.AreEqual(settings.Window, read.Window);
    }

    [TestMethod]
    public void Turning_the_window_memory_off_deletes_the_saved_window_values()
    {
        var store = new AppSettingsStore(Key, null, null);
        var settings = new AppSettings { Window = new SavedWindowBounds(1, 2, 3, 4, false) };
        Assert.IsTrue(store.TrySave(settings, out _));

        settings.RememberWindow = false;
        settings.Window = null;
        Assert.IsTrue(store.TrySave(settings, out _));

        using var key = Registry.CurrentUser.OpenSubKey(Key)!;
        Assert.IsNull(key.GetValue("window_left"));
        Assert.IsNull(key.GetValue("window_width"));
        Assert.IsNull(store.Load().Window);
    }

    [TestMethod]
    public void Null_legacy_paths_never_import_even_when_the_real_pyqt5_keys_exist()
    {
        // 라이브 검증용(--settings-key)은 실제 PyQt5 키를 건드리지도 읽지도 않는다.
        WriteLegacy();

        Assert.AreEqual(100, new AppSettingsStore(Key, null, null).Load().ScalePercent);
    }

    [TestMethod]
    public void Startup_registration_writes_a_quoted_command_with_the_minimized_argument_and_removes_it()
    {
        var startup = new StartupRegistration(RunKey, "WindowResizerTest");
        Assert.IsFalse(startup.IsEnabled());

        Assert.IsNull(startup.Set(true, @"C:\Program Files\WR\WindowResizer.App.exe"));

        Assert.IsTrue(startup.IsEnabled());
        Assert.AreEqual("\"C:\\Program Files\\WR\\WindowResizer.App.exe\" --minimized", startup.Command());

        Assert.IsNull(startup.Set(false, ""));
        Assert.IsFalse(startup.IsEnabled());
    }

    [TestMethod]
    public void Removing_a_registration_that_does_not_exist_is_not_an_error()
    {
        Assert.IsNull(new StartupRegistration(RunKey, "WindowResizerTest").Set(false, ""));
    }
}
