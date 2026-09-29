namespace WindowResizer.App.ViewModels;

/// <summary>
/// ViewModel 이 사용자에게 묻는 창들과 운영체제에 부탁하는 일(클립보드, 폴더 열기, 저장 위치 고르기).
/// 뷰(<c>DialogService</c>)가 WPF 로 구현하고 테스트는 가짜를 넘긴다. ViewModel 은 창을 직접 만들지 않는다.
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

    /// <summary>클립보드에 글을 넣는다. 다른 프로그램이 클립보드를 쥐고 있으면 실패할 수 있다 - 성공하면 true.</summary>
    bool CopyToClipboard(string text);

    /// <summary>저장할 파일 위치를 고르게 한다. 취소하면 null. <paramref name="filter"/> 는 <c>텍스트 (*.txt)|*.txt</c> 꼴.</summary>
    string? ChooseSaveFile(string title, string suggestedFileName, string filter);

    /// <summary>탐색기로 폴더를 연다. 성공하면 null, 실패하면 원인.</summary>
    string? OpenFolder(string path);
}
