using WindowResizer.Core.Profiles;
using WindowResizer.Core.Windowing;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.Infrastructure.Tests;

/// <summary>
/// S3 게이트: 실제 Notepad 창이 프로필 사각형에 실제로 도착하는가.
/// "API 가 성공을 돌려줬다"는 통과가 아니다 - 적용 뒤 OS 가 보고하는 사각형을 잰다.
///
/// 안전 규칙:
/// - 이 테스트가 띄운 창만 만진다. 실행 전 창 목록을 떠 두고 새로 생긴 Notepad 창만 고른다.
///   Win11 Notepad 가 새 창 대신 기존 창에 탭을 열면 새 창이 없다 - 그때는 기존 창을
///   건드리지 않고 Inconclusive 로 끝낸다.
/// - 끝나면 그 창에만 닫기를 요청한다.
/// </summary>
[TestClass]
[DoNotParallelize]
public sealed class NotepadLiveSmokeTests
{
    private static readonly Win32Windows Windows = new();

    [TestMethod]
    [TestCategory("Gate")]
    [TestCategory("Live")]
    public void Profile_geometry_lands_on_a_real_notepad_window_including_from_maximized()
    {
        var primary = Windows.EnumerateMonitors().Single(m => m.IsPrimary);
        var target = new PixelRect(primary.WorkArea.X + 120, primary.WorkArea.Y + 90, 820, 610);
        var config = new WindowConfiguration { X = target.X, Y = target.Y, Width = target.Width, Height = target.Height };
        var applier = new ProfileApplier(Windows);

        using var notepad = OwnNotepad.Launch(Windows);
        var window = notepad.Window;
        {
            // 1. 일반 상태에서 적용
            Assert.AreEqual(ApplyOutcome.Applied, applier.Apply(window.Handle, config));
            AssertLandsOn(window.Handle, target, "일반 상태에서 적용");

            // 2. 최대화된 창에 적용 - 먼저 복원돼야 좌표가 먹는다
            Assert.IsTrue(Windows.Maximize(window.Handle), "스모크 준비: 최대화 실패");
            Assert.AreEqual(ApplyOutcome.Applied, applier.Apply(window.Handle, config));
            Assert.IsFalse(Windows.IsMaximized(window.Handle), "최대화 상태가 남았다");
            AssertLandsOn(window.Handle, target, "최대화 상태에서 적용");

            // 3. 매칭: 실행 파일 경로로 이 창을 찾는다
            var criteria = new MatchingCriteria
            {
                Strategy = MatchingStrategy.ExecutablePath,
                ExecutablePathPattern = window.Info.ExecutablePath,
            };
            Assert.IsTrue(criteria.Matches(window.Info), "실행 파일 경로 매칭 실패: " + window.Info.ExecutablePath);

            // 4. 항상 위 켜고 끄기가 실제 창 스타일에 반영된다
            Assert.IsTrue(Windows.SetTopmost(window.Handle, true));
            Assert.IsTrue(Windows.SetTopmost(window.Handle, false));
        }
    }

    /// <summary>
    /// D-021 게이트: 최대화/최소화된 실제 창을 떠도 일반 위치가 나오고 -32000 이 나오지 않는다.
    /// 작업 영역 좌표 변환이 틀리면 일반 상태의 캡처와 최대화 상태의 캡처가 어긋난다.
    /// </summary>
    [TestMethod]
    [TestCategory("Gate")]
    [TestCategory("Live")]
    public void Capture_returns_the_normal_placement_of_a_real_window_in_every_state()
    {
        var primary = Windows.EnumerateMonitors().Single(m => m.IsPrimary);
        var target = new PixelRect(primary.WorkArea.X + 140, primary.WorkArea.Y + 110, 760, 540);

        using var notepad = OwnNotepad.Launch(Windows);
        var handle = notepad.Handle;
        Assert.AreEqual(ApplyOutcome.Applied, new ProfileApplier(Windows).Apply(handle,
            new WindowConfiguration { X = target.X, Y = target.Y, Width = target.Width, Height = target.Height }));
        AssertLandsOn(handle, target, "캡처 준비");

        AssertCaptured(handle, target, maximized: false, "일반 상태");

        Assert.IsTrue(Windows.Minimize(handle), "스모크 준비: 최소화 실패");
        AssertCaptured(handle, target, maximized: false, "일반에서 최소화");

        Assert.IsTrue(Windows.Restore(handle), "스모크 준비: 복원 실패");
        Assert.IsTrue(Windows.Maximize(handle), "스모크 준비: 최대화 실패");
        AssertCaptured(handle, target, maximized: true, "최대화");

        Assert.IsTrue(Windows.Minimize(handle), "스모크 준비: 최소화 실패");
        AssertCaptured(handle, target, maximized: true, "최대화에서 최소화");
    }

    private static void AssertCaptured(nint handle, PixelRect expected, bool maximized, string step)
    {
        var result = WindowCapture.Capture(Windows, handle);
        Assert.IsTrue(result.Succeeded, $"{step}: 캡처 거절 {result.Refusal}");
        var c = result.Configuration!;
        Assert.AreEqual(expected, new PixelRect(c.X, c.Y, c.Width, c.Height), $"{step}: 사각형");
        Assert.AreEqual(maximized, c.IsMaximized, $"{step}: 최대화 플래그");
    }

    private static void AssertLandsOn(nint handle, PixelRect expected, string step)
    {
        // 다른 프로세스 창이라 반영이 한 박자 늦을 수 있다. 짧게 기다리며 잰다.
        PixelRect? actual = null;
        for (var i = 0; i < 20; i++)
        {
            actual = Windows.GetRect(handle);
            if (actual == expected) return;
            Thread.Sleep(50);
        }
        Assert.Fail($"{step}: 창이 {expected} 가 아니라 {actual} 에 있다");
    }

}
