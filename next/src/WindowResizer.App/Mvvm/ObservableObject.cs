using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;

namespace WindowResizer.App.Mvvm;

/// <summary>속성 변경 알림의 최소 구현. 외부 MVVM 패키지를 들이지 않는다.</summary>
public abstract class ObservableObject : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;

    protected bool Set<T>(ref T field, T value, [CallerMemberName] string? name = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value)) return false;
        field = value;
        OnPropertyChanged(name);
        return true;
    }

    protected void OnPropertyChanged([CallerMemberName] string? name = null) =>
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}

/// <summary>
/// 버튼, 메뉴, 키 입력이 공유하는 명령 하나. 계획 4.1: 어느 경로로 시작해도 같은 코드 한 곳으로 들어간다.
/// </summary>
public sealed class RelayCommand(Action execute, Func<bool>? canExecute = null) : ICommand
{
    public event EventHandler? CanExecuteChanged
    {
        add => CommandManager.RequerySuggested += value;
        remove => CommandManager.RequerySuggested -= value;
    }

    public bool CanExecute(object? parameter) => canExecute?.Invoke() ?? true;

    public void Execute(object? parameter)
    {
        if (CanExecute(parameter)) execute();
    }
}
