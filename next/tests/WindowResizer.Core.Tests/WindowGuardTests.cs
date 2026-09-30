using WindowResizer.Core.Profiles;
using WindowResizer.Core.Windowing;

namespace WindowResizer.Core.Tests;

[TestClass]
public sealed class WindowGuardTests
{
    private sealed class FakeWindows : IWindowOperations
    {
        public Dictionary<nint, PixelRect> Rects { get; } = new();
        public HashSet<nint> Maximized { get; } = new();
        public HashSet<nint> Minimized { get; } = new();
        public HashSet<nint> Refusing { get; } = new();   // Move does nothing (admin window)
        public int Moves { get; private set; }

        public bool IsWindow(nint window) => Rects.ContainsKey(window);
        public bool IsMaximized(nint window) => Maximized.Contains(window);
        public bool IsMinimized(nint window) => Minimized.Contains(window);
        public PixelRect? GetRect(nint window) => Rects.TryGetValue(window, out var r) ? r : null;
        public WindowPlacement? GetPlacement(nint window) => null;
        public bool Restore(nint window) => true;
        public bool Maximize(nint window) => true;
        public bool Minimize(nint window) => true;
        public bool SetTopmost(nint window, bool topmost) => true;

        public bool Move(nint window, PixelRect rect)
        {
            Moves++;
            if (Refusing.Contains(window)) return false;
            Rects[window] = rect;
            return true;
        }
    }

    private sealed class FakeCursor : ICursorConfiner
    {
        public PixelRect? Clip { get; private set; }
        public int Confines { get; private set; }
        public PixelRect? Current() => Clip ?? new PixelRect(0, 0, 3840, 2160);
        public bool Confine(PixelRect rect) { Clip = rect; Confines++; return true; }
        public bool Release() { Clip = null; return true; }
    }

    private sealed class Harness
    {
        public FakeWindows Windows { get; } = new();
        public FakeCursor Cursor { get; } = new();
        public nint Foreground { get; set; }
        public HashSet<int> KeysDown { get; } = new();
        public List<GuardNotice> Notices { get; } = new();
        public WindowGuard Guard { get; }

        public Harness()
        {
            Guard = new WindowGuard(Windows, Cursor, () => Foreground, KeysDown.Contains);
            Guard.Notice += Notices.Add;
        }
    }

    private static readonly PixelRect Target = new(100, 100, 800, 600);

    private static Profile Locked(Action<Profile>? tweak = null)
    {
        var p = new Profile { Name = "Locked", LockPosition = true };
        tweak?.Invoke(p);
        return p;
    }

    [TestMethod]
    public void A_locked_window_dragged_beyond_the_tolerance_is_put_back_and_small_drifts_are_left()
    {
        var h = new Harness();
        h.Windows.Rects[1] = Target;
        h.Guard.Engage(1, "p", Locked(), Target);

        h.Windows.Rects[1] = Target with { X = 103 };      // 오차 5px 안
        h.Guard.Tick();
        Assert.AreEqual(0, h.Windows.Moves);

        h.Windows.Rects[1] = Target with { X = 400, Y = 300 };
        h.Guard.Tick();
        Assert.AreEqual(Target, h.Windows.Rects[1]);
        Assert.AreEqual(1, h.Windows.Moves);
    }

    [TestMethod]
    public void A_resize_puts_back_the_whole_place_and_the_restore_switches_are_honoured()
    {
        var h = new Harness();
        h.Windows.Rects[1] = Target;
        h.Guard.Engage(1, "p", Locked(), Target);
        h.Windows.Rects[1] = Target with { Width = 1200 };
        h.Guard.Tick();
        Assert.AreEqual(Target, h.Windows.Rects[1]);

        var off = new Harness();
        off.Windows.Rects[1] = Target;
        off.Guard.Engage(1, "p", Locked(p => p.AutoRestore = new AutoRestore { RestoreOnMove = false }), Target);
        off.Windows.Rects[1] = Target with { X = 900 };
        off.Guard.Tick();
        Assert.AreEqual(0, off.Windows.Moves, "restore_on_move 가 꺼져 있으면 옮겨도 그대로 둔다");
    }

    [TestMethod]
    public void Maximized_and_minimized_windows_are_left_alone()
    {
        var h = new Harness();
        h.Windows.Rects[1] = Target;
        h.Guard.Engage(1, "p", Locked(), Target);

        h.Windows.Rects[1] = new PixelRect(0, 0, 3840, 2160);
        h.Windows.Maximized.Add(1);
        h.Guard.Tick();
        h.Windows.Maximized.Clear();
        h.Windows.Minimized.Add(1);
        h.Windows.Rects[1] = new PixelRect(-32000, -32000, 160, 28);
        h.Guard.Tick();

        Assert.AreEqual(0, h.Windows.Moves);
    }

    [TestMethod]
    public void A_window_that_cannot_be_moved_is_given_up_after_the_max_attempts_and_reported_once()
    {
        var h = new Harness();
        h.Windows.Rects[1] = Target;
        h.Windows.Refusing.Add(1);
        h.Guard.Engage(1, "p", Locked(p => p.AutoRestore = new AutoRestore { MaxAttempts = 3 }), Target);
        h.Windows.Rects[1] = Target with { X = 900 };

        for (var i = 0; i < 10; i++) h.Guard.Tick();

        Assert.AreEqual(3, h.Windows.Moves, "세 번 시도하고 그만둔다");
        Assert.HasCount(1, h.Notices);
        Assert.AreEqual(GuardNoticeKind.LockGaveUp, h.Notices[0].Kind);
        Assert.AreEqual(0, h.Guard.Count, "가둠도 없으니 이 창은 더 지키지 않는다");
    }

    [TestMethod]
    public void Unlimited_attempts_back_off_instead_of_hammering_a_window_that_refuses()
    {
        var h = new Harness();
        h.Windows.Rects[1] = Target with { X = 900 };
        h.Windows.Refusing.Add(1);
        h.Guard.Engage(1, "p", Locked(p => p.AutoRestore = new AutoRestore { MaxAttempts = -1 }), Target);

        for (var i = 0; i < 40; i++) h.Guard.Tick();

        Assert.IsLessThan(20, h.Windows.Moves, "실패가 이어지면 검사 간격이 늘어난다");
        Assert.IsEmpty(h.Notices, "무제한이면 포기하지 않는다");
    }

    [TestMethod]
    public void Engaging_a_profile_without_locks_releases_the_old_ones_and_release_by_profile_counts_windows()
    {
        var h = new Harness();
        h.Windows.Rects[1] = Target;
        h.Windows.Rects[2] = Target;
        h.Guard.Engage(1, "p", Locked(), Target);
        h.Guard.Engage(2, "p", Locked(), Target);
        Assert.AreEqual(2, h.Guard.Count);

        h.Guard.Engage(1, "other", new Profile { Name = "plain" }, Target);
        Assert.AreEqual(1, h.Guard.Count);

        Assert.AreEqual(1, h.Guard.Release("p"));
        Assert.AreEqual(0, h.Guard.Count);
        h.Windows.Rects[2] = Target with { X = 900 };
        h.Guard.Tick();
        Assert.AreEqual(0, h.Windows.Moves, "풀린 창은 더 되돌리지 않는다");
    }

    [TestMethod]
    public void The_cursor_is_confined_only_while_the_window_is_in_front_and_confined_again_when_it_returns()
    {
        var h = new Harness();
        h.Windows.Rects[1] = Target;
        h.Guard.Engage(1, "p", new Profile { Name = "c", MouseConstraint = true, ConstraintEscapeKey = "" }, Target);

        h.Foreground = 99;
        h.Guard.Tick();
        Assert.IsNull(h.Cursor.Clip, "다른 창이 앞이면 가두지 않는다");

        h.Foreground = 1;
        h.Guard.Tick();
        Assert.AreEqual(Target, h.Cursor.Clip);

        h.Guard.Tick();
        Assert.AreEqual(1, h.Cursor.Confines, "같은 사각형이면 다시 걸지 않는다");

        h.Windows.Rects[1] = Target with { X = 300 };
        h.Guard.Tick();
        Assert.AreEqual(Target with { X = 300 }, h.Cursor.Clip, "창이 옮겨지면 새 사각형으로 가둔다");

        h.Foreground = 99;
        h.Guard.Tick();
        Assert.IsNull(h.Cursor.Clip, "전경을 잃으면 푼다");

        h.Foreground = 1;
        h.Guard.Tick();
        Assert.IsNotNull(h.Cursor.Clip, "돌아오면 다시 가둔다");
    }

    [TestMethod]
    public void The_escape_key_frees_the_cursor_until_the_profile_is_applied_again()
    {
        var h = new Harness();
        h.Windows.Rects[1] = Target;
        var profile = new Profile { Name = "c", MouseConstraint = true, ConstraintEscapeKey = "Escape" };
        h.Guard.Engage(1, "p", profile, Target);
        h.Foreground = 1;
        h.Guard.Tick();
        Assert.IsNotNull(h.Cursor.Clip);

        h.KeysDown.Add(0x1B);
        h.Guard.Tick();
        h.KeysDown.Clear();
        Assert.IsNull(h.Cursor.Clip);
        Assert.AreEqual(GuardNoticeKind.ConstraintEscaped, h.Notices.Single().Kind);

        h.Guard.Tick();
        Assert.IsNull(h.Cursor.Clip, "탈출한 뒤에는 다시 가두지 않는다");

        h.Guard.Engage(1, "p", profile, Target);
        h.Guard.Tick();
        Assert.IsNotNull(h.Cursor.Clip, "다시 적용하면 가둔다");
    }

    [TestMethod]
    public void A_closed_window_frees_the_cursor_and_release_all_frees_everything()
    {
        var h = new Harness();
        h.Windows.Rects[1] = Target;
        h.Guard.Engage(1, "p", new Profile { Name = "c", MouseConstraint = true, ConstraintEscapeKey = "" }, Target);
        h.Foreground = 1;
        h.Guard.Tick();
        Assert.IsNotNull(h.Cursor.Clip);

        h.Windows.Rects.Remove(1);
        h.Guard.Tick();
        Assert.IsNull(h.Cursor.Clip);
        Assert.AreEqual(0, h.Guard.Count);

        h.Windows.Rects[2] = Target;
        h.Guard.Engage(2, "p", new Profile { Name = "c", MouseConstraint = true, ConstraintEscapeKey = "" }, Target);
        h.Foreground = 2;
        h.Guard.Tick();
        h.Guard.ReleaseAll();
        Assert.IsNull(h.Cursor.Clip);
    }

    [TestMethod]
    public void An_unreadable_escape_key_means_no_escape_key_rather_than_a_crash()
    {
        var h = new Harness();
        h.Windows.Rects[1] = Target;
        h.Guard.Engage(1, "p", new Profile { Name = "c", MouseConstraint = true, ConstraintEscapeKey = "not a key" }, Target);
        h.Foreground = 1;
        h.KeysDown.Add(0x1B);

        h.Guard.Tick();

        Assert.IsNotNull(h.Cursor.Clip);
        Assert.IsEmpty(h.Notices);
    }
}
