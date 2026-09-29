using System.IO;
using System.Text;
using WindowResizer.App.ViewModels;
using WindowResizer.Core.Diagnostics;
using WindowResizer.Core.Profiles;

namespace WindowResizer.App.Tests;

/// <summary>로그 페이지의 화면 쪽 규칙(걸러 보기, 지우기, 복사, 내보내기)과 정보 페이지, 상태 줄 -> 로그 연결.</summary>
[TestClass]
public sealed class LogViewModelTests
{
    private sealed class RecordingDialogs : IDialogService
    {
        public List<string> Copied { get; } = [];
        public bool CopyWorks { get; set; } = true;
        public string? SavePath { get; set; }
        public List<string> SaveSuggestions { get; } = [];
        public List<string> Opened { get; } = [];
        public string? OpenError { get; set; }

        public bool ConfirmDelete(string profileName) => true;
        public void Warn(string title, string message) { }
        public bool ShowEditor(ProfileEditorViewModel editor) => false;
        public WindowRow? ChooseWindow(IReadOnlyList<WindowRow> candidates) => null;

        public bool CopyToClipboard(string text)
        {
            if (!CopyWorks) return false;
            Copied.Add(text);
            return true;
        }

        public string? ChooseSaveFile(string title, string suggestedFileName, string filter)
        {
            SaveSuggestions.Add(suggestedFileName);
            return SavePath;
        }

        public string? OpenFolder(string path)
        {
            Opened.Add(path);
            return OpenError;
        }
    }

    private sealed class Harness
    {
        public ActivityLog Log { get; } = new(() => new DateTime(2026, 9, 30, 14, 3, 22));
        public RecordingDialogs Dialogs { get; } = new();
        public List<(string Message, LogLevel Level)> Statuses { get; } = [];
        public LogViewModel Vm { get; }

        public Harness()
        {
            Vm = new LogViewModel(Log, Dialogs, k => k, (m, l) => Statuses.Add((m, l)), () => new DateTime(2026, 9, 30, 14, 3, 22));
        }
    }

    [TestMethod]
    public void New_entries_appear_live_and_the_filter_rebuilds_the_list()
    {
        var h = new Harness();
        h.Log.Add(LogLevel.Info, "a");
        h.Log.Add(LogLevel.Error, "b");
        Assert.HasCount(2, h.Vm.Rows);

        h.Vm.MinLevel = LogLevel.Warning;
        Assert.HasCount(1, h.Vm.Rows);
        Assert.AreEqual(LogLevel.Error, h.Vm.Rows[0].Level);

        h.Log.Add(LogLevel.Info, "hidden");
        h.Log.Add(LogLevel.Warning, "shown");
        Assert.HasCount(2, h.Vm.Rows, "걸러진 수준의 새 줄은 목록에 붙지 않는다");
    }

    [TestMethod]
    public void Lowering_the_maximum_drops_the_oldest_rows_from_the_list_too()
    {
        var h = new Harness();
        for (var i = 0; i < 300; i++) h.Log.Add(LogLevel.Info, "line " + i);

        h.Vm.MaxEntries = 100;

        Assert.HasCount(100, h.Vm.Rows);
        StringAssert.EndsWith(h.Vm.Rows[0].Text, "line 200");
        Assert.AreEqual("Log.Count", h.Vm.CountText, "text 함수가 키를 그대로 돌려주므로 포맷 자리표시가 없다");
    }

    [TestMethod]
    public void Clearing_empties_the_list_and_shows_the_empty_state()
    {
        var h = new Harness();
        Assert.IsTrue(h.Vm.IsEmpty);
        h.Log.Add(LogLevel.Info, "a");
        Assert.IsFalse(h.Vm.IsEmpty);

        h.Vm.ClearCommand.Execute(null);

        Assert.IsEmpty(h.Vm.Rows);
        Assert.IsTrue(h.Vm.IsEmpty);
        Assert.IsEmpty(h.Statuses, "지운 뒤에 새 줄이 생겨 목록이 비지 않는 일은 없다");
    }

    [TestMethod]
    public void Copy_gives_only_the_visible_lines()
    {
        var h = new Harness();
        h.Log.Add(LogLevel.Info, "quiet");
        h.Log.Add(LogLevel.Error, "boom");
        h.Vm.MinLevel = LogLevel.Error;

        h.Vm.CopyCommand.Execute(null);

        Assert.AreEqual("[14:03:22] ERROR: boom", h.Dialogs.Copied.Single());
        Assert.AreEqual("Status.LogCopied", h.Statuses.Single().Message);
    }

    [TestMethod]
    public void Copy_with_nothing_to_copy_or_a_busy_clipboard_says_so()
    {
        var h = new Harness();
        h.Vm.CopyCommand.Execute(null);
        Assert.AreEqual("Status.LogNothingToCopy", h.Statuses.Last().Message);
        Assert.IsEmpty(h.Dialogs.Copied);

        h.Log.Add(LogLevel.Info, "a");
        h.Dialogs.CopyWorks = false;
        h.Vm.CopyCommand.Execute(null);
        Assert.AreEqual(("Status.CopyFailed", LogLevel.Warning), h.Statuses.Last());
    }

    [TestMethod]
    public void Export_writes_a_bom_file_with_the_header_and_the_visible_lines()
    {
        var h = new Harness();
        h.Log.Add(LogLevel.Warning, "저장 실패");
        var path = Path.Combine(Path.GetTempPath(), "wr-log-" + Guid.NewGuid().ToString("N") + ".txt");
        h.Dialogs.SavePath = path;
        try
        {
            h.Vm.ExportCommand.Execute(null);

            Assert.AreEqual("windowresizer_log_20260930_140322.txt", h.Dialogs.SaveSuggestions.Single());
            var bytes = File.ReadAllBytes(path);
            CollectionAssert.AreEqual(new byte[] { 0xEF, 0xBB, 0xBF }, bytes[..3], "옛 편집기에서도 한글이 깨지지 않게 BOM");
            var text = new UTF8Encoding(true).GetString(bytes);
            StringAssert.StartsWith(text.TrimStart('\uFEFF'), "Log.ExportTitle");
            StringAssert.Contains(text, "[14:03:22] WARNING: 저장 실패");
            Assert.AreEqual("Status.LogExported", h.Statuses.Single().Message);
        }
        finally
        {
            File.Delete(path);
        }
    }

    [TestMethod]
    public void Cancelling_the_save_dialog_writes_nothing_and_says_nothing()
    {
        var h = new Harness();
        h.Log.Add(LogLevel.Info, "a");
        h.Dialogs.SavePath = null;

        h.Vm.ExportCommand.Execute(null);

        Assert.IsEmpty(h.Statuses);
    }

    [TestMethod]
    public void An_unwritable_export_path_is_a_warning_not_a_crash()
    {
        var h = new Harness();
        h.Log.Add(LogLevel.Info, "a");
        h.Dialogs.SavePath = Path.Combine(Path.GetTempPath(), "wr-no-such-folder-" + Guid.NewGuid().ToString("N"), "log.txt");

        h.Vm.ExportCommand.Execute(null);

        Assert.AreEqual("Status.LogExportFailed", h.Statuses.Single().Message);
        Assert.AreEqual(LogLevel.Warning, h.Statuses.Single().Level);
    }

    [TestMethod]
    public void A_language_change_rebuilds_the_level_names()
    {
        var language = "a";
        var log = new ActivityLog();
        var vm = new LogViewModel(log, null, k => language + ":" + k, (_, _) => { });
        Assert.AreEqual("a:Log.Level.Info", vm.LevelOptions[0].Display);

        language = "b";
        vm.RefreshTexts();

        Assert.AreEqual("b:Log.Level.Info", vm.LevelOptions[0].Display);
        Assert.HasCount(3, vm.LevelOptions);
    }

    // --- 상태 줄 -> 로그 ---------------------------------------------------------------------

    private static MainViewModel NewMain(Func<Core.Overlay.OverlaySettings, string?>? saveOverlay = null, AboutInfo? about = null,
        RecordingDialogs? dialogs = null) =>
        new(() => [], null!, new ProfileDocument(), _ => null, dialogs!, k => k, saveOverlay: saveOverlay, about: about);

    [TestMethod]
    public void Every_status_line_message_is_logged_and_failures_are_warnings()
    {
        string? saveError = null;
        var main = NewMain(saveOverlay: _ => saveError);

        main.ShowStatus("hello");
        main.Overlay.Hidden = true; // 저장 성공: 성공 문구
        saveError = "denied";
        main.Overlay.Hidden = false; // 저장 실패: 실패 문구

        var entries = main.Activity.Entries;
        Assert.HasCount(3, entries);
        Assert.AreEqual(("hello", LogLevel.Info), (entries[0].Message, entries[0].Level));
        Assert.AreEqual(("Status.OverlayHidden", LogLevel.Info), (entries[1].Message, entries[1].Level), "성공 문구는 정보");
        Assert.AreEqual(LogLevel.Warning, entries[2].Level, "저장 실패는 경고");
        Assert.AreEqual(entries[2].Message, main.Status);
        Assert.HasCount(3, main.Log.Rows, "로그 페이지 목록에도 같은 줄이 있다");
    }

    [TestMethod]
    public void An_unhandled_exception_is_logged_as_an_error_with_its_details()
    {
        var main = new MainViewModel(() => [], null!, new ProfileDocument(), _ => null, null!,
            k => k == "Status.UnhandledError" ? "{0}|{1}" : k);
        Exception thrown;
        try { throw new InvalidOperationException("바인딩이 깨졌다"); }
        catch (Exception ex) { thrown = ex; }

        main.LogException(thrown);

        var errors = main.Activity.AtLeast(LogLevel.Error).ToList();
        Assert.HasCount(2, errors, "상태 줄용 한 줄과 스택이 든 자세한 한 줄");
        StringAssert.Contains(errors[0].Message, "InvalidOperationException");
        StringAssert.Contains(errors[1].Message, "바인딩이 깨졌다");
        StringAssert.Contains(errors[1].Message, "LogViewModelTests", "스택(던진 곳)이 들어 있다");
        Assert.AreEqual("InvalidOperationException|바인딩이 깨졌다", main.Status);
    }

    [TestMethod]
    public void The_status_level_does_not_stick_to_the_next_message()
    {
        var main = NewMain();

        main.ShowStatus("warn", LogLevel.Warning);
        main.ShowStatus("plain");

        Assert.AreEqual(LogLevel.Info, main.Activity.Entries[^1].Level);
    }

    // --- 정보 --------------------------------------------------------------------------------

    private static readonly AboutInfo Sample = new("v0.02.0-preview.5", ".NET 10.0", IsAdministrator: false,
        @"C:\app\WindowResizer.App.exe", @"C:\app\profiles", @"Software\WindowResizer\Next\Settings",
        @"Software\WindowResizer\Next\Overlay", @"Software\WindowResizer\Next\Hotkeys");

    [TestMethod]
    public void The_info_text_lists_every_value_and_the_registry_paths_start_with_hkcu()
    {
        var main = NewMain(about: Sample);

        var text = main.About.InfoText();

        StringAssert.StartsWith(text, "WindowResizer v0.02.0-preview.5");
        StringAssert.Contains(text, @"C:\app\profiles");
        StringAssert.Contains(text, @"HKCU\Software\WindowResizer\Next\Settings");
        Assert.AreEqual(@"HKCU\Software\WindowResizer\Next\Hotkeys", main.About.HotkeyKeyPath);
        Assert.AreEqual("About.No", main.About.AdministratorText);
    }

    [TestMethod]
    public void The_folder_button_opens_the_profiles_folder_and_a_failure_is_a_warning()
    {
        var dialogs = new RecordingDialogs();
        var main = NewMain(about: Sample, dialogs: dialogs);

        main.About.OpenProfilesFolderCommand.Execute(null);
        Assert.AreEqual(@"C:\app\profiles", dialogs.Opened.Single());

        dialogs.OpenError = "no explorer";
        main.About.OpenProfilesFolderCommand.Execute(null);
        Assert.AreEqual(LogLevel.Warning, main.Activity.Entries[^1].Level);
    }

    [TestMethod]
    public void The_copy_buttons_copy_the_info_and_only_the_settings_key_path()
    {
        var dialogs = new RecordingDialogs();
        var main = NewMain(about: Sample, dialogs: dialogs);

        main.About.CopyInfoCommand.Execute(null);
        main.About.CopySettingsKeyCommand.Execute(null);

        Assert.HasCount(2, dialogs.Copied);
        StringAssert.Contains(dialogs.Copied[0], "WindowResizer v0.02.0-preview.5");
        Assert.AreEqual(@"HKCU\Software\WindowResizer\Next\Settings", dialogs.Copied[1]);
    }

    [TestMethod]
    public void Without_known_paths_the_folder_and_key_buttons_are_disabled()
    {
        var main = NewMain();

        Assert.IsFalse(main.About.OpenProfilesFolderCommand.CanExecute(null));
        Assert.IsFalse(main.About.CopySettingsKeyCommand.CanExecute(null));
    }
}
