namespace WindowResizer.Core;

/// <summary>
/// 이 어셈블리를 가리키기 위한 표식.
///
/// Core 는 프로필, 매칭 조건, 창 기하 계산을 소유하며 Win32 나 WPF 를 알지 못한다.
/// 그 경계는 이 프로젝트가 net10.0(-windows 없음)을 target 하는 것으로 지켜진다.
/// 계약 타입들은 S2 에서 들어온다.
/// </summary>
public static class CoreAssembly
{
    /// <summary>테스트와 조합 루트가 어셈블리를 찾을 때 쓰는 진입점.</summary>
    public static System.Reflection.Assembly Reference => typeof(CoreAssembly).Assembly;
}
