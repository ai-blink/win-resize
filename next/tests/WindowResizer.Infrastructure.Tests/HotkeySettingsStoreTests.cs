using Microsoft.Win32;
using WindowResizer.Core.Hotkeys;
using WindowResizer.Infrastructure.Settings;

namespace WindowResizer.Infrastructure.Tests;

/// <summary>
/// 전체 적용 단축키 저장소(D-026). 테스트마다 HKCU 아래 임시 키와 임시 폴더의 가짜 PyQt5 파일을 쓰고 끝나면 지운다 -
/// 실제 사용자 설정과 실제 <c>application_hotkeys.json</c> 은 읽지도 쓰지도 않는다.
/// </summary>
[TestClass]
public sealed class HotkeySettingsStoreTests
{
    private const string LegacyJson = """{"apply_all_profiles": {"modifiers": 3, "key_code": 69, "enabled": true}}""";

    private string _root = "";
    private string _dir = "";

    private string Key => _root + @"\Next\Hotkeys";
    private string LegacyFile => Path.Combine(_dir, "application_hotkeys.json");

    [TestInitialize]
    public void Setup()
    {
        _root = @"Software\WindowResizer.Tests\" + Guid.NewGuid().ToString("N");
        _dir = Path.Combine(Path.GetTempPath(), "wr-hotkey-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_dir);
    }

    [TestCleanup]
    public void Cleanup()
    {
        Registry.CurrentUser.DeleteSubKeyTree(_root, throwOnMissingSubKey: false);
        using var parent = Registry.CurrentUser.OpenSubKey(@"Software\WindowResizer.Tests");
        if (parent is { SubKeyCount: 0, ValueCount: 0 })
            Registry.CurrentUser.DeleteSubKey(@"Software\WindowResizer.Tests", throwOnMissingSubKey: false);
        if (Directory.Exists(_dir)) Directory.Delete(_dir, recursive: true);
    }

    [TestMethod]
    public void Nothing_saved_and_no_pyqt5_file_means_off()
    {
        Assert.AreEqual(ApplyAllHotkey.Off, new HotkeySettingsStore(Key, LegacyFile).Load());
    }

    [TestMethod]
    public void The_pyqt5_file_is_imported_once_into_the_new_key_and_never_written()
    {
        File.WriteAllText(LegacyFile, LegacyJson);
        var store = new HotkeySettingsStore(Key, LegacyFile);

        Assert.AreEqual(new ApplyAllHotkey(true, "Ctrl+Alt+E"), store.Load());

        // 가져온 값이 새 키에 남았으니, 옛 파일이 바뀌거나 사라져도 새 앱은 자기 값을 쓴다.
        File.WriteAllText(LegacyFile, """{"apply_all_profiles": {"modifiers": 2, "key_code": 65, "enabled": false}}""");
        Assert.AreEqual(new ApplyAllHotkey(true, "Ctrl+Alt+E"), store.Load());
        File.Delete(LegacyFile);
        Assert.AreEqual(new ApplyAllHotkey(true, "Ctrl+Alt+E"), store.Load());
    }

    [TestMethod]
    public void Saved_values_win_over_the_pyqt5_file()
    {
        File.WriteAllText(LegacyFile, LegacyJson);
        var store = new HotkeySettingsStore(Key, LegacyFile);

        Assert.IsTrue(store.TrySave(new ApplyAllHotkey(false, "Ctrl+Shift+F9"), out var error), error?.Message);

        Assert.AreEqual(new ApplyAllHotkey(false, "Ctrl+Shift+F9"), store.Load());
    }

    [TestMethod]
    public void A_null_legacy_path_never_imports_even_when_the_default_file_exists()
    {
        // 라이브 검증용(--hotkey-key)은 실제 PyQt5 파일을 건드리지도 읽지도 않는다.
        Assert.AreEqual(ApplyAllHotkey.Off, new HotkeySettingsStore(Key, legacyFilePath: null).Load());
    }

    [TestMethod]
    public void A_broken_pyqt5_file_imports_nothing()
    {
        File.WriteAllText(LegacyFile, "{ not json");

        Assert.AreEqual(ApplyAllHotkey.Off, new HotkeySettingsStore(Key, LegacyFile).Load());
    }
}
