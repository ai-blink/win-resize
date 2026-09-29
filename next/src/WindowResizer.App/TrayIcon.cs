using Forms = System.Windows.Forms;

namespace WindowResizer.App;

/// <summary>
/// 시스템 트레이 아이콘(S4c, D-020). WinForms <see cref="Forms.NotifyIcon"/> 을 감싼다 - WPF 에는 트레이 API 가 없다.
/// WinForms 는 이 파일에서만 쓴다.
///
/// 메뉴는 PyQt5 트레이 6항목 그대로다: 창 열기, 오버레이 드웰 모드, 오버레이 버튼 감추기, 감추기 스위치 표시,
/// 오버레이 버튼 모두 닫기, 프로그램 종료. 오버레이 세 토글은 <see cref="ViewModels.OverlayViewModel"/> 을 직접
/// 읽고 쓴다 - 메뉴를 열 때마다 체크를 다시 읽으므로 페이지나 메뉴 막대에서 바꾼 값과 어긋나지 않는다.
/// 왼쪽 클릭과 더블클릭은 창을 연다(PyQt5 와 같다).
/// </summary>
public sealed class TrayIcon : IDisposable
{
    private readonly Forms.NotifyIcon _icon;
    // 트레이 칸 크기(보통 16 px, 배율에 따라 커진다)에 맞는 프레임을 고른다.
    private readonly System.Drawing.Icon _appIcon = AppIcon.Load(Forms.SystemInformation.SmallIconSize);
    private readonly Func<string, string> _text;
    private bool _hiddenNoticeShown;

    public TrayIcon(Func<string, string> text, Action open, Action exit,
        ViewModels.OverlayViewModel overlay, Action closeAllOverlays)
    {
        _text = text;
        var menu = new Forms.ContextMenuStrip();
        _labels.Add((menu.Items.Add(text("Tray.Open"), null, (_, _) => open()), "Tray.Open"));
        menu.Items.Add(new Forms.ToolStripSeparator());

        var dwell = Toggle(text("Tray.OverlayDwell"), () => overlay.IsDwell, v => overlay.IsDwell = v);
        var hidden = Toggle(text("Tray.OverlayHidden"), () => overlay.Hidden, v => overlay.Hidden = v);
        var toggle = Toggle(text("Tray.OverlaySwitch"), () => overlay.ToggleVisible, v => overlay.ToggleVisible = v);
        _labels.Add((dwell.Item, "Tray.OverlayDwell"));
        _labels.Add((hidden.Item, "Tray.OverlayHidden"));
        _labels.Add((toggle.Item, "Tray.OverlaySwitch"));
        menu.Items.Add(dwell.Item);
        menu.Items.Add(hidden.Item);
        menu.Items.Add(toggle.Item);
        _labels.Add((menu.Items.Add(text("Tray.OverlayCloseAll"), null, (_, _) => closeAllOverlays()), "Tray.OverlayCloseAll"));
        menu.Opening += (_, _) =>
        {
            foreach (var (item, get) in new[] { dwell, hidden, toggle }) item.Checked = get();
        };

        menu.Items.Add(new Forms.ToolStripSeparator());
        _labels.Add((menu.Items.Add(text("Tray.Exit"), null, (_, _) => exit()), "Tray.Exit"));

        _icon = new Forms.NotifyIcon
        {
            Icon = _appIcon,
            Text = IconText(),
            ContextMenuStrip = menu,
            Visible = true,
        };
        _icon.MouseClick += (_, e) =>
        {
            if (e.Button == Forms.MouseButtons.Left) open();
        };
    }

    private readonly List<(Forms.ToolStripItem Item, string Key)> _labels = new();

    private string IconText() => _text("App.Title") + " " + AppInfo.DisplayVersion;

    /// <summary>표시 언어가 바뀌었다 - 메뉴 항목과 아이콘 설명을 새 언어로 다시 적는다.</summary>
    public void RefreshTexts()
    {
        foreach (var (item, key) in _labels) item.Text = _text(key);
        _icon.Text = IconText();
    }

    /// <summary>
    /// 체크 항목 하나. 누르면 읽은 값의 반대를 쓴다(CheckOnClick 을 쓰지 않는다 - 체크 표시가 설정보다 앞서가면
    /// 저장 실패 등으로 둘이 어긋난다).
    /// </summary>
    private static (Forms.ToolStripMenuItem Item, Func<bool> Get) Toggle(string label, Func<bool> get, Action<bool> set)
    {
        var item = new Forms.ToolStripMenuItem(label);
        item.Click += (_, _) => set(!get());
        return (item, get);
    }

    /// <summary>처음 트레이로 숨길 때 한 번만 알린다. 매번 띄우면 소음이다(PyQt5 <c>_tray_notification_shown</c>).</summary>
    public void NotifyHiddenOnce()
    {
        if (_hiddenNoticeShown) return;
        _hiddenNoticeShown = true;
        _icon.ShowBalloonTip(3000, _text("App.Title"), _text("Tray.HiddenNotice"), Forms.ToolTipIcon.Info);
    }

    /// <summary>아이콘을 지운다. 지우지 않고 끝나면 트레이에 죽은 아이콘이 마우스를 올릴 때까지 남는다.</summary>
    public void Dispose()
    {
        _icon.Visible = false;
        _icon.ContextMenuStrip?.Dispose();
        _icon.Dispose();
        _appIcon.Dispose();
    }
}
