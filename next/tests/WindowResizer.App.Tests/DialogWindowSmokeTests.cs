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
        // 세트가 있는 프로필: 편집 창은 단일 조합 칸을 닫고 안내를 보이며, 단축키 페이지는 등록 목록과 세트 편집을 그린다.
        profile.HotkeyEnabled = true;
        profile.HotkeySets.Add(new HotkeySet { Enabled = true, Combination = "Ctrl+Alt+F1", Action = "apply_profile" });
        profile.HotkeySets.Add(new HotkeySet { Enabled = true, Combination = "not a key", Action = "apply_profile" });
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
        main.Hotkeys.Sync();
        main.Hotkeys.SelectedProfile = main.Hotkeys.ProfileChoices.First();
        Assert.IsNotEmpty(main.Hotkeys.Rows, "잘못된 조합이 등록 목록에 보여야 한다");
        var mainWindow = new MainWindow { DataContext = main, ShowActivated = false, Left = -4000 };
        mainWindow.Show();
        foreach (var page in Enum.GetValues<AppPage>())
        {
            main.Page = page;
            mainWindow.UpdateLayout();
        }

        // 화면 크기: 등록한 창은 루트에 배율 변환이 걸리고 최소 크기와 창 크기가 같은 비율로 커진다. 끝나면 되돌린다(정적 값).
        var baseMin = mainWindow.MinWidth;
        var baseWidth = mainWindow.Width;
        main.Page = AppPage.Settings;
        try
        {
            Theming.UiScale.Set(1.25);
            mainWindow.UpdateLayout();
            Assert.AreEqual(baseMin * 1.25, mainWindow.MinWidth, 0.01);
            // 창 크기는 장치 픽셀로 반올림돼 1 DIP 안팎으로 어긋난다.
            Assert.AreEqual(baseWidth * 1.25, mainWindow.Width, 1.0);
            var transform = (System.Windows.Media.ScaleTransform)((FrameworkElement)mainWindow.Content).LayoutTransform;
            Assert.AreEqual(1.25, transform.ScaleX, 0.0001);
        }
        finally
        {
            Theming.UiScale.Set(1.0);
        }
        Assert.AreEqual(baseMin, mainWindow.MinWidth, 0.01);
        mainWindow.Close();

        // 앱 아이콘: 한 ICO 에 16-256 px 아홉 프레임이 있어야 작업 표시줄과 트레이에서 뭉개지지 않는다(원본 PNG 는 256 px 한
        // 장이었다). 창은 앱 기본 스타일에서, 트레이는 같은 리소스를 GDI 아이콘으로 읽어 프레임을 고른다.
        // (Application 은 프로세스에 하나뿐이라 다른 STA 테스트를 만들지 않고 여기서 함께 본다.)
        var frames = System.Windows.Media.Imaging.BitmapDecoder
            .Create(AppIcon.Uri, System.Windows.Media.Imaging.BitmapCreateOptions.None, System.Windows.Media.Imaging.BitmapCacheOption.OnLoad)
            .Frames.Select(f => f.PixelWidth).OrderBy(w => w).ToArray();
        CollectionAssert.AreEqual(new[] { 16, 20, 24, 32, 40, 48, 64, 128, 256 }, frames);
        using (var small = AppIcon.Load(new System.Drawing.Size(16, 16)))
        using (var large = AppIcon.Load(new System.Drawing.Size(32, 32)))
        {
            Assert.AreEqual(16, small.Width);
            Assert.AreEqual(32, large.Width);
        }
        Assert.IsNotNull(mainWindow.Icon, "메인 창 XAML 루트의 Icon 이 빠졌다(Window 암시적 스타일은 파생 창에 적용되지 않는다)");
        Assert.IsNotNull(window.Icon, "편집 창도 같은 아이콘을 받는다");
        Assert.IsNotNull(picker.Icon, "창 고르기 창도 같은 아이콘을 받는다");

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

            // 우클릭 메뉴: 이름(굵게) / 위치 / 속성, 덮어쓰기, 복제 / 삭제. 각 항목을 눌러 이벤트가 나가는지 본다.
            button.SetInfo("Overlay.Menu.Position 1 2 300 200");
            var menu = button.ButtonMenu;
            menu.IsOpen = true;
            try
            {
                var items = menu.Items.Cast<object>().ToList();
                Assert.AreEqual("Blender", ((System.Windows.Controls.TextBlock)items[0]).Text);
                Assert.AreEqual(FontWeights.Bold, ((System.Windows.Controls.TextBlock)items[0]).FontWeight);
                var clickable = items.OfType<System.Windows.Controls.MenuItem>().ToList();
                // 창의 문구 함수는 위에서 만든 것(k + " {0} {1}")이다.
                CollectionAssert.AreEqual(
                    new[] { "Overlay.Menu.Properties {0} {1}", "Overlay.Menu.Overwrite {0} {1}", "Overlay.Menu.Duplicate {0} {1}", "Overlay.Menu.Delete {0} {1}" },
                    clickable.Select(m => (string)m.Header).ToArray());
                Assert.IsTrue(items.TakeWhile(i => i is not System.Windows.Controls.MenuItem).All(i => i is System.Windows.Controls.TextBlock or System.Windows.Controls.Separator),
                    "머리글과 정보 줄은 누를 수 있는 항목이 아니어야 한다");

                var raised = new List<string>();
                button.EditRequested += _ => raised.Add("edit");
                button.OverwriteRequested += _ => raised.Add("overwrite");
                button.DuplicateRequested += _ => raised.Add("duplicate");
                button.DeleteRequested += _ => raised.Add("delete");
                foreach (var item in clickable)
                    item.RaiseEvent(new RoutedEventArgs(System.Windows.Controls.MenuItem.ClickEvent));
                CollectionAssert.AreEqual(new[] { "edit", "overwrite", "duplicate", "delete" }, raised);
            }
            finally
            {
                menu.IsOpen = false;
            }
        }
        finally
        {
            button.Close();
        }

        // 버튼 속성 창: 네 페이지를 앱 리소스로 그려 바인딩 오류가 없는지 본다.
        var buttonEditor = new ButtonEditorViewModel(
            new Core.Overlay.OverlayButton { Id = "b", Name = "Blender", X = 1, Y = 2, Width = 300, Height = 200 }, () => null, k => k);
        var buttonWindow = new ButtonEditorWindow { DataContext = buttonEditor, ShowActivated = false, Left = -4000 };
        buttonWindow.Show();
        try
        {
            foreach (var page in Enum.GetValues<ButtonPage>())
            {
                buttonEditor.Page = page;
                buttonWindow.UpdateLayout();
            }
            Assert.IsNotNull(buttonWindow.Icon, "버튼 속성 창도 같은 아이콘을 받는다");
        }
        finally
        {
            buttonWindow.Close();
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
