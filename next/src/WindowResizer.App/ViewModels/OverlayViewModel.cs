using WindowResizer.App.Mvvm;
using WindowResizer.Core.Overlay;

namespace WindowResizer.App.ViewModels;

/// <summary>
/// 오버레이 전역 설정(메뉴 지도 2.5)의 화면 쪽 주인. 오버레이 페이지, 메뉴 막대, 트레이가 이 객체 하나를 본다 -
/// PyQt5 는 세 곳을 따로 맞추느라 <c>_sync_*_controls</c> 가 셋 있었다.
///
/// 값을 바꾸면 바로 저장하고 <see cref="Changed"/> 로 알린다(떠 있는 버튼 창이 따라 바뀐다).
/// 저장이 실패해도 화면 값은 유지한다 - 설정은 되돌릴 이유가 없고, 다음 저장이 다시 시도한다.
/// </summary>
public sealed class OverlayViewModel : ObservableObject
{
    private readonly Func<OverlaySettings, string?> _save;
    private readonly Func<string, string> _text;
    private readonly Action<string> _status;
    private readonly Action<string> _warn;

    /// <param name="warning">저장 실패처럼 경고로 기록할 문구를 받는 곳. 없으면 <paramref name="status"/> 로 보낸다.</param>
    public OverlayViewModel(OverlaySettings settings, Func<OverlaySettings, string?> save,
        Func<string, string> text, Action<string> status, Action<string>? warning = null)
    {
        Settings = settings;
        _save = save;
        _text = text;
        _status = status;
        _warn = warning ?? status;
        SetDwellCommand = new ParameterCommand<bool>(dwell => IsDwell = dwell);
    }

    /// <summary>메뉴 막대의 클릭/드웰 두 항목. 인자 true 면 드웰.</summary>
    public System.Windows.Input.ICommand SetDwellCommand { get; }

    /// <summary>현재 설정. 버튼 창(O3)이 읽는다. 바꾸는 것은 이 클래스의 속성으로만.</summary>
    public OverlaySettings Settings { get; }

    /// <summary>설정 하나가 바뀌었다. 인자는 속성 이름.</summary>
    public event Action<string>? Changed;

    public bool IsDwell
    {
        get => Settings.Activation == OverlayActivation.Dwell;
        set
        {
            var activation = value ? OverlayActivation.Dwell : OverlayActivation.Click;
            if (Settings.Activation == activation) return;
            Settings.Activation = activation;
            OnPropertyChanged(nameof(IsClick));
            Commit(nameof(IsDwell), value
                ? string.Format(_text("Status.OverlayDwell"), DwellSeconds)
                : _text("Status.OverlayClick"));
        }
    }

    public bool IsClick
    {
        get => !IsDwell;
        set => IsDwell = !value;
    }

    /// <summary>드웰 시간(초). 슬라이더가 0.2-5.0 을 0.1 단위로 움직인다.</summary>
    public double DwellSeconds
    {
        get => Settings.DwellMs / 1000.0;
        set
        {
            var ms = (int)Math.Round(value * 10) * 100;
            if (Settings.DwellMs == Math.Clamp(ms, OverlaySettings.MinDwellMs, OverlaySettings.MaxDwellMs)) return;
            Settings.DwellMs = ms;
            Commit(nameof(DwellSeconds), string.Format(_text("Status.OverlayDwellTime"), DwellSeconds));
        }
    }

    public bool Hidden
    {
        get => Settings.Hidden;
        set
        {
            if (Settings.Hidden == value) return;
            Settings.Hidden = value;
            Commit(nameof(Hidden), _text(value ? "Status.OverlayHidden" : "Status.OverlayShown"));
        }
    }

    public bool ToggleVisible
    {
        get => Settings.ToggleVisible;
        set
        {
            if (Settings.ToggleVisible == value) return;
            Settings.ToggleVisible = value;
            // 스위치를 치우면서 버튼을 감춘 채로 두면 되살릴 방법이 사라진다(PyQt5 hide_overlay_toggle_button).
            if (!value && Settings.Hidden)
            {
                Settings.Hidden = false;
                OnPropertyChanged(nameof(Hidden));
                Changed?.Invoke(nameof(Hidden));
            }
            Commit(nameof(ToggleVisible), _text(value ? "Status.OverlaySwitchShown" : "Status.OverlaySwitchRemoved"));
        }
    }

    public bool Locked
    {
        get => Settings.Locked;
        set
        {
            if (Settings.Locked == value) return;
            Settings.Locked = value;
            Commit(nameof(Locked), _text(value ? "Status.OverlayLocked" : "Status.OverlayUnlocked"));
        }
    }

    /// <summary>버튼 창이 옮겨졌다(O3). 자리만 저장하고 상태 줄은 건드리지 않는다.</summary>
    public void RememberPosition(string profileId, ScreenPoint point)
    {
        Settings.Layout[profileId] = point;
        _save(Settings);
    }

    public void RememberTogglePosition(ScreenPoint point)
    {
        Settings.TogglePosition = point;
        _save(Settings);
    }

    private void Commit(string property, string message)
    {
        OnPropertyChanged(property);
        Changed?.Invoke(property);
        var error = _save(Settings);
        if (error is null) _status(message);
        else _warn(string.Format(_text("Status.SettingsSaveFailed"), error));
    }
}
