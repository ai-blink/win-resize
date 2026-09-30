using WindowResizer.Core.Profiles;
using WindowResizer.Core.Windowing;

namespace WindowResizer.Core.Tests;

[TestClass]
public sealed class AutoApplyMonitorTests
{
    private sealed class Harness
    {
        public List<WindowSnapshot> Windows { get; } = new();
        public double Now { get; set; } = 1000;
        public List<(nint Handle, string Id)> Applies { get; } = new();
        public List<AutoApplyResult> Results { get; } = new();
        public Func<nint, string, bool> Succeeds { get; set; } = (_, _) => true;
        public AutoApplyMonitor Monitor { get; }

        public Harness()
        {
            Monitor = new AutoApplyMonitor(() => Windows.ToList(), (h, id, _) => { Applies.Add((h, id)); return Succeeds(h, id); }, () => Now);
            Monitor.Applied += Results.Add;
        }

        public void Open(nint handle, string title, string process = "app.exe") =>
            Windows.Add(new WindowSnapshot(handle, new WindowInfo(title, process, "", @"C:\apps\" + process), new PixelRect(0, 0, 800, 600), false));

        public void Advance(double seconds)
        {
            Now += seconds;
            Monitor.Tick();
        }
    }

    private static (string Id, Profile Profile) AutoProfile(string id, string name, MatchingStrategy strategy, string pattern,
        double delay = 2, int retries = 3, double retryDelay = 0.5, int priority = 50)
    {
        var criteria = new MatchingCriteria { Strategy = strategy, ApplyDelay = delay, MaxRetries = retries, RetryDelay = retryDelay, Priority = priority };
        switch (strategy)
        {
            case MatchingStrategy.ProcessName: criteria.ProcessNamePattern = pattern; break;
            case MatchingStrategy.ExecutablePath: criteria.ExecutablePathPattern = pattern; break;
            default: criteria.WindowTitlePattern = pattern; break;
        }
        return (id, new Profile
        {
            Name = name, AutoApply = true, MatchingCriteria = criteria,
            WindowConfig = new WindowConfiguration { X = 1, Y = 2, Width = 300, Height = 200 },
        });
    }

    [TestMethod]
    public void Windows_open_when_monitoring_starts_are_the_baseline_and_only_new_ones_are_applied()
    {
        var h = new Harness();
        h.Open(1, "Blender old");
        h.Monitor.SetProfiles([AutoProfile("b", "Blender", MatchingStrategy.TitleContains, "Blender")]);

        h.Advance(10);
        Assert.IsEmpty(h.Applies, "감시를 켤 때 이미 있던 창은 건드리지 않는다");

        h.Open(2, "Blender new");
        h.Advance(1);
        Assert.IsEmpty(h.Applies, "적용 지연(기본 2초)이 지나기 전에는 적용하지 않는다");
        h.Advance(2);
        CollectionAssert.AreEqual(new[] { ((nint)2, "b") }, h.Applies);
        Assert.IsTrue(h.Results.Single().Success);

        h.Advance(30);
        Assert.HasCount(1, h.Applies, "한 번 적용한 창은 사라질 때까지 다시 적용하지 않는다");
    }

    [TestMethod]
    public void The_profiles_own_delay_and_retry_settings_are_used()
    {
        var h = new Harness();
        h.Monitor.SetProfiles([AutoProfile("b", "B", MatchingStrategy.TitleContains, "Blender", delay: 5, retries: 3, retryDelay: 2)]);
        h.Succeeds = (_, _) => false;
        h.Open(1, "Blender");

        h.Advance(1);   // 발견
        h.Advance(3);   // 4초: 아직 5초 전
        Assert.IsEmpty(h.Applies);
        h.Advance(2);   // 6초: 첫 시도
        Assert.HasCount(1, h.Applies);
        h.Advance(1);   // 재시도 간격 2초 전
        Assert.HasCount(1, h.Applies);
        h.Advance(2);
        Assert.HasCount(2, h.Applies);
        h.Advance(2);
        Assert.HasCount(3, h.Applies);
        h.Advance(10);

        Assert.HasCount(3, h.Applies, "시도는 max_retries 번까지다");
        Assert.IsFalse(h.Results.Single().Success, "다 실패하면 실패로 알린다");
    }

    [TestMethod]
    public void Only_the_most_specific_matching_profile_is_applied()
    {
        var h = new Harness();
        h.Monitor.SetProfiles(
        [
            AutoProfile("title", "Loose", MatchingStrategy.TitleContains, "Blender"),
            AutoProfile("path", "Exact", MatchingStrategy.ExecutablePath, @"C:\apps\blender.exe"),
            AutoProfile("proc", "Process", MatchingStrategy.ProcessName, "blender.exe"),
        ]);
        h.Open(1, "Blender", "blender.exe");   // 세 프로필이 다 맞는다
        h.Advance(1);
        h.Advance(3);

        CollectionAssert.AreEqual(new[] { ((nint)1, "path") }, h.Applies);
    }

    [TestMethod]
    public void Ties_go_to_the_higher_priority_then_the_name()
    {
        var h = new Harness();
        h.Monitor.SetProfiles(
        [
            AutoProfile("a", "Alpha", MatchingStrategy.TitleContains, "App", priority: 50),
            AutoProfile("b", "Beta", MatchingStrategy.TitleContains, "App", priority: 80),
        ]);
        h.Open(1, "App main");
        h.Advance(1);
        h.Advance(3);

        Assert.AreEqual("b", h.Applies.Single().Id);
    }

    [TestMethod]
    public void The_title_is_matched_at_apply_time_because_programs_set_it_late()
    {
        var h = new Harness();
        h.Monitor.SetProfiles([AutoProfile("b", "B", MatchingStrategy.TitleContains, "Blender")]);
        h.Open(1, "Starting...");
        h.Advance(1);
        h.Advance(3);
        Assert.IsEmpty(h.Applies);

        h.Windows[0] = h.Windows[0] with { Info = new WindowInfo("Blender 5.2", "app.exe", "", @"C:\apps\app.exe") };
        h.Advance(1);
        Assert.HasCount(1, h.Applies);
    }

    [TestMethod]
    public void Small_untitled_minimized_and_unmatched_windows_are_never_applied_and_a_reused_handle_counts_as_new()
    {
        var h = new Harness();
        h.Monitor.SetProfiles([AutoProfile("b", "B", MatchingStrategy.TitleContains, "App")]);
        h.Windows.Add(new WindowSnapshot(1, new WindowInfo("App tiny"), new PixelRect(0, 0, 50, 50), false));
        h.Windows.Add(new WindowSnapshot(2, new WindowInfo("A"), new PixelRect(0, 0, 800, 600), false));
        h.Windows.Add(new WindowSnapshot(3, new WindowInfo("App mini"), new PixelRect(-32000, -32000, 800, 600), true));
        h.Open(4, "Other window");
        h.Advance(1);
        h.Advance(5);
        Assert.IsEmpty(h.Applies);

        h.Windows.Clear();
        h.Open(5, "App one");
        h.Advance(1);
        h.Advance(3);
        Assert.HasCount(1, h.Applies);

        h.Windows.Clear();
        h.Advance(1);            // 창이 사라졌다
        h.Open(5, "App one");    // 같은 핸들이 다시 쓰였다
        h.Advance(1);
        h.Advance(3);
        Assert.HasCount(2, h.Applies);
    }

    [TestMethod]
    public void No_auto_apply_profiles_stops_monitoring_and_profiles_without_a_place_do_not_count()
    {
        var h = new Harness();
        var noPlace = AutoProfile("n", "N", MatchingStrategy.TitleContains, "x");
        noPlace.Profile.WindowConfig = null;
        var off = AutoProfile("o", "O", MatchingStrategy.TitleContains, "x");
        off.Profile.AutoApply = false;

        h.Monitor.SetProfiles([noPlace, off]);
        Assert.AreEqual(0, h.Monitor.ProfileCount);
        Assert.IsFalse(h.Monitor.IsRunning);

        h.Monitor.SetProfiles([AutoProfile("b", "B", MatchingStrategy.TitleContains, "x")]);
        Assert.IsTrue(h.Monitor.IsRunning);
        h.Monitor.SetProfiles([]);
        Assert.IsFalse(h.Monitor.IsRunning);
    }

    [TestMethod]
    public void Changing_the_profile_list_while_running_keeps_the_baseline()
    {
        var h = new Harness();
        h.Open(1, "App old");
        h.Monitor.SetProfiles([AutoProfile("a", "A", MatchingStrategy.TitleContains, "App")]);
        h.Monitor.SetProfiles([AutoProfile("a", "A", MatchingStrategy.TitleContains, "App"), AutoProfile("z", "Z", MatchingStrategy.TitleContains, "Zed")]);

        h.Advance(1);
        h.Advance(5);

        Assert.IsEmpty(h.Applies, "프로필을 편집했다고 이미 열린 창이 새 창이 되지는 않는다");
    }
}
