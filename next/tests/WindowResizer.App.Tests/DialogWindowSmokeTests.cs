using System.Windows;
using WindowResizer.App.ViewModels;
using WindowResizer.Core.Profiles;
using WindowResizer.Core.Windowing;

namespace WindowResizer.App.Tests;

/// <summary>
/// XAML 은 컴파일이 통과해도 리소스 키나 바인딩 형식이 틀리면 창을 열 때 죽는다.
/// 실제 앱 리소스(<c>App.xaml</c>)를 올린 채 창을 띄우고 모든 페이지를 한 번씩 그려 본다.
/// </summary>
[TestClass]
public sealed class DialogWindowSmokeTests
{
    [STATestMethod]
    public void Editor_and_picker_windows_open_and_render_every_page_with_the_app_resources()
    {
        if (Application.Current is null) new App().InitializeComponent();

        // 바인딩 오류는 예외가 아니라 추적 출력으로만 나온다. 모아서 0 건인지 본다.
        var bindingErrors = new BindingErrorCollector();
        System.Diagnostics.PresentationTraceSources.Refresh();
        System.Diagnostics.PresentationTraceSources.DataBindingSource.Listeners.Add(bindingErrors);
        System.Diagnostics.PresentationTraceSources.DataBindingSource.Switch.Level = System.Diagnostics.SourceLevels.Error;

        var windows = new NoWindows();
        var profile = Profile.FromWindow(new WindowInfo("t", "blender.exe", "", @"C:\B\blender.exe"),
            new WindowConfiguration { X = 1, Y = 2, Width = 300, Height = 200 }, "Blender");
        var editor = new ProfileEditorViewModel(profile, EditorPage.General, _ => false, () => [], windows, null!, k => k);

        var window = new ProfileEditorWindow { DataContext = editor, ShowActivated = false, Left = -4000 };
        window.Show();
        try
        {
            foreach (var page in Enum.GetValues<EditorPage>())
            {
                editor.Page = page;
                window.UpdateLayout();
            }
        }
        finally
        {
            window.Close();
        }

        var row = new WindowRow(1, new WindowInfo("Scene"), 10, new PixelRect(0, 0, 10, 10), false, false);
        var picker = new WindowPickerWindow([row]) { ShowActivated = false, Left = -4000 };
        picker.Show();
        picker.UpdateLayout();
        Assert.AreEqual(row, picker.Selected);
        picker.Close();

        // 메인 창도 같은 리소스로 그린다(되돌리기 버튼 등 S4b 에서 늘어난 바인딩).
        var document = new ProfileDocument();
        document.Add(profile, 1);
        document.Unreadable.Add(new UnreadableProfile("broken", """{ "name": "Old" }""", "bad enum"));
        var main = new MainViewModel(() => [row], windows, document, _ => null, null!, k => k);
        main.RefreshWindows();
        var mainWindow = new MainWindow { DataContext = main, ShowActivated = false, Left = -4000 };
        mainWindow.Show();
        foreach (var page in Enum.GetValues<AppPage>())
        {
            main.Page = page;
            mainWindow.UpdateLayout();
        }
        mainWindow.Close();

        // 오버레이 버튼: 모양 4 x 게이지 4 를 드웰 진행 중 상태로 그리고, 활성화 방지 스타일이 실제로 걸렸는지 본다.
        var button = new Overlay.OverlayButtonWindow("p", k => k + " {0} {1}");
        button.Show();
        try
        {
            Assert.IsTrue(button.IsNoActivate, "WS_EX_NOACTIVATE/TOOLWINDOW 가 걸리지 않았다 - 누르면 대상 창이 바뀐다");
            foreach (var shape in Core.Profiles.OverlayStyle.Shapes)
            foreach (var gauge in Core.Profiles.OverlayStyle.Gauges)
            {
                button.Configure("Blender", new Core.Profiles.OverlayStyle { Shape = shape, Gauge = gauge, BackgroundColor = "not-a-colour" },
                    new Core.Overlay.OverlaySettings { Activation = Core.Overlay.OverlayActivation.Dwell });
                button.ShowFeedback(success: shape == "pill");
                button.UpdateLayout();
            }
        }
        finally
        {
            button.Close();
        }

        // 감추기 스위치: 두 상태(보임/감춤)와 잠금 여부로 그리고, 활성화 방지가 걸렸는지 본다.
        var hideSwitch = new Overlay.OverlayToggleWindow(k => k);
        hideSwitch.Show();
        try
        {
            Assert.IsTrue(hideSwitch.IsNoActivate, "스위치가 활성화되면 직전 창이 바뀐다");
            foreach (var hidden in new[] { false, true })
            foreach (var locked in new[] { false, true })
            {
                hideSwitch.Configure(hidden, locked);
                hideSwitch.UpdateLayout();
            }
        }
        finally
        {
            hideSwitch.Close();
        }

        System.Diagnostics.PresentationTraceSources.DataBindingSource.Listeners.Remove(bindingErrors);
        Assert.IsEmpty(bindingErrors.Messages, string.Join(Environment.NewLine, bindingErrors.Messages));
    }

    private sealed class BindingErrorCollector : System.Diagnostics.TraceListener
    {
        public List<string> Messages { get; } = new();
        public override void Write(string? message) { }
        public override void WriteLine(string? message) { if (message is not null) Messages.Add(message); }
    }

    private sealed class NoWindows : IWindowOperations
    {
        public bool IsWindow(nint window) => false;
        public bool IsMaximized(nint window) => false;
        public bool IsMinimized(nint window) => false;
        public PixelRect? GetRect(nint window) => null;
        public WindowPlacement? GetPlacement(nint window) => null;
        public bool Restore(nint window) => false;
        public bool Maximize(nint window) => false;
        public bool Minimize(nint window) => false;
        public bool Move(nint window, PixelRect rect) => false;
        public bool SetTopmost(nint window, bool topmost) => false;
    }
}
