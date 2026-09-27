using System.IO;
using System.Xml.Linq;
using WindowResizer.App.ViewModels;
using WindowResizer.Core.Profiles;
using WindowResizer.Core.Windowing;

namespace WindowResizer.App.Tests;

/// <summary>
/// 메인 창 상태 규율(notes/plans/2026-09-27-s4-main-window-state-and-menu-map.md 2절).
/// 실제 창 없이 가짜 열거와 가짜 창 조작으로 잰다.
/// </summary>
[TestClass]
public sealed class MainViewModelTests
{
    private static readonly string[] Keys = [];

    [TestMethod]
    public void Selection_survives_a_refresh_by_handle_and_clears_when_the_window_is_gone()
    {
        var desktop = new FakeDesktop(Row(1, "Notepad"), Row(2, "Blender"));
        var vm = desktop.CreateViewModel();
        vm.RefreshWindows();
        vm.SelectedWindow = vm.Windows.Single(w => w.Handle == 2);

        desktop.Rows = [Row(2, "Blender (moved)"), Row(3, "Chrome")];
        vm.RefreshWindows();
        Assert.AreEqual((nint)2, vm.SelectedWindow?.Handle, "같은 hwnd 는 새 목록에서 다시 선택돼야 한다");
        Assert.AreEqual("Blender (moved)", vm.SelectedWindow!.Info.Title, "새 목록의 줄을 가리켜야 한다");

        desktop.Rows = [Row(3, "Chrome")];
        vm.RefreshWindows();
        Assert.IsNull(vm.SelectedWindow, "사라진 창의 선택은 비워야 한다");
    }

    [TestMethod]
    public void Apply_refreshes_first_so_a_window_opened_after_the_last_refresh_is_included()
    {
        var desktop = new FakeDesktop(Row(1, "Notepad"));
        var vm = desktop.CreateViewModel(Profile("blender", "Blender", 10, 20, 800, 600));
        vm.RefreshWindows();

        // 마지막 새로고침 뒤에 뜬 창
        desktop.Rows = [Row(1, "Notepad"), Row(7, "Blender 5.2")];
        vm.SelectedProfile = vm.Profiles.Single();
        vm.ApplyProfileCommand.Execute(null);

        CollectionAssert.Contains(desktop.Operations.Moves, ((nint)7, new PixelRect(10, 20, 800, 600)));
        Assert.AreEqual("Status.Applied:blender", vm.Status);
    }

    [TestMethod]
    public void Apply_moves_every_matching_window_and_nothing_else_without_a_window_selection()
    {
        var desktop = new FakeDesktop(Row(1, "Blender A"), Row(2, "Notepad"), Row(3, "Blender B"));
        var vm = desktop.CreateViewModel(Profile("blender", "Blender", 0, 0, 640, 480));
        vm.SelectedProfile = vm.Profiles.Single();

        Assert.IsNull(vm.SelectedWindow);
        vm.ApplyProfileCommand.Execute(null);

        CollectionAssert.AreEquivalent(new nint[] { 1, 3 }, desktop.Operations.Moves.Select(m => m.Handle).ToArray());
    }

    [TestMethod]
    public void No_matching_window_is_reported_and_nothing_moves()
    {
        var desktop = new FakeDesktop(Row(1, "Notepad"));
        var vm = desktop.CreateViewModel(Profile("blender", "Blender", 0, 0, 640, 480));
        vm.SelectedProfile = vm.Profiles.Single();

        vm.ApplyProfileCommand.Execute(null);

        Assert.IsEmpty(desktop.Operations.Moves);
        Assert.AreEqual("Status.NoMatch:blender", vm.Status);
    }

    [TestMethod]
    public void Apply_command_needs_a_profile_selection_only()
    {
        var vm = new FakeDesktop().CreateViewModel(Profile("p", "x", 0, 0, 10, 10));

        Assert.IsFalse(vm.ApplyProfileCommand.CanExecute(null));
        vm.SelectedProfile = vm.Profiles.Single();
        Assert.IsTrue(vm.ApplyProfileCommand.CanExecute(null));
    }

    [TestMethod]
    public void Search_filters_by_title_or_process_ignoring_case()
    {
        var desktop = new FakeDesktop(Row(1, "Untitled - Notepad", "notepad.exe"), Row(2, "Scene", "blender.exe"));
        var vm = desktop.CreateViewModel();
        vm.RefreshWindows();

        vm.SearchText = "BLENDER";
        CollectionAssert.AreEqual(new nint[] { 2 }, vm.WindowsView.Cast<WindowRow>().Select(w => w.Handle).ToArray());

        vm.SearchText = "notepad";
        CollectionAssert.AreEqual(new nint[] { 1 }, vm.WindowsView.Cast<WindowRow>().Select(w => w.Handle).ToArray());

        vm.SearchText = "";
        Assert.AreEqual(2, vm.WindowsView.Cast<WindowRow>().Count());
    }

    [TestMethod]
    public void Navigation_switches_the_page()
    {
        var vm = new FakeDesktop().CreateViewModel();

        vm.NavigateCommand.Execute(AppPage.Settings);

        Assert.AreEqual(AppPage.Settings, vm.Page);
    }

    [TestMethod]
    public void Korean_and_english_string_resources_have_the_same_keys()
    {
        var ko = ResourceKeys("Strings.ko.xaml");
        var en = ResourceKeys("Strings.en.xaml");

        CollectionAssert.AreEquivalent(ko, en,
            "빠진 키 - en: " + string.Join(", ", ko.Except(en)) + " / ko: " + string.Join(", ", en.Except(ko)));
        Assert.IsNotEmpty(ko);
    }

    private static string[] ResourceKeys(string fileName)
    {
        var xaml = XNamespace.Get("http://schemas.microsoft.com/winfx/2006/xaml");
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
        {
            var path = Path.Combine(dir.FullName, "src", "WindowResizer.App", "Resources", fileName);
            if (File.Exists(path))
            {
                return XDocument.Load(path).Root!.Elements()
                    .Select(e => (string?)e.Attribute(xaml + "Key"))
                    .OfType<string>()
                    .ToArray();
            }
        }
        Assert.Fail(fileName + " 를 찾지 못했다");
        return Keys;
    }

    // --- S4b: 저장, 되돌리기, 삭제, 새 프로필, 편집 --------------------------------------

    [TestMethod]
    public void Apply_adds_one_per_applied_window_to_the_count_and_saves()
    {
        var desktop = new FakeDesktop(Row(1, "Blender A"), Row(2, "Blender B"));
        var vm = desktop.CreateViewModel(Profile("blender", "Blender", 0, 0, 640, 480));
        vm.SelectedProfile = vm.Profiles.Single();

        vm.ApplyProfileCommand.Execute(null);

        var saved = desktop.Document.Find("id-blender")!;
        Assert.AreEqual(2, saved.AppliedCount);
        Assert.AreEqual(FakeDesktop.Now, saved.LastAppliedAt);
        Assert.AreEqual(1, desktop.Saves);
        Assert.AreEqual("id-blender", vm.SelectedProfile?.Id, "저장 뒤에도 선택이 남아야 한다");
    }

    [TestMethod]
    public void Failed_save_restores_the_document_and_the_list_and_says_so()
    {
        var desktop = new FakeDesktop { SaveError = "disk full" };
        var vm = desktop.CreateViewModel(Profile("a", "x", 0, 0, 10, 10), Profile("b", "y", 0, 0, 10, 10));
        vm.SelectedProfile = vm.Profiles[0];

        vm.DeleteProfileCommand.Execute(null);

        Assert.HasCount(2, desktop.Document.Profiles);
        CollectionAssert.AreEqual(new[] { "a", "b" }, vm.Profiles.Select(p => p.Name).ToArray());
        Assert.AreEqual("Status.SaveFailed:disk full", vm.Status);
    }

    [TestMethod]
    public void Delete_asks_first_and_does_nothing_when_declined()
    {
        var desktop = new FakeDesktop();
        var vm = desktop.CreateViewModel(Profile("a", "x", 0, 0, 10, 10));
        vm.SelectedProfile = vm.Profiles.Single();

        desktop.Dialogs.ConfirmAnswer = false;
        vm.DeleteProfileCommand.Execute(null);
        Assert.AreEqual(1, vm.ProfileCount);
        Assert.AreEqual(0, desktop.Saves);

        desktop.Dialogs.ConfirmAnswer = true;
        vm.DeleteProfileCommand.Execute(null);
        Assert.AreEqual(0, vm.ProfileCount);
        Assert.IsNull(vm.SelectedProfile);
        Assert.AreEqual(1, desktop.Saves);
    }

    [TestMethod]
    public void New_profile_from_window_is_prefilled_named_after_the_program_and_saved_only_on_save()
    {
        var blender = new WindowRow(5, new WindowInfo("Scene - Blender 5.2", "blender.exe", "", @"C:\Blender\blender.exe"),
            100, new PixelRect(40, 50, 1200, 800), false, false);
        var desktop = new FakeDesktop(blender);
        var vm = desktop.CreateViewModel(Profile("Blender", "zzz", 0, 0, 10, 10));
        vm.RefreshWindows();
        vm.SelectedWindow = vm.Windows.Single();

        desktop.Dialogs.EditorAnswer = false;
        vm.NewProfileFromWindowCommand.Execute(null);
        Assert.HasCount(1, desktop.Document.Profiles, "취소하면 아무것도 안 생긴다");

        desktop.Dialogs.EditorAnswer = true;
        vm.NewProfileFromWindowCommand.Execute(null);

        var editor = desktop.Dialogs.LastEditor!;
        Assert.AreEqual(EditorPage.Position, editor.Page);
        Assert.AreEqual("Blender (2)", editor.Name, "같은 이름이 있으면 번호를 붙인다");
        Assert.AreEqual((40, 50, 1200, 800), (editor.X, editor.Y, editor.Width, editor.Height));
        Assert.AreEqual(MatchingStrategy.ExecutablePath, editor.Strategy);

        var created = desktop.Document.Profiles.Last().Value;
        Assert.AreEqual("Blender (2)", created.Name);
        Assert.AreEqual(@"C:\Blender\blender.exe", created.MatchingCriteria!.ExecutablePathPattern);
        Assert.AreEqual(vm.SelectedProfile?.Profile, created, "새 프로필이 선택돼야 한다");
    }

    [TestMethod]
    public void New_profile_from_a_window_parked_at_minus_32000_is_refused_without_opening_the_editor()
    {
        var desktop = new FakeDesktop(Row(5, "Blender"));
        desktop.Operations.Minimized = true;
        desktop.Operations.Placement = new WindowPlacement(new PixelRect(-32000, -32000, 160, 28), false);
        var vm = desktop.CreateViewModel();
        vm.RefreshWindows();
        vm.SelectedWindow = vm.Windows.Single();

        vm.NewProfileFromWindowCommand.Execute(null);

        Assert.IsNull(desktop.Dialogs.LastEditor);
        StringAssert.StartsWith(vm.Status, "Status.CaptureRefused:");
    }

    [TestMethod]
    public void Cancelled_edit_leaves_the_profile_untouched_and_saved_edit_keeps_unknown_fields()
    {
        var desktop = new FakeDesktop();
        var row = Profile("a", "x", 0, 0, 10, 10);
        row.Profile.Extra = new() { ["future_field"] = System.Text.Json.JsonDocument.Parse("42").RootElement };
        var vm = desktop.CreateViewModel(row);
        vm.SelectedProfile = vm.Profiles.Single();

        desktop.Dialogs.EditorAnswer = false;
        desktop.Dialogs.OnEditor = e => e.Name = "changed";
        vm.EditProfileCommand.Execute(null);
        Assert.AreEqual("a", desktop.Document.Find("id-a")!.Name);

        desktop.Dialogs.EditorAnswer = true;
        desktop.Dialogs.OnEditor = e => { e.Name = "renamed"; e.Width = 999; Assert.IsTrue(e.TrySave()); };
        vm.EditProfileCommand.Execute(null);

        var saved = desktop.Document.Find("id-a")!;
        Assert.AreEqual(("renamed", 999), (saved.Name, saved.WindowConfig!.Width));
        Assert.IsTrue(saved.Extra!.ContainsKey("future_field"), "편집 창이 모르는 키가 사라지면 안 된다");
        Assert.AreEqual("renamed", vm.SelectedProfile?.Name, "목록 행도 새 값이어야 한다");
    }

    [TestMethod]
    public void Editor_validation_blocks_save_and_jumps_to_the_page_with_the_problem()
    {
        var desktop = new FakeDesktop();
        var vm = desktop.CreateViewModel(Profile("a", "x", 0, 0, 10, 10), Profile("b", "y", 0, 0, 10, 10));
        var editor = vm.CreateEditor(ProfileJson.Clone(desktop.Document.Find("id-a")!), "id-a", EditorPage.Advanced);

        editor.Name = "B";
        Assert.IsFalse(editor.TrySave());
        Assert.AreEqual(("Editor.Error.NameTaken:{0}", EditorPage.General), (editor.Error, editor.Page));

        editor.Name = "a";
        editor.TitlePattern = "  ";
        Assert.IsFalse(editor.TrySave());
        Assert.AreEqual(EditorPage.Target, editor.Page);

        editor.TitlePattern = "x";
        editor.HotkeyEnabled = true;
        editor.HotkeyCombination = "Ctrl+";
        Assert.IsFalse(editor.TrySave());
        Assert.AreEqual(EditorPage.RunMethod, editor.Page);

        editor.HotkeyCombination = "Ctrl+Alt+E";
        Assert.IsTrue(editor.TrySave());
        Assert.AreEqual("", editor.Error);
    }

    [TestMethod]
    public void Capture_in_the_editor_uses_the_apply_matching_and_asks_when_several_windows_match()
    {
        var desktop = new FakeDesktop(
            Row(1, "Blender A") with { Rect = new PixelRect(1, 2, 300, 200) },
            Row(2, "Notepad"),
            Row(3, "Blender B") with { Rect = new PixelRect(7, 8, 900, 700) });
        var vm = desktop.CreateViewModel(Profile("b", "Blender", 0, 0, 10, 10));
        var editor = vm.CreateEditor(ProfileJson.Clone(desktop.Document.Find("id-b")!), "id-b", EditorPage.Position);

        desktop.Dialogs.Choose = candidates => candidates.Single(c => c.Handle == 3);
        editor.CaptureFromWindowCommand.Execute(null);

        CollectionAssert.AreEquivalent(new nint[] { 1, 3 }, desktop.Dialogs.LastCandidates!.Select(c => c.Handle).ToArray());
        Assert.AreEqual((7, 8, 900, 700), (editor.X, editor.Y, editor.Width, editor.Height));

        editor.TitlePattern = "nothing";
        editor.CaptureFromWindowCommand.Execute(null);
        Assert.AreEqual("Editor.Capture.NoMatch:{0}", editor.Message);
    }

    // --- S4b-4: 위치 덮어쓰기와 되돌리기 ---------------------------------------------------

    [TestMethod]
    public void Overwrite_needs_one_window_and_one_profile_and_changes_only_the_geometry()
    {
        var desktop = new FakeDesktop(Row(1, "Blender") with { Rect = new PixelRect(70, 80, 1100, 900) });
        var row = Profile("b", "Blender", 0, 0, 640, 480);
        row.Profile.WindowConfig!.AlwaysOnTop = true;
        var vm = desktop.CreateViewModel(row);
        vm.RefreshWindows();

        vm.SelectedProfile = vm.Profiles.Single();
        Assert.IsFalse(vm.OverwritePositionCommand.CanExecute(null), "창 선택이 없으면 꺼져 있다");
        vm.SelectedWindow = vm.Windows.Single();
        Assert.IsTrue(vm.OverwritePositionCommand.CanExecute(null));

        vm.OverwritePositionCommand.Execute(null);

        var config = desktop.Document.Find("id-b")!.WindowConfig!;
        Assert.AreEqual((70, 80, 1100, 900, true), (config.X, config.Y, config.Width, config.Height, config.AlwaysOnTop));
        Assert.IsTrue(vm.CanUndo);
        Assert.AreEqual("Status.PositionOverwritten:b", vm.Status);
    }

    [TestMethod]
    public void Undo_restores_the_old_geometry_and_survives_an_apply_but_not_an_edit()
    {
        var desktop = new FakeDesktop(Row(1, "Blender") with { Rect = new PixelRect(70, 80, 1100, 900) });
        var vm = desktop.CreateViewModel(Profile("b", "Blender", 5, 6, 640, 480));
        vm.RefreshWindows();
        vm.SelectedWindow = vm.Windows.Single();
        vm.SelectedProfile = vm.Profiles.Single();

        vm.OverwritePositionCommand.Execute(null);
        vm.ApplyProfileCommand.Execute(null);
        Assert.IsTrue(vm.CanUndo, "적용 횟수 저장은 되돌리기를 지우지 않는다");

        vm.UndoCommand.Execute(null);
        var config = desktop.Document.Find("id-b")!.WindowConfig!;
        Assert.AreEqual((5, 6, 640, 480), (config.X, config.Y, config.Width, config.Height));
        Assert.AreEqual(1, desktop.Document.Find("id-b")!.AppliedCount, "되돌리기는 위치만 되돌린다");
        Assert.IsFalse(vm.CanUndo);

        vm.OverwritePositionCommand.Execute(null);
        desktop.Dialogs.OnEditor = e => e.Description = "edited";
        vm.EditProfileCommand.Execute(null);
        Assert.IsFalse(vm.CanUndo, "다른 변경이 저장되면 되돌리기는 남의 변경을 덮으므로 사라진다");
    }

    [TestMethod]
    public void Failed_undo_changes_nothing_and_can_be_retried()
    {
        var desktop = new FakeDesktop(Row(1, "Blender") with { Rect = new PixelRect(70, 80, 1100, 900) });
        var vm = desktop.CreateViewModel(Profile("b", "Blender", 5, 6, 640, 480));
        vm.RefreshWindows();
        vm.SelectedWindow = vm.Windows.Single();
        vm.SelectedProfile = vm.Profiles.Single();
        vm.OverwritePositionCommand.Execute(null);

        desktop.SaveError = "locked";
        vm.UndoCommand.Execute(null);
        Assert.AreEqual(70, desktop.Document.Find("id-b")!.WindowConfig!.X);
        Assert.IsTrue(vm.CanUndo);

        desktop.SaveError = null;
        vm.UndoCommand.Execute(null);
        Assert.AreEqual(5, desktop.Document.Find("id-b")!.WindowConfig!.X);
    }

    // --- D-022: 읽지 못한 프로필 --------------------------------------------------------------

    [TestMethod]
    public void Unreadable_profile_is_listed_can_only_be_deleted_and_survives_other_saves()
    {
        var desktop = new FakeDesktop(Row(1, "Blender"));
        desktop.Document.Unreadable.Add(new UnreadableProfile("broken", """{ "name": "Old", "profile_type": "nope" }""", "bad enum"));
        var vm = desktop.CreateViewModel(Profile("a", "Blender", 0, 0, 10, 10));
        vm.RefreshWindows();
        vm.SelectedWindow = vm.Windows.Single();

        var broken = vm.Profiles.Single(p => p.IsUnreadable);
        Assert.AreEqual(("Old", "bad enum", "-"), (broken.Name, broken.Error, broken.Target));

        vm.SelectedProfile = broken;
        Assert.IsFalse(vm.ApplyProfileCommand.CanExecute(null));
        Assert.IsFalse(vm.EditProfileCommand.CanExecute(null));
        Assert.IsFalse(vm.OverwritePositionCommand.CanExecute(null));
        Assert.IsTrue(vm.DeleteProfileCommand.CanExecute(null));

        // 다른 프로필의 변경이 저장돼도 남는다.
        vm.SelectedProfile = vm.Profiles.Single(p => p.Id == "id-a");
        vm.ApplyProfileCommand.Execute(null);
        Assert.HasCount(1, desktop.Document.Unreadable);
        Assert.IsTrue(vm.Profiles.Any(p => p.IsUnreadable), "다시 만든 목록에도 흐린 줄이 있어야 한다");

        vm.SelectedProfile = vm.Profiles.Single(p => p.IsUnreadable);
        vm.DeleteProfileCommand.Execute(null);
        Assert.IsEmpty(desktop.Document.Unreadable);
        Assert.AreEqual("Status.ProfileDeleted:Old", vm.Status);
    }

    [TestMethod]
    public void Failed_save_also_restores_unreadable_profiles()
    {
        var desktop = new FakeDesktop { SaveError = "locked" };
        desktop.Document.Unreadable.Add(new UnreadableProfile("broken", """{ "name": "Old" }""", "x"));
        var vm = desktop.CreateViewModel();
        vm.SelectedProfile = vm.Profiles.Single();

        vm.DeleteProfileCommand.Execute(null);

        Assert.HasCount(1, desktop.Document.Unreadable);
        Assert.AreEqual(1, vm.ProfileCount);
    }

    private static WindowRow Row(nint handle, string title, string process = "app.exe") =>
        new(handle, new WindowInfo(Title: title, ProcessName: process), 100, new PixelRect(0, 0, 300, 200), false, false);

    private static ProfileRow Profile(string name, string titleContains, int x, int y, int w, int h) =>
        new("id-" + name, new Profile
        {
            Name = name,
            WindowConfig = new WindowConfiguration { X = x, Y = y, Width = w, Height = h },
            MatchingCriteria = new MatchingCriteria { Strategy = MatchingStrategy.TitleContains, WindowTitlePattern = titleContains },
        });

    private sealed class FakeDesktop
    {
        public const double Now = 1_800_000_000.5;

        public FakeDesktop(params WindowRow[] rows)
        {
            Rows = rows;
            Operations = new RecordingWindows(this);
        }

        public WindowRow[] Rows { get; set; }
        public RecordingWindows Operations { get; }
        public FakeDialogs Dialogs { get; } = new();
        public ProfileDocument Document { get; } = new();
        public string? SaveError { get; set; }
        public int Saves { get; private set; }

        public MainViewModel CreateViewModel(params ProfileRow[] profiles)
        {
            foreach (var p in profiles) Document.Profiles.Add(new(p.Id, p.Profile));
            return new(() => Rows, Operations, Document,
                _ => { if (SaveError is null) Saves++; return SaveError; },
                Dialogs, key => key + ":{0}", null, () => Now);
        }
    }

    private sealed class FakeDialogs : IDialogService
    {
        public bool ConfirmAnswer { get; set; } = true;
        public bool EditorAnswer { get; set; } = true;
        public Action<ProfileEditorViewModel>? OnEditor { get; set; }
        public Func<IReadOnlyList<WindowRow>, WindowRow?> Choose { get; set; } = c => c[0];
        public ProfileEditorViewModel? LastEditor { get; private set; }
        public IReadOnlyList<WindowRow>? LastCandidates { get; private set; }

        public bool ConfirmDelete(string profileName) => ConfirmAnswer;

        public bool ShowEditor(ProfileEditorViewModel editor)
        {
            LastEditor = editor;
            OnEditor?.Invoke(editor);
            // 실제 창과 같이 저장 버튼은 TrySave 가 통과해야 닫힌다.
            return EditorAnswer && editor.TrySave();
        }

        public WindowRow? ChooseWindow(IReadOnlyList<WindowRow> candidates)
        {
            LastCandidates = candidates;
            return Choose(candidates);
        }
    }

    private sealed class RecordingWindows(FakeDesktop desktop) : IWindowOperations
    {
        public List<(nint Handle, PixelRect Rect)> Moves { get; } = new();
        public bool Minimized { get; set; }
        public WindowPlacement? Placement { get; set; }

        public bool IsWindow(nint window) => true;
        public bool IsMaximized(nint window) => false;
        public bool IsMinimized(nint window) => Minimized;
        public PixelRect? GetRect(nint window) => desktop.Rows.FirstOrDefault(r => r.Handle == window)?.Rect;
        public WindowPlacement? GetPlacement(nint window) => Placement;
        public bool Restore(nint window) => true;
        public bool Maximize(nint window) => true;
        public bool Minimize(nint window) => true;
        public bool Move(nint window, PixelRect rect) { Moves.Add((window, rect)); return true; }
        public bool SetTopmost(nint window, bool topmost) => true;
    }
}
