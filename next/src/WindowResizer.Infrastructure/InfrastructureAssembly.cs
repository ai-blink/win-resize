namespace WindowResizer.Infrastructure;

/// <summary>
/// 이 어셈블리를 가리키기 위한 표식.
///
/// Infrastructure 는 Win32 P/Invoke 와 프로필 파일 영속화를 소유한다.
/// 그래서 net10.0-windows 를 target 하고 Core 를 참조한다. 반대 방향은 없다.
/// 실제 adapter 들은 S3 에서 들어온다.
/// </summary>
public static class InfrastructureAssembly
{
    /// <summary>테스트와 조합 루트가 어셈블리를 찾을 때 쓰는 진입점.</summary>
    public static System.Reflection.Assembly Reference => typeof(InfrastructureAssembly).Assembly;
}
