using System.Windows;
using WindowResizer.App.ViewModels;

namespace WindowResizer.App;

/// <summary>창 여러 개 중 하나를 고르는 작은 창.</summary>
public partial class WindowPickerWindow : Window
{
    public WindowPickerWindow(IReadOnlyList<WindowRow> candidates)
    {
        InitializeComponent();
        Candidates.ItemsSource = candidates;
        Candidates.SelectedIndex = 0;
    }

    public WindowRow? Selected => Candidates.SelectedItem as WindowRow;

    private void OnSelect(object sender, RoutedEventArgs e)
    {
        if (Selected is not null) DialogResult = true;
    }
}
