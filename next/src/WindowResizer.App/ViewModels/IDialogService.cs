namespace WindowResizer.App.ViewModels;

/// <summary>
/// ViewModel 이 사용자에게 묻는 창들. 뷰(<c>DialogService</c>)가 WPF 창으로 구현하고 테스트는 가짜를 넘긴다.
/// ViewModel 은 창을 직접 만들지 않는다.
/// </summary>
public interface IDialogService
{
    /// <summary>삭제 확인. 되돌릴 수 없는 동작만 묻는다.</summary>
    bool ConfirmDelete(string profileName);

    /// <summary>경고 상자. 확인 하나만 있다 - 사용자가 알아야 하지만 되돌릴 선택은 없는 일에 쓴다.</summary>
    void Warn(string title, string message);

    /// <summary>프로필 편집 창을 모달로 연다. 저장을 눌러 닫혔으면 true.</summary>
    bool ShowEditor(ProfileEditorViewModel editor);

    /// <summary>조건에 맞는 창이 여러 개일 때 하나를 고르게 한다. 취소하면 null.</summary>
    WindowRow? ChooseWindow(IReadOnlyList<WindowRow> candidates);
}
