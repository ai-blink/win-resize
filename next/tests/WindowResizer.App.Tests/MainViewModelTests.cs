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

    private static WindowRow Row(nint handle, string title, string process = "app.exe") =>
        new(handle, new WindowInfo(Title: title, ProcessName: process), 100, new PixelRect(0, 0, 300, 200), false, false);

    private static ProfileRow Profile(string name, string titleContains, int x, int y, int w, int h) =>
        new("id-" + name, new Profile
        {
            Name = name,
            WindowConfig = new WindowConfiguration { X = x, Y = y, Width = w, Height = h },
            MatchingCriteria = new MatchingCriteria { Strategy = MatchingStrategy.TitleContains, WindowTitlePattern = titleContains },
        });

    private sealed class FakeDesktop(params WindowRow[] rows)
    {
        public WindowRow[] Rows { get; set; } = rows;
        public RecordingWindows Operations { get; } = new();

        public MainViewModel CreateViewModel(params ProfileRow[] profiles) =>
            new(() => Rows, Operations, profiles, key => key + ":{0}", null);
    }

    private sealed class RecordingWindows : IWindowOperations
    {
        public List<(nint Handle, PixelRect Rect)> Moves { get; } = new();

        public bool IsWindow(nint window) => true;
        public bool IsMaximized(nint window) => false;
        public bool IsMinimized(nint window) => false;
        public PixelRect? GetRect(nint window) => null;
        public bool Restore(nint window) => true;
        public bool Maximize(nint window) => true;
        public bool Minimize(nint window) => true;
        public bool Move(nint window, PixelRect rect) { Moves.Add((window, rect)); return true; }
        public bool SetTopmost(nint window, bool topmost) => true;
    }
}
