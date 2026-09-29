using System.Windows;
using System.Windows.Input;

namespace WindowResizer.App;

/// <summary>메인 창. 상태와 동작은 <see cref="ViewModels.MainViewModel"/> 이 소유하고, 여기에는 초점 이동만 있다.</summary>
public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        Theming.UiScale.Attach(this);
        DataContextChanged += (_, e) =>
        {
            if (e.NewValue is ViewModels.MainViewModel main)
                main.Log.Rows.CollectionChanged += (_, change) =>
                {
                    if (change.Action == System.Collections.Specialized.NotifyCollectionChangedAction.Add) ScrollLogToEnd();
                };
        };
    }

    /// <summary>로그 페이지가 열릴 때, 자동 스크롤이 켜져 있으면 맨 아래(가장 최근 줄)를 보인다.</summary>
    private void OnLogPageVisibleChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        if ((bool)e.NewValue) ScrollLogToEnd();
    }

    private void ScrollLogToEnd()
    {
        if (DataContext is not ViewModels.MainViewModel { Log: { AutoScroll: true } log } || log.Rows.Count == 0) return;
        // 줄이 붙은 뒤 목록이 크기를 다시 잡은 다음에 스크롤해야 마지막 줄이 보인다.
        Dispatcher.BeginInvoke(new Action(() =>
        {
            if (log.Rows.Count > 0) LogList.ScrollIntoView(log.Rows[^1]);
        }), System.Windows.Threading.DispatcherPriority.Background);
    }

    /// <summary>슬라이더를 끄는 동안은 숫자만 바뀌고, 놓을 때 화면 크기를 적용한다(SettingsViewModel 참고).</summary>
    private void OnScaleDragStarted(object sender, System.Windows.Controls.Primitives.DragStartedEventArgs e)
    {
        if (DataContext is ViewModels.MainViewModel main) main.Settings.BeginScaleDrag();
    }

    private void OnScaleDragCompleted(object sender, System.Windows.Controls.Primitives.DragCompletedEventArgs e)
    {
        if (DataContext is ViewModels.MainViewModel main) main.Settings.EndScaleDrag();
    }

    /// <summary>
    /// 단축키 선택 줄이 감지를 시작하거나 멈출 때. 감지 중에는 전역 단축키 등록을 풀어야, 이미 등록된 조합을 다시 누를 때
    /// 칸이 그 키를 받는다(안 풀면 등록이 먼저 잡아 동작이 실행된다).
    /// </summary>
    private void OnPickerDetecting(object? sender, bool detecting)
    {
        if (DataContext is ViewModels.MainViewModel main) main.Hotkeys.SetCapturing(detecting);
    }

    /// <summary>Ctrl+F: 검색 상자로 초점을 옮긴다. 빈 껍데기였던 "검색 및 필터" 메뉴의 실제 기능이다(D-020).</summary>
    private void OnFind(object sender, ExecutedRoutedEventArgs e)
    {
        SearchBox.Focus();
        SearchBox.SelectAll();
    }
}
