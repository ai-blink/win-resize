using System.IO;
using System.Xml.Linq;
using WindowResizer.App.ViewModels;
using WindowResizer.Core.Hotkeys;
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
    public void Edit_by_id_opens_that_profile_whatever_is_selected_and_ignores_unknown_ids()
    {
        var desktop = new FakeDesktop();
        var vm = desktop.CreateViewModel(Profile("a", "x", 0, 0, 10, 10), Profile("b", "y", 5, 5, 20, 20));
        vm.SelectedProfile = vm.Profiles.Single(p => p.Id == "id-a");

        desktop.Dialogs.OnEditor = e => { e.Description = "from overlay"; Assert.IsTrue(e.TrySave()); };
        vm.EditProfile("id-b");

        Assert.AreEqual("from overlay", desktop.Document.Find("id-b")!.Description);
        Assert.AreNotEqual("from overlay", desktop.Document.Find("id-a")!.Description, "선택돼 있던 다른 프로필은 그대로여야 한다");

        desktop.Dialogs.OnEditor = _ => Assert.Fail("없는 id 는 편집 창을 열면 안 된다");
        vm.EditProfile("id-none");
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

    // --- 오버레이 O2 ------------------------------------------------------------------------

    [TestMethod]
    public void Overlay_settings_save_on_every_change_and_report_in_the_status_line()
    {
        var saved = new List<string>();
        var desktop = new FakeDesktop();
        var vm = desktop.CreateViewModel();
        var overlay = new OverlayViewModel(new Core.Overlay.OverlaySettings(), s => { saved.Add(s.ToValues()["interaction_mode"]); return null; },
            key => key + ":{0}", m => vm.ShowStatus(m));

        overlay.IsDwell = true;
        overlay.IsDwell = true;   // 같은 값은 저장하지 않는다
        Assert.IsFalse(overlay.IsClick);
        CollectionAssert.AreEqual(new[] { "dwell" }, saved);
        StringAssert.StartsWith(vm.Status, "Status.OverlayDwell:");

        overlay.DwellSeconds = 1.26;
        Assert.AreEqual(1300, overlay.Settings.DwellMs, "0.1초 단위로 맞춘다");
        overlay.DwellSeconds = 9;
        Assert.AreEqual(5000, overlay.Settings.DwellMs);
    }

    [TestMethod]
    public void Removing_the_switch_shows_hidden_buttons_so_they_can_come_back()
    {
        var changed = new List<string>();
        var overlay = new OverlayViewModel(new Core.Overlay.OverlaySettings(), _ => null, k => k, _ => { });
        overlay.Changed += changed.Add;
        overlay.ToggleVisible = true;
        overlay.Hidden = true;

        overlay.ToggleVisible = false;

        Assert.IsFalse(overlay.Hidden);
        CollectionAssert.Contains(changed, "Hidden", "버튼 창도 다시 보여야 하니 알린다");
    }

    [TestMethod]
    public void A_failed_settings_save_keeps_the_value_and_says_so()
    {
        var status = "";
        var overlay = new OverlayViewModel(new Core.Overlay.OverlaySettings(), _ => "denied", k => k + ":{0}", s => status = s);

        overlay.Locked = true;

        Assert.IsTrue(overlay.Locked);
        Assert.AreEqual("Status.SettingsSaveFailed:denied", status);
    }

    [TestMethod]
    public void Profile_overlay_switches_and_close_all_go_through_the_profile_file()
    {
        var desktop = new FakeDesktop();
        desktop.Document.Unreadable.Add(new UnreadableProfile("broken", """{ "name": "Old" }""", "x"));
        var vm = desktop.CreateViewModel(Profile("a", "x", 0, 0, 10, 10), Profile("b", "y", 0, 0, 10, 10));

        vm.SetProfileOverlayCommand.Execute(vm.Profiles.Single(p => p.Id == "id-a"));
        vm.SetProfileOverlayCommand.Execute(vm.Profiles.Single(p => p.Id == "id-b"));
        vm.SetProfileOverlay(vm.Profiles.Single(p => p.IsUnreadable), true);

        Assert.IsTrue(vm.Profiles.Where(p => !p.IsUnreadable).All(p => p.OverlayEnabled));
        Assert.IsFalse(vm.Profiles.Single(p => p.IsUnreadable).OverlayEnabled, "읽지 못한 프로필에는 버튼이 없다");
        Assert.AreEqual(2, desktop.Saves);

        vm.CloseAllOverlaysCommand.Execute(null);

        Assert.IsTrue(desktop.Document.Profiles.All(p => p.Value.OverlayStyle!.Enabled == false));
        Assert.AreEqual("Status.OverlayAllClosed:{0}", vm.Status);
        vm.CloseAllOverlaysCommand.Execute(null);
        Assert.AreEqual(3, desktop.Saves, "켜진 것이 없으면 저장하지 않는다");
    }

    // --- 오버레이 O3: 버튼이 누른 프로필을 직전 창에 ---------------------------------------------

    [TestMethod]
    public void Overlay_apply_ignores_matching_counts_the_window_and_keeps_the_undo()
    {
        var desktop = new FakeDesktop(Row(1, "Blender") with { Rect = new PixelRect(70, 80, 1100, 900) });
        var vm = desktop.CreateViewModel(Profile("b", "only-blender", 5, 6, 640, 480));
        vm.RefreshWindows();
        vm.SelectedWindow = vm.Windows.Single();
        vm.SelectedProfile = vm.Profiles.Single();
        vm.OverwritePositionCommand.Execute(null);

        var ok = vm.ApplyProfileToWindow("id-b", 42, "Untitled - Notepad");

        Assert.IsTrue(ok);
        Assert.AreEqual((nint)42, desktop.Operations.Moves.Last().Handle, "조건과 맞지 않는 창에도 적용한다(버튼의 뜻)");
        Assert.AreEqual(1, desktop.Document.Find("id-b")!.AppliedCount);
        Assert.AreEqual("Status.OverlayApplied:b", vm.Status);
        Assert.IsTrue(vm.CanUndo, "적용 횟수 저장은 되돌리기를 지우지 않는다");
    }

    [TestMethod]
    public void Overlay_apply_without_a_target_or_profile_fails_and_moves_nothing()
    {
        var desktop = new FakeDesktop();
        var vm = desktop.CreateViewModel(Profile("b", "x", 5, 6, 640, 480));

        Assert.IsFalse(vm.ApplyProfileToWindow("id-b", null, ""));
        Assert.AreEqual("Status.OverlayNoTarget:{0}", vm.Status);
        Assert.IsFalse(vm.ApplyProfileToWindow("gone", 42, "x"));
        Assert.IsEmpty(desktop.Operations.Moves);
        Assert.AreEqual(0, desktop.Saves);
    }

    // --- 단축키 페이지 (D-026) ---------------------------------------------------------------

    [TestMethod]
    public void Sync_registers_enabled_profile_hotkeys_and_lists_every_result_including_conflicts()
    {
        var desktop = new FakeDesktop();
        var registrar = desktop.UseHotkeys();
        registrar.ErrorFor = b => b.Text == "Ctrl+Alt+F2" ? 1409 : 0;
        var vm = desktop.CreateViewModel(HotkeyProfile("a", "Ctrl+Alt+F1"), HotkeyProfile("b", "Ctrl+Alt+F2"), HotkeyProfile("c", "nonsense"));

        vm.Hotkeys.Sync();

        CollectionAssert.AreEqual(new[] { "Ctrl+Alt+F1", "Ctrl+Alt+F2" }, registrar.Last.Select(b => b.Text).ToArray(),
            "잘못된 조합은 등록 대상에서 빠지고 나머지는 계속 등록한다");
        Assert.HasCount(3, vm.Hotkeys.Rows, "등록 둘 + 계획 단계에서 걸러진 하나가 모두 목록에 보여야 한다");
        Assert.IsFalse(vm.Hotkeys.Rows.Single(r => r.Text == "Ctrl+Alt+F1").IsProblem);
        Assert.StartsWith("Hotkeys.State.InUse", vm.Hotkeys.Rows.Single(r => r.Text == "Ctrl+Alt+F2").State);
        Assert.StartsWith("Hotkeys.State.Invalid", vm.Hotkeys.Rows.Single(r => r.Text == "nonsense").State);
    }

    [TestMethod]
    public void Saving_profile_hotkeys_persists_sets_mirrors_the_first_into_the_single_fields_and_registers_again()
    {
        var desktop = new FakeDesktop();
        var registrar = desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(Profile("p", "x", 0, 0, 10, 10));
        vm.Hotkeys.Sync();
        var before = registrar.Calls.Count;

        var saved = vm.SaveProfileHotkeys("id-p", true,
        [
            new HotkeySet { Enabled = true, Combination = "Ctrl+Alt+F5", Action = "release_profile" },
            new HotkeySet { Enabled = true, Combination = "Ctrl+Alt+F6", Action = "apply_profile" },
        ]);

        Assert.IsTrue(saved);
        var profile = desktop.Document.Find("id-p")!;
        Assert.IsTrue(profile.HotkeyEnabled);
        Assert.HasCount(2, profile.HotkeySets);
        Assert.AreEqual("Ctrl+Alt+F5", profile.HotkeyCombination);
        Assert.AreEqual("release_profile", profile.HotkeyAction);
        Assert.AreEqual(FakeDesktop.Now, profile.ModifiedAt);
        Assert.HasCount(before + 1, registrar.Calls, "저장하면 한 번 다시 등록한다");
        CollectionAssert.AreEqual(new[] { "Ctrl+Alt+F5", "Ctrl+Alt+F6" }, registrar.Last.Select(b => b.Text).ToArray());
        Assert.AreEqual("Status.HotkeysSaved:p", vm.Status);
    }

    [TestMethod]
    public void A_failed_save_of_profile_hotkeys_rolls_back_and_keeps_the_old_registration()
    {
        var desktop = new FakeDesktop();
        var registrar = desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(HotkeyProfile("a", "Ctrl+Alt+F1"));
        vm.Hotkeys.Sync();
        desktop.SaveError = "disk full";

        var saved = vm.SaveProfileHotkeys("id-a", true, [new HotkeySet { Enabled = true, Combination = "Ctrl+Alt+F9", Action = "apply_profile" }]);

        Assert.IsFalse(saved);
        Assert.AreEqual("Ctrl+Alt+F1", desktop.Document.Find("id-a")!.HotkeyCombination);
        CollectionAssert.AreEqual(new[] { "Ctrl+Alt+F1" }, registrar.Last.Select(b => b.Text).ToArray());
    }

    [TestMethod]
    public void Deleting_a_profile_drops_its_registration_and_unrelated_saves_leave_registration_alone()
    {
        var desktop = new FakeDesktop(Row(1, "blender"));
        var registrar = desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(HotkeyProfile("blender", "Ctrl+Alt+F1"), HotkeyProfile("b", "Ctrl+Alt+F2"));
        vm.Hotkeys.Sync();

        // 적용 횟수 저장은 단축키와 무관하다 - 눌러서 실행하는 도중에 등록을 지웠다 다시 하면 안 된다.
        var calls = registrar.Calls.Count;
        vm.SelectedProfile = vm.Profiles.First();
        vm.ApplyProfileCommand.Execute(null);
        Assert.HasCount(calls, registrar.Calls, "적용 횟수 저장이 등록을 건드렸다");

        vm.SelectedProfile = vm.Profiles.Single(p => p.Id == "id-b");
        vm.DeleteProfileCommand.Execute(null);
        CollectionAssert.AreEqual(new[] { "Ctrl+Alt+F1" }, registrar.Last.Select(b => b.Text).ToArray());
    }

    [TestMethod]
    public void Pressing_a_profile_hotkey_applies_it_on_the_ui_thread_without_moving_the_selection()
    {
        var desktop = new FakeDesktop(Row(1, "blender a"), Row(2, "Notepad"));
        var registrar = desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(HotkeyProfile("blender", "Ctrl+Alt+F1"), Profile("other", "Notepad", 1, 2, 30, 40));
        vm.Hotkeys.Sync();
        vm.SelectedProfile = vm.Profiles.Single(p => p.Id == "id-other");

        registrar.Press(b => b.Action == HotkeyAction.ApplyProfile);
        Assert.IsEmpty(desktop.Operations.Moves, "등록기 스레드에서 바로 실행하면 안 된다 - Post 를 거쳐야 한다");
        desktop.Drain();

        CollectionAssert.AreEqual(new nint[] { 1 }, desktop.Operations.Moves.Select(m => m.Handle).ToArray());
        Assert.AreEqual(1, desktop.Document.Find("id-blender")!.AppliedCount);
        Assert.AreEqual("id-other", vm.SelectedProfile?.Id, "단축키가 사용자의 선택을 옮겼다");
        Assert.AreEqual("Status.Applied:blender", vm.Status);
    }

    [TestMethod]
    public void Auto_apply_hotkey_flips_and_saves_the_flag_and_release_reports_that_nothing_is_locked()
    {
        var desktop = new FakeDesktop();
        var registrar = desktop.UseHotkeys();
        var profile = HotkeyProfile("p", "");
        profile.Profile.HotkeySets.Add(new HotkeySet { Enabled = true, Combination = "Ctrl+Alt+F1", Action = "auto_apply_toggle" });
        profile.Profile.HotkeySets.Add(new HotkeySet { Enabled = true, Combination = "Ctrl+Alt+F2", Action = "release_profile" });
        var vm = desktop.CreateViewModel(profile);
        vm.Hotkeys.Sync();

        registrar.Press(b => b.Action == HotkeyAction.AutoApplyToggle);
        desktop.Drain();
        Assert.IsTrue(desktop.Document.Find("id-p")!.AutoApply);
        Assert.AreEqual("Status.HotkeyAutoApplyOn:p", vm.Status);
        var saves = desktop.Saves;

        registrar.Press(b => b.Action == HotkeyAction.ReleaseProfile);
        desktop.Drain();
        Assert.AreEqual("Status.HotkeyNothingToRelease:p", vm.Status);
        Assert.AreEqual(saves, desktop.Saves, "풀 것이 없으면 아무것도 저장하지 않는다");
    }

    [TestMethod]
    public void Always_on_top_hotkey_toggles_the_foreground_window_not_a_profile()
    {
        var desktop = new FakeDesktop();
        var registrar = desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(HotkeyProfile("p", "Ctrl+Alt+F1", HotkeyAction.AlwaysOnTopToggle));
        vm.Hotkeys.Sync();

        desktop.TopmostResult = ("Some window", true, true);
        registrar.Press(b => b.Action == HotkeyAction.AlwaysOnTopToggle);
        desktop.Drain();
        Assert.AreEqual("Status.HotkeyTopmostOn:Some window", vm.Status);

        desktop.TopmostResult = null;
        registrar.Press(b => b.Action == HotkeyAction.AlwaysOnTopToggle);
        desktop.Drain();
        Assert.AreEqual("Status.HotkeyNoForeground:{0}", vm.Status);
    }

    [TestMethod]
    public void A_hotkey_for_a_profile_deleted_after_registration_reports_it_and_changes_nothing()
    {
        var desktop = new FakeDesktop(Row(1, "Blender"));
        var registrar = desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(HotkeyProfile("blender", "Ctrl+Alt+F1"));
        vm.Hotkeys.Sync();
        var stale = registrar.Last.Single();
        vm.SelectedProfile = vm.Profiles.Single();
        vm.DeleteProfileCommand.Execute(null);

        vm.RunHotkey(stale);

        Assert.AreEqual("Status.HotkeyProfileGone:{0}", vm.Status);
        Assert.IsEmpty(desktop.Operations.Moves);
    }

    [TestMethod]
    public void Apply_all_applies_every_profile_to_every_match_and_counts_each_profile()
    {
        var desktop = new FakeDesktop(Row(1, "Blender A"), Row(2, "Notepad"), Row(3, "Blender B"));
        var vm = desktop.CreateViewModel(Profile("blender", "Blender", 0, 0, 640, 480), Profile("note", "Notepad", 5, 5, 300, 200));

        vm.ApplyAllProfilesCommand.Execute(null);

        CollectionAssert.AreEquivalent(new nint[] { 1, 3, 2 }, desktop.Operations.Moves.Select(m => m.Handle).ToArray());
        Assert.AreEqual(2, desktop.Document.Find("id-blender")!.AppliedCount);
        Assert.AreEqual(1, desktop.Document.Find("id-note")!.AppliedCount);
        Assert.AreEqual("Status.AppliedAll:3", vm.Status);
        Assert.AreEqual(1, desktop.Saves, "횟수는 한 번에 저장한다");
    }

    [TestMethod]
    public void Apply_all_with_no_match_says_so_and_saves_nothing()
    {
        var desktop = new FakeDesktop(Row(1, "Chrome"));
        var vm = desktop.CreateViewModel(Profile("blender", "Blender", 0, 0, 640, 480));

        vm.ApplyAllProfilesCommand.Execute(null);

        Assert.AreEqual("Status.AppliedAllNone:{0}", vm.Status);
        Assert.AreEqual(0, desktop.Saves);
    }

    [TestMethod]
    public void Apply_all_hotkey_registers_first_runs_the_same_path_and_is_saved_even_when_registration_fails()
    {
        var desktop = new FakeDesktop(Row(1, "Blender A"));
        var registrar = desktop.UseHotkeys(new ApplyAllHotkey(true, "Ctrl+Alt+E"));
        var vm = desktop.CreateViewModel(Profile("blender", "Blender", 0, 0, 640, 480));
        vm.Hotkeys.Sync();
        Assert.AreEqual(HotkeyAction.ApplyAllProfiles, registrar.Last.First().Action);
        Assert.AreEqual("Hotkeys.State.Registered:{0}", vm.Hotkeys.ApplyAllState);

        registrar.Press(b => b.Action == HotkeyAction.ApplyAllProfiles);
        desktop.Drain();
        Assert.AreEqual((nint)1, desktop.Operations.Moves.Single().Handle, "버튼과 같은 전체 적용 경로다");

        registrar.ErrorFor = _ => 1409;
        registrar.ProbeErrorFor = _ => 1409;
        vm.Hotkeys.ApplyAll.Combination = "Ctrl+Alt+F3";
        vm.Hotkeys.ApplyAll.SaveCommand!.Execute(null);
        Assert.AreEqual(new ApplyAllHotkey(true, "Ctrl+Alt+F3"), desktop.SavedApplyAll.Last());
        Assert.AreEqual("Status.HotkeyApplyAllNotRegistered:{0}", vm.Status);
        Assert.HasCount(1, desktop.Dialogs.Warnings, "등록에 실패해도 저장은 하고, 경고 상자로 알린다");
        Assert.StartsWith("Hotkeys.Warn.Body", desktop.Dialogs.Warnings[0].Message);
        Assert.StartsWith("Hotkeys.Check.Blocked", vm.Hotkeys.ApplyAll.Problem);
        Assert.StartsWith("Hotkeys.State.InUse", vm.Hotkeys.ApplyAllState);
    }

    [TestMethod]
    public void Apply_all_hotkey_input_that_does_not_parse_is_refused_and_not_saved()
    {
        var desktop = new FakeDesktop();
        desktop.UseHotkeys();
        var vm = desktop.CreateViewModel();
        vm.Hotkeys.ApplyAll.Enabled = true;
        vm.Hotkeys.ApplyAll.Combination = "Ctrl+";

        vm.Hotkeys.ApplyAll.SaveCommand!.Execute(null);

        Assert.AreEqual("Hotkeys.Check.Invalid:{0}", vm.Hotkeys.ApplyAll.Problem);
        Assert.IsTrue(vm.Hotkeys.ApplyAll.HasProblem);
        Assert.IsEmpty(desktop.SavedApplyAll);
        Assert.IsEmpty(desktop.Dialogs.Warnings, "형식이 틀린 건 저장 자체를 막는다 - 팝업이 아니라 줄에 이유를 붙인다");
    }

    [TestMethod]
    public void The_hotkey_editor_reads_a_single_combination_as_the_first_set_and_each_row_saves_on_its_own()
    {
        var desktop = new FakeDesktop();
        desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(HotkeyProfile("p", "Ctrl+Alt+F1"));
        vm.Hotkeys.Sync();

        vm.Hotkeys.SelectedProfile = vm.Hotkeys.ProfileChoices.Single();
        Assert.IsTrue(vm.Hotkeys.ProfileHotkeysEnabled);
        Assert.AreEqual("Ctrl+Alt+F1", vm.Hotkeys.Sets[0].Combination);
        Assert.IsTrue(vm.Hotkeys.Sets[0].Enabled);
        Assert.IsFalse(vm.Hotkeys.Sets[1].Enabled);
        Assert.IsFalse(vm.Hotkeys.Sets[0].IsDirty, "읽어 온 값은 저장된 값이다");

        // 세트 2 와 3 을 고치되 세트 3 만 저장한다: 세트 2 의 초안은 저장되지도 지워지지도 않는다.
        vm.Hotkeys.Sets[1].Enabled = true;
        vm.Hotkeys.Sets[1].Combination = "Ctrl+Alt+F8";
        vm.Hotkeys.Sets[2].Enabled = true;
        vm.Hotkeys.Sets[2].Combination = "Ctrl+Alt+F9";
        vm.Hotkeys.Sets[2].Action = HotkeyAction.AlwaysOnTopToggle;
        Assert.IsTrue(vm.Hotkeys.Sets[1].IsDirty);

        vm.Hotkeys.Sets[2].SaveCommand!.Execute(null);

        var saved = desktop.Document.Find("id-p")!.HotkeySets;
        CollectionAssert.AreEqual(new[] { "Ctrl+Alt+F1", "Ctrl+Alt+F9" }, saved.Select(s => s.Combination).ToArray(), "저장 안 한 세트 2 는 문서에 없다");
        CollectionAssert.AreEqual(new[] { "apply_profile", "always_on_top_toggle" }, saved.Select(s => s.Action).ToArray());
        Assert.IsFalse(vm.Hotkeys.Sets[2].IsDirty);
        Assert.IsTrue(vm.Hotkeys.Sets[1].IsDirty, "다른 줄의 저장 안 한 변경은 남는다");
        Assert.AreEqual("Ctrl+Alt+F8", vm.Hotkeys.Sets[1].Combination);
        Assert.AreEqual("id-p", vm.Hotkeys.SelectedProfile?.Id, "저장 뒤에도 같은 프로필이 선택돼 있어야 한다");

        vm.Hotkeys.Sets[1].SaveCommand!.Execute(null);
        CollectionAssert.AreEqual(new[] { "Ctrl+Alt+F1", "Ctrl+Alt+F8", "Ctrl+Alt+F9" },
            desktop.Document.Find("id-p")!.HotkeySets.Select(s => s.Combination).ToArray());
    }

    [TestMethod]
    public void Unsaved_edits_survive_an_unrelated_save_but_an_outside_change_reloads_the_rows()
    {
        var desktop = new FakeDesktop(Row(1, "p"));
        desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(HotkeyProfile("p", "Ctrl+Alt+F1"));
        vm.Hotkeys.Sync();
        vm.Hotkeys.SelectedProfile = vm.Hotkeys.ProfileChoices.Single();
        vm.Hotkeys.Sets[1].Enabled = true;
        vm.Hotkeys.Sets[1].Combination = "Ctrl+Alt+F8";

        // 적용 횟수 저장은 단축키와 무관하다 - 고치는 중인 값을 지우면 안 된다.
        vm.SelectedProfile = vm.Profiles.Single();
        vm.ApplyProfileCommand.Execute(null);
        Assert.AreEqual("Ctrl+Alt+F8", vm.Hotkeys.Sets[1].Combination);
        Assert.IsTrue(vm.Hotkeys.Sets[1].IsDirty);

        // 편집 창 같은 바깥 변경으로 세트가 바뀌면 문서 값으로 다시 읽는다.
        vm.SaveProfileHotkeys("id-p", true, [new HotkeySet { Enabled = true, Combination = "Ctrl+Alt+F5", Action = "apply_profile" }]);
        Assert.AreEqual("Ctrl+Alt+F5", vm.Hotkeys.Sets[0].Combination);
        Assert.AreEqual("", vm.Hotkeys.Sets[1].Combination);
        Assert.IsFalse(vm.Hotkeys.Sets[1].IsDirty);
    }

    [TestMethod]
    public void Every_edit_is_checked_at_once_and_a_bad_combination_gets_a_reason_on_its_row()
    {
        var desktop = new FakeDesktop();
        var registrar = desktop.UseHotkeys(new ApplyAllHotkey(true, "Ctrl+Alt+E"));
        registrar.ProbeErrorFor = c => c == HotkeyCombination.Parse("Win+L") ? 1409 : c == HotkeyCombination.Parse("Ctrl+Alt+F7") ? 5 : 0;
        var vm = desktop.CreateViewModel(HotkeyProfile("p", "Ctrl+Alt+F1"));
        vm.Hotkeys.Sync();
        vm.Hotkeys.SelectedProfile = vm.Hotkeys.ProfileChoices.Single();
        var row = vm.Hotkeys.Sets[1];
        row.Enabled = true;

        row.Combination = "Ctrl+Alt+F2";
        Assert.IsFalse(row.HasProblem);

        row.Combination = "Win+L";
        Assert.StartsWith("Hotkeys.Check.Blocked", row.Problem, "다른 프로그램이나 Windows 가 쓰는 조합");

        row.Combination = "Ctrl+Alt+F7";
        Assert.AreEqual("Hotkeys.Check.Failed:5", row.Problem);

        row.Combination = "Ctrl+Alt";
        Assert.StartsWith("Hotkeys.Check.Invalid", row.Problem, "주 키가 없는 덜 쓴 조합");

        row.Combination = "Ctrl+Alt+E";
        Assert.AreEqual("Hotkeys.Check.Duplicate:Hotkeys.ApplyAll.Label:{0}", row.Problem, "전체 적용 단축키와 겹친다");
        Assert.IsTrue(vm.Hotkeys.ApplyAll.HasProblem, "겹치면 양쪽 줄에 다 이유가 붙는다");

        row.Enabled = false;
        Assert.IsFalse(row.HasProblem, "꺼진 줄은 검사하지 않는다");
        Assert.IsFalse(vm.Hotkeys.ApplyAll.HasProblem, "겹침이 사라지면 상대 줄도 풀린다");
    }

    [TestMethod]
    public void Saving_a_combination_that_cannot_be_registered_keeps_it_and_warns_with_the_reason()
    {
        var desktop = new FakeDesktop();
        var registrar = desktop.UseHotkeys();
        registrar.ErrorFor = _ => 1409;
        registrar.ProbeErrorFor = _ => 1409;
        var vm = desktop.CreateViewModel(Profile("p", "x", 0, 0, 10, 10));
        vm.Hotkeys.Sync();
        vm.Hotkeys.SelectedProfile = vm.Hotkeys.ProfileChoices.Single();
        vm.Hotkeys.ProfileHotkeysEnabled = true;
        var row = vm.Hotkeys.Sets[0];
        row.Enabled = true;
        row.Combination = "Ctrl+Alt+F5";

        row.SaveCommand!.Execute(null);

        Assert.AreEqual("Ctrl+Alt+F5", desktop.Document.Find("id-p")!.HotkeySets.Single().Combination, "PyQt5 처럼 등록에 실패해도 저장은 한다");
        Assert.IsTrue(row.HasProblem, "빨간 테두리가 남는다");
        var warning = desktop.Dialogs.Warnings.Single();
        Assert.AreEqual("Hotkeys.Warn.Title:{0}", warning.Title);
        Assert.StartsWith("Hotkeys.Warn.Body", warning.Message);
        Assert.StartsWith("Hotkeys.Check.Blocked", row.Problem, "경고에 쓰이는 이유가 줄에도 그대로 붙어 있다");
    }

    [TestMethod]
    public void The_profile_master_switch_saves_at_once_and_is_undone_if_the_save_fails()
    {
        var desktop = new FakeDesktop();
        desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(HotkeyProfile("p", "Ctrl+Alt+F1"));
        vm.Hotkeys.Sync();
        vm.Hotkeys.SelectedProfile = vm.Hotkeys.ProfileChoices.Single();

        vm.Hotkeys.ProfileHotkeysEnabled = false;
        Assert.IsFalse(desktop.Document.Find("id-p")!.HotkeyEnabled);

        desktop.SaveError = "disk full";
        vm.Hotkeys.ProfileHotkeysEnabled = true;
        Assert.IsFalse(vm.Hotkeys.ProfileHotkeysEnabled, "저장에 실패하면 스위치를 되돌린다");
        Assert.IsFalse(desktop.Document.Find("id-p")!.HotkeyEnabled);
    }

    [TestMethod]
    public void The_hotkey_editor_refuses_a_bad_combination_and_writes_nothing()
    {
        var desktop = new FakeDesktop();
        desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(Profile("p", "x", 0, 0, 10, 10));
        vm.Hotkeys.Sync();
        vm.Hotkeys.SelectedProfile = vm.Hotkeys.ProfileChoices.Single();
        vm.Hotkeys.ProfileHotkeysEnabled = true;
        var saves = desktop.Saves;
        vm.Hotkeys.Sets[0].Enabled = true;
        vm.Hotkeys.Sets[0].Combination = "Ctrl+Ctrl+A";

        vm.Hotkeys.Sets[0].SaveCommand!.Execute(null);

        Assert.AreEqual("Hotkeys.Error.SetInvalid:Ctrl+Ctrl+A", vm.Status);
        Assert.IsTrue(vm.Hotkeys.Sets[0].HasProblem);
        Assert.AreEqual(saves, desktop.Saves);
    }

    [TestMethod]
    public void The_profile_list_shows_the_first_registered_shortcut_from_sets()
    {
        var withSets = HotkeyProfile("a", "");
        withSets.Profile.HotkeySets.Add(new HotkeySet { Enabled = false, Combination = "Ctrl+F1", Action = "apply_profile" });
        withSets.Profile.HotkeySets.Add(new HotkeySet { Enabled = true, Combination = "Ctrl+F2", Action = "apply_profile" });
        var off = HotkeyProfile("b", "Ctrl+F3");
        off.Profile.HotkeyEnabled = false;

        Assert.AreEqual("Ctrl+F2", withSets.Hotkey);
        Assert.AreEqual("-", off.Hotkey);
    }

    [TestMethod]
    public void Registrations_are_released_while_a_hotkey_box_has_focus_and_come_back_after()
    {
        var desktop = new FakeDesktop();
        var registrar = desktop.UseHotkeys(new ApplyAllHotkey(true, "Ctrl+Alt+E"));
        var vm = desktop.CreateViewModel(HotkeyProfile("a", "Ctrl+Alt+F1"));
        vm.Hotkeys.Sync();
        Assert.HasCount(2, registrar.Last, "전체 적용 + 프로필 하나");

        // 등록된 조합을 다시 누르려면 등록이 먼저 키를 잡아 가면 안 된다.
        vm.Hotkeys.SetCapturing(true);
        Assert.IsEmpty(registrar.Last);

        // 입력 중에 문서가 바뀌어도(다른 저장) 등록을 되살리지 않는다.
        vm.SaveProfileHotkeys("id-a", true, [new HotkeySet { Enabled = true, Combination = "Ctrl+Alt+F2", Action = "apply_profile" }]);
        Assert.IsEmpty(registrar.Last);

        vm.Hotkeys.SetCapturing(false);
        CollectionAssert.AreEqual(new[] { "Ctrl+Alt+E", "Ctrl+Alt+F2" }, registrar.Last.Select(b => b.Text).ToArray());
    }

    [TestMethod]
    public void Registrations_are_released_while_the_profile_editor_is_open()
    {
        var desktop = new FakeDesktop();
        var registrar = desktop.UseHotkeys();
        var vm = desktop.CreateViewModel(HotkeyProfile("a", "Ctrl+Alt+F1"));
        vm.Hotkeys.Sync();
        vm.SelectedProfile = vm.Profiles.Single();

        IReadOnlyList<HotkeyBinding>? whileOpen = null;
        desktop.Dialogs.OnEditor = _ => whileOpen = registrar.Last;
        vm.EditProfileCommand.Execute(null);

        Assert.IsNotNull(whileOpen);
        Assert.IsEmpty(whileOpen, "편집 창이 열린 동안에는 등록이 풀려 있어야 한다");
        CollectionAssert.AreEqual(new[] { "Ctrl+Alt+F1" }, registrar.Last.Select(b => b.Text).ToArray(), "닫으면 되살아난다");
    }

    private static ProfileRow HotkeyProfile(string name, string combination, HotkeyAction action = HotkeyAction.ApplyProfile)
    {
        var row = Profile(name, name, 10, 20, 800, 600);
        row.Profile.HotkeyEnabled = true;
        row.Profile.HotkeyCombination = combination;
        row.Profile.HotkeyAction = HotkeyActions.ToKey(action);
        return row;
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

        public HotkeyServices? Hotkeys { get; private set; }
        public List<ApplyAllHotkey> SavedApplyAll { get; } = new();
        public (string Title, bool Topmost, bool Succeeded)? TopmostResult { get; set; }
        private readonly Queue<Action> _posted = new();

        /// <summary>단축키 가짜를 붙인다. 등록기가 알리는 일은 <see cref="Drain"/> 을 불러야 UI 스레드에서 실행된다.</summary>
        public FakeRegistrar UseHotkeys(ApplyAllHotkey? applyAll = null)
        {
            var registrar = new FakeRegistrar();
            Hotkeys = new HotkeyServices(registrar, applyAll,
                hotkey => { SavedApplyAll.Add(hotkey); return null; },
                () => TopmostResult,
                _posted.Enqueue);
            return registrar;
        }

        /// <summary>UI 스레드로 넘어온 일을 실행한다.</summary>
        public void Drain()
        {
            while (_posted.Count > 0) _posted.Dequeue()();
        }

        public MainViewModel CreateViewModel(params ProfileRow[] profiles)
        {
            foreach (var p in profiles) Document.Profiles.Add(new(p.Id, p.Profile));
            return new(() => Rows, Operations, Document,
                _ => { if (SaveError is null) Saves++; return SaveError; },
                Dialogs, key => key + ":{0}", null, () => Now, hotkeys: Hotkeys);
        }
    }

    private sealed class FakeRegistrar : IHotkeyRegistrar
    {
        public event Action<HotkeyBinding>? Activated;
        public List<IReadOnlyList<HotkeyBinding>> Calls { get; } = new();
        public Func<HotkeyBinding, int> ErrorFor { get; set; } = _ => 0;
        public Func<HotkeyCombination, int> ProbeErrorFor { get; set; } = _ => 0;

        private HashSet<HotkeyCombination> _registered = new();

        /// <summary>실제 등록기와 같이, 자기가 <b>등록에 성공한</b> 조합만 0 이다(실패한 시도는 남의 것으로 본다).</summary>
        public int Probe(HotkeyCombination combination) => _registered.Contains(combination) ? 0 : ProbeErrorFor(combination);
        public IReadOnlyList<HotkeyBinding> Last => Calls[^1];

        public IReadOnlyList<HotkeyRegistration> Replace(IReadOnlyList<HotkeyBinding> bindings)
        {
            Calls.Add(bindings.ToList());
            _registered = bindings.Where(b => ErrorFor(b) == 0).Select(b => b.Combination).ToHashSet();
            return bindings.Select(b => new HotkeyRegistration(b, ErrorFor(b) == 0, ErrorFor(b))).ToList();
        }

        /// <summary>등록된 것 중 조건에 맞는 단축키를 누른다(등록기 스레드에서 알리는 것과 같다).</summary>
        public void Press(Func<HotkeyBinding, bool> which) => Activated?.Invoke(Last.First(which));
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

        public List<(string Title, string Message)> Warnings { get; } = new();

        public void Warn(string title, string message) => Warnings.Add((title, message));

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

        public bool CopyToClipboard(string text) => true;

        public string? ChooseSaveFile(string title, string suggestedFileName, string filter) => null;

        public string? OpenFolder(string path) => null;
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
