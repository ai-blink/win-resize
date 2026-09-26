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

    /// <summary>Ctrl+F: 검색 상자로 초점을 옮긴다. 빈 껍데기였던 "검색 및 필터" 메뉴의 실제 기능이다(D-020).</summary>
    private void OnFind(object sender, ExecutedRoutedEventArgs e)
    {
        SearchBox.Focus();
        SearchBox.SelectAll();
    }
}
