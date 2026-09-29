using WindowResizer.App.ViewModels;
using WindowResizer.Core.Settings;

namespace WindowResizer.App.Tests;

/// <summary>설정 페이지의 화면 쪽 규칙: 바꾸면 바로 저장하고 알린다, 화면 크기는 끄는 동안 숫자만.</summary>
[TestClass]
public sealed class SettingsViewModelTests
{
    private sealed class Harness
    {
        public AppSettings Settings { get; } = new();
        public List<string> Changes { get; } = [];
        public List<string> Statuses { get; } = [];
        public int Saves { get; private set; }
        public string? SaveError { get; set; }
        public bool Startup { get; set; }
        public string? StartupError { get; set; }
        public SettingsViewModel Vm { get; }

        public Harness()
        {
            Vm = new SettingsViewModel(
                Settings,
                _ => { Saves++; return SaveError; },
                () => Startup,
                enabled => { if (StartupError is null) Startup = enabled; return StartupError; },
                key => key,
                Statuses.Add);
            Vm.Changed += Changes.Add;
        }
    }

    [TestMethod]
    public void Picking_a_theme_saves_and_announces_it_once_and_moves_the_cards()
    {
        var h = new Harness();

        h.Vm.IsThemeDark = true;

        Assert.AreEqual(ThemeChoice.Dark, h.Settings.Theme);
        CollectionAssert.AreEqual(new[] { "Theme" }, h.Changes);
        Assert.AreEqual(1, h.Saves);
        Assert.IsTrue(h.Vm.IsThemeDark);
        Assert.IsFalse(h.Vm.IsThemeSystem);
        Assert.AreEqual("Status.ThemeDark", h.Statuses.Single());
    }

    [TestMethod]
    public void Picking_the_theme_that_is_already_set_does_nothing()
    {
        var h = new Harness();

        h.Vm.IsThemeSystem = true;
        h.Vm.IsThemeDark = false;

        Assert.AreEqual(0, h.Saves);
        Assert.IsEmpty(h.Changes);
    }

    [TestMethod]
    public void Moving_the_slider_without_dragging_applies_at_once()
    {
        var h = new Harness();

        h.Vm.ScalePercent = 115;

        Assert.AreEqual(115, h.Settings.ScalePercent);
        CollectionAssert.AreEqual(new[] { "AppliedScale" }, h.Changes);
        Assert.AreEqual("Status.Scale", h.Statuses.Single());
    }

    [TestMethod]
    public void While_dragging_only_the_number_changes_and_letting_go_applies()
    {
        var h = new Harness();
        h.Vm.BeginScaleDrag();

        h.Vm.ScalePercent = 80;
        h.Vm.ScalePercent = 125;

        Assert.AreEqual(100, h.Settings.ScalePercent, "끄는 도중에는 적용하지 않는다");
        Assert.IsEmpty(h.Changes);
        Assert.AreEqual(0, h.Saves);
        Assert.AreEqual("125%", h.Vm.ScaleText);

        h.Vm.EndScaleDrag();

        Assert.AreEqual(125, h.Settings.ScalePercent);
        CollectionAssert.AreEqual(new[] { "AppliedScale" }, h.Changes);
        Assert.AreEqual(1, h.Saves);
    }

    [TestMethod]
    public void Dragging_back_to_the_applied_value_applies_nothing()
    {
        var h = new Harness();
        h.Vm.BeginScaleDrag();
        h.Vm.ScalePercent = 120;
        h.Vm.ScalePercent = 100;

        h.Vm.EndScaleDrag();

        Assert.IsEmpty(h.Changes);
        Assert.AreEqual(0, h.Saves);
    }

    [TestMethod]
    public void The_slider_value_snaps_to_the_scale_steps_and_the_range()
    {
        var h = new Harness();

        h.Vm.ScalePercent = 999;
        Assert.AreEqual(125, h.Settings.ScalePercent);

        h.Vm.ScalePercent = 3;
        Assert.AreEqual(75, h.Settings.ScalePercent);
    }

    [TestMethod]
    public void Reset_goes_back_to_one_hundred_percent()
    {
        var h = new Harness();
        h.Vm.ScalePercent = 75;

        h.Vm.ResetScaleCommand.Execute(null);

        Assert.AreEqual(100, h.Settings.ScalePercent);
    }

    [TestMethod]
    public void Changing_the_language_announces_before_the_status_text_is_made()
    {
        // App 이 알림을 받아 리소스 사전을 바꾼 뒤에야 상태 문구를 만들어야 새 언어로 나온다.
        var settings = new AppSettings();
        var order = new List<string>();
        var vm = new SettingsViewModel(settings, _ => null, () => false, _ => null, k => { order.Add("text:" + k); return k; }, _ => order.Add("status"));
        vm.Changed += _ => order.Add("changed");

        vm.Language = "en";

        CollectionAssert.AreEqual(new[] { "changed", "text:Status.Language", "status" }, order);
        Assert.AreEqual("en", settings.Language);
    }

    [TestMethod]
    public void An_unknown_language_is_refused()
    {
        var h = new Harness();

        h.Vm.Language = "xx";

        Assert.AreEqual("ko", h.Settings.Language);
        Assert.IsEmpty(h.Changes);
    }

    [TestMethod]
    public void A_failed_save_keeps_the_value_and_says_so()
    {
        var h = new Harness { SaveError = "disk" };

        h.Vm.IsThemeLight = true;

        Assert.AreEqual(ThemeChoice.Light, h.Settings.Theme, "설정은 되돌리지 않는다 - 다음 저장이 다시 시도한다");
        Assert.AreEqual("Status.SettingsSaveFailed", h.Statuses.Single());
    }

    [TestMethod]
    public void The_startup_checkbox_follows_the_registration_not_our_own_copy()
    {
        var h = new Harness { Startup = true };
        var vm = new SettingsViewModel(h.Settings, _ => null, () => h.Startup, e => { h.Startup = e; return null; }, k => k, _ => { });
        Assert.IsTrue(vm.StartWithWindows);

        h.Startup = false; // 작업 관리자에서 껐다
        vm.RefreshStartup();

        Assert.IsFalse(vm.StartWithWindows);
    }

    [TestMethod]
    public void Opening_the_settings_page_rereads_the_startup_registration()
    {
        var startup = true;
        var main = new MainViewModel(() => [], null!, new WindowResizer.Core.Profiles.ProfileDocument(), _ => null, null!, k => k,
            settings: new SettingsServices(new AppSettings(), _ => null, () => startup, _ => null));
        Assert.IsTrue(main.Settings.StartWithWindows);

        startup = false; // 작업 관리자에서 껐다
        main.Page = AppPage.Settings;

        Assert.IsFalse(main.Settings.StartWithWindows);
    }

    [TestMethod]
    public void Turning_startup_on_registers_and_a_failure_leaves_it_off()
    {
        var h = new Harness();
        h.Vm.StartWithWindows = true;
        Assert.IsTrue(h.Startup);
        Assert.AreEqual("Status.StartupOn", h.Statuses.Last());

        var failing = new Harness { StartupError = "denied" };
        failing.Vm.StartWithWindows = true;
        Assert.IsFalse(failing.Vm.StartWithWindows);
        Assert.AreEqual("Status.StartupFailed", failing.Statuses.Single());
        Assert.AreEqual(0, failing.Saves, "시작 등록은 우리 설정 키에 복사하지 않는다");
    }

    [TestMethod]
    public void Remembering_the_window_saves_bounds_only_while_on_and_off_forgets_them()
    {
        var h = new Harness();
        var bounds = new SavedWindowBounds(10, 20, 1000, 700, false);

        h.Vm.RememberBounds(bounds);
        Assert.AreEqual(bounds, h.Settings.Window);
        Assert.AreEqual(1, h.Saves);

        h.Vm.RememberBounds(bounds);
        Assert.AreEqual(1, h.Saves, "같은 자리는 다시 쓰지 않는다");

        h.Vm.RememberWindow = false;
        Assert.IsNull(h.Settings.Window);

        h.Vm.RememberBounds(bounds);
        Assert.IsNull(h.Settings.Window, "기억하지 않기로 했으면 적지 않는다");
    }
}
