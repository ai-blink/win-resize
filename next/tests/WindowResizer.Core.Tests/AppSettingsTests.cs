using WindowResizer.Core.Settings;

namespace WindowResizer.Core.Tests;

/// <summary>앱 설정(설정 페이지)의 값 규칙, PyQt5 가져오기 해석, 창 위치 보정.</summary>
[TestClass]
public sealed class AppSettingsTests
{
    [TestMethod]
    [DataRow(0, 75)]
    [DataRow(74, 75)]
    [DataRow(75, 75)]
    [DataRow(77, 75)]
    [DataRow(78, 80)]
    [DataRow(100, 100)]
    [DataRow(122, 120)]
    [DataRow(123, 125)]
    [DataRow(999, 250)]
    [DataRow(230, 230)]
    public void Scale_is_clamped_and_rounded_to_five_percent_steps(int input, int expected)
    {
        Assert.AreEqual(expected, AppSettings.NormalizeScale(input));
    }

    [TestMethod]
    public void A_nan_scale_falls_back_to_the_default()
    {
        Assert.AreEqual(AppSettings.DefaultScalePercent, AppSettings.NormalizeScale(double.NaN));
    }

    [TestMethod]
    public void Defaults_follow_the_system_in_korean_at_one_hundred_percent_and_remember_the_window()
    {
        var settings = AppSettings.FromValues(new Dictionary<string, string>());

        Assert.AreEqual(ThemeChoice.System, settings.Theme);
        Assert.AreEqual(100, settings.ScalePercent);
        Assert.AreEqual("ko", settings.Language);
        Assert.IsTrue(settings.RememberWindow);
        Assert.IsNull(settings.Window);
    }

    [TestMethod]
    public void Values_round_trip_including_the_window()
    {
        var original = new AppSettings
        {
            Theme = ThemeChoice.Dark,
            ScalePercent = 115,
            Language = "en",
            RememberWindow = false,
            Window = new SavedWindowBounds(-1200, 40, 1100, 700, Maximized: true),
        };

        var read = AppSettings.FromValues(original.ToValues());

        Assert.AreEqual(ThemeChoice.Dark, read.Theme);
        Assert.AreEqual(115, read.ScalePercent);
        Assert.AreEqual("en", read.Language);
        Assert.IsFalse(read.RememberWindow);
        Assert.AreEqual(original.Window, read.Window);
    }

    [TestMethod]
    public void Unknown_language_theme_and_broken_numbers_fall_back_to_defaults()
    {
        var read = AppSettings.FromValues(new Dictionary<string, string>
        {
            ["theme"] = "purple",
            ["language"] = "xx",
            ["scale_percent"] = "big",
            ["window_left"] = "1", ["window_top"] = "2", ["window_width"] = "x", ["window_height"] = "4",
        });

        Assert.AreEqual(ThemeChoice.System, read.Theme);
        Assert.AreEqual("ko", read.Language);
        Assert.AreEqual(100, read.ScalePercent);
        Assert.IsNull(read.Window, "폭이 숫자가 아니면 창 값 전체를 쓰지 않는다");
    }

    [TestMethod]
    public void The_pc_pyqt5_values_import_as_follow_system_and_seventy_five_percent()
    {
        // 이 PC 의 실제 값: theme=dark, color_scheme=Dark, follow_system=true / scale_percent=75.
        var settings = AppSettings.FromPyQt5(
            new Dictionary<string, string> { ["theme"] = "dark", ["color_scheme"] = "Dark", ["follow_system"] = "true" },
            new Dictionary<string, string>
            {
                ["scale_percent"] = "75", ["main_window_size"] = "@Size(920 640)", ["main_window_position"] = "@Point(507 531)",
            });

        Assert.AreEqual(ThemeChoice.System, settings.Theme);
        Assert.AreEqual(75, settings.ScalePercent);
        Assert.IsNull(settings.Window, "Qt 논리 픽셀 창 자리는 가져오지 않는다");
    }

    [TestMethod]
    public void A_fixed_pyqt5_theme_imports_as_that_theme_and_the_high_contrast_scheme_follows_the_system()
    {
        static ThemeChoice Import(string theme) => AppSettings.FromPyQt5(
            new Dictionary<string, string> { ["theme"] = theme, ["follow_system"] = "false" }, null).Theme;

        Assert.AreEqual(ThemeChoice.Dark, Import("dark"));
        Assert.AreEqual(ThemeChoice.Light, Import("light"));
        Assert.AreEqual(ThemeChoice.System, Import("custom"));
    }

    [TestMethod]
    public void Only_one_of_the_two_pyqt5_keys_present_still_imports_that_part()
    {
        var scaleOnly = AppSettings.FromPyQt5(null, new Dictionary<string, string> { ["scale_percent"] = "90" });
        Assert.AreEqual(ThemeChoice.System, scaleOnly.Theme);
        Assert.AreEqual(90, scaleOnly.ScalePercent);
    }

    [TestMethod]
    public void A_window_inside_the_screen_stays_where_it_is()
    {
        var saved = new SavedWindowBounds(100, 80, 1200, 700, Maximized: false);

        Assert.AreEqual(saved, saved.Fit(0, 0, 3840, 2160, 980, 560));
    }

    [TestMethod]
    public void A_window_left_on_a_removed_monitor_is_moved_back_onto_the_screen()
    {
        // 두 번째 모니터(오른쪽, x 1920~3839)를 뺐다. 가상 화면은 1920x1080 하나다.
        var saved = new SavedWindowBounds(2500, 300, 1200, 700, Maximized: false);

        var fit = saved.Fit(0, 0, 1920, 1080, 980, 560);

        Assert.AreEqual(720, fit.Left, "오른쪽 끝이 화면 끝에 닿게 밀어 넣는다");
        Assert.AreEqual(300, fit.Top);
        Assert.AreEqual(1200, fit.Width);
    }

    [TestMethod]
    public void A_window_larger_than_the_screen_shrinks_but_never_below_the_minimum()
    {
        var saved = new SavedWindowBounds(-50, -50, 4000, 3000, Maximized: false);

        var fit = saved.Fit(0, 0, 1600, 900, 980, 560);

        Assert.AreEqual(new SavedWindowBounds(0, 0, 1600, 900, false), fit);
    }

    [TestMethod]
    public void A_window_smaller_than_the_minimum_grows_to_it()
    {
        var saved = new SavedWindowBounds(10, 10, 300, 200, Maximized: false);

        var fit = saved.Fit(0, 0, 1920, 1080, 980, 560);

        Assert.AreEqual(980, fit.Width);
        Assert.AreEqual(560, fit.Height);
    }

    [TestMethod]
    public void A_left_monitor_with_negative_coordinates_is_a_valid_place()
    {
        var saved = new SavedWindowBounds(-1500, 100, 1200, 700, Maximized: false);

        Assert.AreEqual(saved, saved.Fit(-1920, 0, 3840, 1080, 980, 560));
    }
}
