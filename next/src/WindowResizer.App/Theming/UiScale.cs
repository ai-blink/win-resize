using System.Windows;
using System.Windows.Media;

namespace WindowResizer.App.Theming;

/// <summary>
/// 화면 크기(설정 페이지, 75-125%). PyQt5 <c>ui_scale_manager.py</c> 395줄은 위젯 트리를 돌며 최소 크기, 여백, 스타일
/// 시트의 숫자를 다시 계산했다. WPF 는 창의 루트에 <see cref="ScaleTransform"/> 을 <c>LayoutTransform</c> 으로 걸면
/// 글자와 여백과 컨트롤이 함께 커지고 레이아웃도 그 크기로 다시 잡힌다 - 걸어 두기만 하면 된다.
///
/// 창은 <see cref="Attach"/> 로 한 번 등록한다. 창 크기와 최소 크기도 같은 비율로 따라가야 커진 내용이 잘리지 않는다.
/// 오버레이 버튼 창은 등록하지 않는다 - 버튼은 화면에서 누르기 쉬운 고정 크기(44 px)여야 한다.
/// </summary>
public static class UiScale
{
    public static double Factor { get; private set; } = 1.0;

    /// <summary>등록한 창이 모두 새 배율을 적용한 뒤가 아니라 배율이 바뀌자마자 불린다.</summary>
    public static event Action? Changed;

    public static void Set(double factor)
    {
        if (Math.Abs(Factor - factor) < 0.0001) return;
        Factor = factor;
        Changed?.Invoke();
    }

    public static void Attach(Window window)
    {
        var minWidth = window.MinWidth;
        var minHeight = window.MinHeight;
        var applied = 1.0;

        void Apply()
        {
            var ratio = Factor / applied;
            applied = Factor;

            if (window.Content is FrameworkElement root)
                root.LayoutTransform = Factor == 1.0 ? Transform.Identity : new ScaleTransform(Factor, Factor);
            window.MinWidth = minWidth * Factor;
            window.MinHeight = minHeight * Factor;

            // 창 크기는 지금 크기에 비율만 곱한다 - 사용자가 늘린 크기를 기본값으로 되돌리지 않는다.
            if (window.WindowState == WindowState.Normal)
            {
                var work = SystemParameters.WorkArea;
                if (!double.IsNaN(window.Width)) window.Width = Math.Min(window.Width * ratio, work.Width);
                if (!double.IsNaN(window.Height)) window.Height = Math.Min(window.Height * ratio, work.Height);
            }
        }

        Apply();
        Changed += Apply;
        window.Closed += (_, _) => Changed -= Apply;
    }
}
