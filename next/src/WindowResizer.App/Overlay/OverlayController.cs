using System.Collections.Specialized;
using System.Windows.Threading;
using WindowResizer.App.ViewModels;
using WindowResizer.Core.Overlay;
using WindowResizer.Core.Windowing;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.App.Overlay;

/// <summary>
/// 오버레이 버튼 창들의 주인(PyQt5 main_window 의 오버레이 부분). 두 원천만 따른다:
/// <list type="bullet">
/// <item>무엇을 띄울지 - 프로필의 <c>overlay_style.enabled</c>(<see cref="MainViewModel.Profiles"/>). 편집 창, 오버레이
///   페이지, 우클릭 닫기, 모두 닫기가 전부 프로필을 바꾸고, 여기는 그 목록에 맞춰 창을 만들거나 닫는다.</item>
/// <item>어떻게 - 전역 설정(<see cref="OverlayViewModel"/>). 감추기, 잠금, 발동 방식, 드웰 시간.</item>
/// </list>
/// 자리는 설정의 배치에서 가져오고, 없거나 지금 화면 밖이면 오른쪽 아래 계단식 기본 자리다(D-023).
/// </summary>
public sealed class OverlayController : IDisposable
{
    private readonly MainViewModel _main;
    private readonly ForegroundTracker _tracker;
    private readonly Func<string, string> _text;
    private readonly Win32Windows _windows = new();
    private readonly Dictionary<string, OverlayButtonWindow> _buttons = new();
    private bool _reconcileQueued;
    private bool _disposed;

    public OverlayController(MainViewModel main, ForegroundTracker tracker, Func<string, string> text)
    {
        _main = main;
        _tracker = tracker;
        _text = text;
        _main.Profiles.CollectionChanged += OnProfilesChanged;
        _main.Overlay.Changed += OnSettingsChanged;
        Reconcile();
    }

    public IReadOnlyCollection<OverlayButtonWindow> Buttons => _buttons.Values;

    /// <summary>프로필 목록에 맞춘다. 있는 창은 고치고, 새로 켠 것은 만들고, 끈 것은 닫는다. 몇 번 불러도 같다.</summary>
    public void Reconcile()
    {
        _reconcileQueued = false;
        if (_disposed) return;

        var wanted = _main.Profiles.Where(p => p.OverlayEnabled).ToDictionary(p => p.Id);

        foreach (var id in _buttons.Keys.Where(id => !wanted.ContainsKey(id)).ToList())
        {
            _buttons[id].Close();
            _buttons.Remove(id);
        }

        foreach (var (id, row) in wanted)
        {
            if (!_buttons.TryGetValue(id, out var button))
            {
                button = Create(id);
                button.Configure(row.Name, row.Profile.EffectiveOverlayStyle, _main.Overlay.Settings);
                Place(button);
                continue;
            }
            button.Configure(row.Name, row.Profile.EffectiveOverlayStyle, _main.Overlay.Settings);
        }
    }

    private OverlayButtonWindow Create(string id)
    {
        var button = new OverlayButtonWindow(id, _text);
        button.Triggered += OnTriggered;
        button.Moved += (b, point) => _main.Overlay.RememberPosition(b.ProfileId, point);
        button.CloseRequested += b =>
        {
            var row = _main.Profiles.FirstOrDefault(p => p.Id == b.ProfileId);
            if (row is not null) _main.SetProfileOverlay(row, false);
        };
        _buttons[id] = button;
        return button;
    }

    /// <summary>
    /// 띄우고 자리를 잡는다. 감춘 상태여도 한 번은 띄운다 - 그래야 창 핸들이 생겨 활성화 방지 스타일이 걸린다
    /// (PyQt5 와 같은 이유). 크기는 띄운 뒤에야 물리 픽셀로 알 수 있다.
    /// </summary>
    private void Place(OverlayButtonWindow button)
    {
        button.Show();
        var size = _windows.GetRect(button.Handle) ?? new PixelRect(0, 0, (int)button.Width, (int)button.Height);
        var monitors = _windows.EnumerateMonitors();

        var point = _main.Overlay.Settings.Layout.TryGetValue(button.ProfileId, out var saved) &&
                    OverlayPlacement.IsVisibleOn(saved, size.Width, size.Height, monitors.Select(m => m.Bounds))
            ? saved
            : OverlayPlacement.NextButton(
                (monitors.FirstOrDefault(m => m.IsPrimary) ?? monitors.First()).WorkArea,
                size.Width, size.Height, _buttons.Count - 1);

        Win32Windows.MoveTo(button.Handle, point.X, point.Y);
        if (point != saved) _main.Overlay.RememberPosition(button.ProfileId, point);
        if (_main.Overlay.Hidden) button.Hide();
    }

    private void OnTriggered(OverlayButtonWindow button)
    {
        var target = _tracker.Target;
        var title = target is { } hwnd ? Win32Windows.DescribeWindow(hwnd).Title : "";
        button.ShowFeedback(_main.ApplyProfileToWindow(button.ProfileId, target, title));
    }

    private void OnSettingsChanged(string property)
    {
        if (property == nameof(OverlayViewModel.Hidden))
        {
            foreach (var button in _buttons.Values)
            {
                if (_main.Overlay.Hidden) button.Hide();
                else button.Show();
            }
            return;
        }
        Reconcile();
    }

    /// <summary>
    /// 프로필 목록은 저장할 때마다 통째로 다시 만들어진다(Clear + Add). 변경 알림마다 맞추지 않고 한 번으로 모은다.
    /// </summary>
    private void OnProfilesChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        if (_reconcileQueued) return;
        _reconcileQueued = true;
        Dispatcher.CurrentDispatcher.BeginInvoke(Reconcile, DispatcherPriority.Background);
    }

    public void Dispose()
    {
        _disposed = true;
        _main.Profiles.CollectionChanged -= OnProfilesChanged;
        _main.Overlay.Changed -= OnSettingsChanged;
        foreach (var button in _buttons.Values) button.Close();
        _buttons.Clear();
    }
}
