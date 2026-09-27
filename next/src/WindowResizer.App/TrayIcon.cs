using Forms = System.Windows.Forms;

namespace WindowResizer.App;

/// <summary>
/// 시스템 트레이 아이콘(S4c, D-020). WinForms <see cref="Forms.NotifyIcon"/> 을 감싼다 - WPF 에는 트레이 API 가 없다.
/// WinForms 는 이 파일에서만 쓴다.
///
/// 메뉴는 PyQt5 트레이 6항목 중 "창 열기"와 "프로그램 종료" 둘이다. 오버레이 네 항목은 오버레이 단계에서 붙는다.
/// 왼쪽 클릭과 더블클릭은 창을 연다(PyQt5 와 같다).
/// </summary>
public sealed class TrayIcon : IDisposable
{
    private readonly Forms.NotifyIcon _icon;
    private readonly Func<string, string> _text;
    private bool _hiddenNoticeShown;

    public TrayIcon(Func<string, string> text, Action open, Action exit)
    {
        _text = text;
        var menu = new Forms.ContextMenuStrip();
        menu.Items.Add(text("Tray.Open"), null, (_, _) => open());
        menu.Items.Add(new Forms.ToolStripSeparator());
        menu.Items.Add(text("Tray.Exit"), null, (_, _) => exit());

        _icon = new Forms.NotifyIcon
        {
            Icon = System.Drawing.SystemIcons.Application,
            Text = text("App.Title"),
            ContextMenuStrip = menu,
            Visible = true,
        };
        _icon.MouseClick += (_, e) =>
        {
            if (e.Button == Forms.MouseButtons.Left) open();
        };
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
    }
}
