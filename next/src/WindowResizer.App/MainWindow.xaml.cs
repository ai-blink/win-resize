using System.Windows;
using System.Windows.Input;

namespace WindowResizer.App;

/// <summary>메인 창. 상태와 동작은 <see cref="ViewModels.MainViewModel"/> 이 소유하고, 여기에는 초점 이동만 있다.</summary>
public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
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
