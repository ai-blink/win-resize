using System.Collections.ObjectModel;
using System.Windows.Input;
using WindowResizer.App.Mvvm;
using WindowResizer.Core.Diagnostics;
using WindowResizer.Core.Hotkeys;
using WindowResizer.Core.Profiles;

namespace WindowResizer.App.ViewModels;

/// <summary>
/// 단축키 쪽에서 밖으로 나가는 다섯 가지. 전부 없어도 앱은 뜬다(테스트) - 그때는 등록만 하지 않는다.
/// </summary>
/// <param name="Registrar">전역 단축키 등록기. 없으면 등록하지 않는다.</param>
/// <param name="ApplyAll">처음 값(저장소에서 읽은 것).</param>
/// <param name="Save">전체 적용 단축키 저장. 성공하면 null, 실패하면 원인.</param>
/// <param name="ToggleForegroundTopmost">전경 창의 항상 위를 뒤집는다. 창이 없으면 null.</param>
/// <param name="Post">UI 스레드로 넘긴다. 등록기는 자기 스레드에서 알리므로 상태를 건드리기 전에 반드시 거친다.</param>
public sealed record HotkeyServices(
    IHotkeyRegistrar? Registrar = null,
    ApplyAllHotkey? ApplyAll = null,
    Func<ApplyAllHotkey, string?>? Save = null,
    Func<(string Title, bool Topmost, bool Succeeded)?>? ToggleForegroundTopmost = null,
    Action<Action>? Post = null);

/// <summary>동작 콤보의 한 칸.</summary>
public sealed record HotkeyActionOption(HotkeyAction Action, string Display);

/// <summary>프로필 고르기 콤보의 한 칸.</summary>
public sealed record HotkeyProfileChoice(string Id, string Name);

/// <summary>등록 상태 목록의 한 줄.</summary>
public sealed record HotkeyStatusRow(string Label, string Text, string Action, string State, bool IsProblem);

/// <summary>
/// 단축키 한 줄의 편집 상태: 초안(고치는 중인 값)과 저장한 값. 줄마다 따로 저장한다 - 한 줄을 저장해도 다른 줄의
/// 저장 안 한 변경은 그대로다. <see cref="Problem"/> 은 이 줄의 조합이 전역 단축키로 못 쓰이는 이유(빨간 테두리)다.
/// </summary>
public sealed class HotkeyEditRow : ObservableObject
{
    private bool _enabled;
    private string _combination = "";
    private HotkeyAction _action = HotkeyAction.ApplyProfile;
    private (bool Enabled, string Combination, HotkeyAction Action) _saved = (false, "", HotkeyAction.ApplyProfile);
    private string _problem = "";

    /// <summary>경고 상자와 문구에 쓰는 이름("전체 적용", "세트 1").</summary>
    public string Label { get => _label; set => Set(ref _label, value); }
    private string _label = "";

    /// <summary>초안이 바뀌었다(다른 줄과의 중복 검사를 다시 하라는 신호).</summary>
    public Action<HotkeyEditRow>? Edited { get; set; }

    public ICommand? SaveCommand { get; init; }

    public bool Enabled { get => _enabled; set { if (Set(ref _enabled, value)) Changed(); } }
    public string Combination { get => _combination; set { if (Set(ref _combination, value ?? "")) Changed(); } }
    public HotkeyAction Action { get => _action; set { if (Set(ref _action, value)) Changed(); } }

    public bool IsDirty => (Enabled, Combination.Trim(), Action) != _saved;

    /// <summary>비어 있으면 문제없다.</summary>
    public string Problem
    {
        get => _problem;
        set { if (Set(ref _problem, value)) OnPropertyChanged(nameof(HasProblem)); }
    }

    public bool HasProblem => _problem.Length > 0;

    /// <summary>저장한 값 그대로 초안을 채운다(알림 없이). 문서에서 읽은 값을 보일 때 쓴다.</summary>
    public void Load(bool enabled, string combination, HotkeyAction action)
    {
        _enabled = enabled;
        _combination = combination;
        _action = action;
        _saved = (enabled, combination.Trim(), action);
        OnPropertyChanged(nameof(Enabled));
        OnPropertyChanged(nameof(Combination));
        OnPropertyChanged(nameof(Action));
        OnPropertyChanged(nameof(IsDirty));
    }

    /// <summary>지금 초안이 저장됐다.</summary>
    public void MarkSaved()
    {
        _saved = (Enabled, Combination.Trim(), Action);
        OnPropertyChanged(nameof(IsDirty));
    }

    /// <summary>마지막으로 저장한(또는 읽은) 값.</summary>
    public (bool Enabled, string Combination, HotkeyAction Action) Saved => _saved;

    private void Changed()
    {
        OnPropertyChanged(nameof(IsDirty));
        Edited?.Invoke(this);
    }
}

/// <summary>
/// 단축키 페이지(메뉴 지도 [단축키]). 세 가지를 맡는다:
/// 전체 적용 단축키 편집, 프로필별 세트(최대 3개)와 동작 편집, 등록 결과 목록.
///
/// 줄마다 저장하고, 줄마다 <b>바로 검사한다</b>: 형식이 틀렸거나, 다른 줄과 겹치거나, 다른 프로그램이나 Windows 가
/// 이미 쓰는 조합이면 그 줄에 이유(빨간 테두리)가 붙는다. 등록할 수 없는 조합도 PyQt5 와 같이 저장은 하고, 저장하는
/// 순간 경고 상자로 알린다.
///
/// 무엇을 등록할지는 문서가 정한다(Core <see cref="HotkeyPlanner"/>) - 프로필을 저장하거나 지울 때마다
/// <see cref="MainViewModel"/> 이 <see cref="Sync"/> 를 불러 통째로 다시 등록한다(PyQt5 와 같다).
/// 프로필 변경은 전부 <see cref="MainViewModel.SaveProfileHotkeys"/> 를 거친다(D-022).
/// </summary>
public sealed class HotkeysViewModel : ObservableObject
{
    /// <summary>편집 창이 한 프로필에 쓰는 세트 수(PyQt5 와 같다).</summary>
    public const int SetsPerProfile = 3;

    private readonly MainViewModel _owner;
    private readonly HotkeyServices _services;
    private readonly Func<string, string> _text;
    private readonly Action<Action> _post;

    private ApplyAllHotkey _applyAll;
    private string _applyAllState = "";

    private HotkeyProfileChoice? _selectedProfile;
    private bool _rebuildingChoices;
    private bool _profileHotkeysEnabled;
    private bool _loading;
    private bool _suppressReload;
    private string _loadedSignature = "";

    public HotkeysViewModel(MainViewModel owner, HotkeyServices services, Func<string, string> text)
    {
        _owner = owner;
        _services = services;
        _text = text;
        _post = services.Post ?? (action => action());

        _applyAll = services.ApplyAll ?? ApplyAllHotkey.Off;
        ApplyAll = new HotkeyEditRow { Label = text("Hotkeys.ApplyAll.Label"), SaveCommand = new RelayCommand(SaveApplyAll), Edited = _ => Recheck() };
        ApplyAll.Load(_applyAll.Enabled, _applyAll.Combination, HotkeyAction.ApplyAllProfiles);

        _actionOptions = BuildActionOptions();
        for (var i = 0; i < SetsPerProfile; i++)
        {
            HotkeyEditRow? row = null;
            row = new HotkeyEditRow
            {
                Label = string.Format(text("Hotkeys.Set.Name"), i + 1),
                Edited = _ => Recheck(),
                SaveCommand = new RelayCommand(() => SaveSet(row!)),
            };
            Sets.Add(row);
        }

        if (services.Registrar is { } registrar)
            registrar.Activated += binding => _post(() => _owner.RunHotkey(binding));
    }

    private IReadOnlyList<HotkeyActionOption> _actionOptions;

    public IReadOnlyList<HotkeyActionOption> ActionOptions
    {
        get => _actionOptions;
        private set => Set(ref _actionOptions, value);
    }

    private List<HotkeyActionOption> BuildActionOptions() => HotkeyActions.ProfileActions
        .Select(a => new HotkeyActionOption(a, _text("Hotkey.Action." + HotkeyActions.ToKey(a))))
        .ToList();

    /// <summary>
    /// 표시 언어가 바뀌었다: 문자열로 만들어 둔 것(동작 콤보, 줄 이름, 등록 결과 목록)을 새 언어로 다시 만든다.
    /// 입력 중인 초안과 저장값은 건드리지 않는다.
    /// </summary>
    public void RefreshTexts()
    {
        ActionOptions = BuildActionOptions();
        ApplyAll.Label = _text("Hotkeys.ApplyAll.Label");
        for (var i = 0; i < Sets.Count; i++) Sets[i].Label = string.Format(_text("Hotkeys.Set.Name"), i + 1);

        // 등록 목록은 같은 계획이면 다시 만들지 않으므로 다시 만들라고 알린다.
        _lastAllRegistered = false;
        Sync();
    }

    public ObservableCollection<HotkeyEditRow> Sets { get; } = new();
    public ObservableCollection<HotkeyProfileChoice> ProfileChoices { get; } = new();
    public ObservableCollection<HotkeyStatusRow> Rows { get; } = new();

    /// <summary>전체 적용 단축키 한 줄(동작은 정해져 있다).</summary>
    public HotkeyEditRow ApplyAll { get; }

    /// <summary>저장한 전체 적용 단축키의 등록 결과 한 줄.</summary>
    public string ApplyAllState { get => _applyAllState; private set => Set(ref _applyAllState, value); }

    // --- 저장 -------------------------------------------------------------------------------

    /// <summary>
    /// 검사하고 저장하고 다시 등록한다. PyQt5 와 같이 <b>등록에 실패해도 저장은 한다</b> -
    /// 다른 프로그램이 쓰고 있는 조합은 그 프로그램을 닫으면 다시 쓸 수 있다. 대신 경고 상자로 알린다.
    /// 형식이 틀리면 저장하지 않는다.
    /// </summary>
    public void SaveApplyAll()
    {
        var text = ApplyAll.Combination.Trim();
        if (ApplyAll.Enabled && !HotkeyCombination.TryParse(text, out _))
        {
            Recheck();
            _owner.ShowStatus(ApplyAll.Problem, LogLevel.Warning);
            return;
        }

        var next = new ApplyAllHotkey(ApplyAll.Enabled, text);
        var error = (_services.Save ?? (_ => null))(next);
        if (error is not null)
        {
            _owner.ShowStatus(string.Format(_text("Status.SettingsSaveFailed"), error), LogLevel.Warning);
            return;
        }

        _applyAll = next;
        ApplyAll.Combination = text;
        ApplyAll.MarkSaved();
        Sync();

        _owner.ShowStatus(!next.Enabled
            ? _text("Status.HotkeyApplyAllOff")
            : Registered(ApplyAllRegistrationKey)
                ? string.Format(_text("Status.HotkeyApplyAllOn"), next.Combination)
                : _text("Status.HotkeyApplyAllNotRegistered"));
        WarnIfProblem(ApplyAll);
    }

    /// <summary>
    /// 세트 한 줄을 저장한다. 문서에는 <b>활성화된 줄 중 조합이 있는 것만</b> 남는다(PyQt5 <c>_collect_hotkey_sets</c>) -
    /// 다른 줄은 저장 안 한 초안이 아니라 마지막으로 저장한 값을 쓴다. 첫 세트는 단일 필드에도 적힌다
    /// (<see cref="MainViewModel.SaveProfileHotkeys"/>).
    /// </summary>
    public void SaveSet(HotkeyEditRow row)
    {
        if (SelectedProfile is not { } choice) return;

        var text = row.Combination.Trim();
        if (row.Enabled && text.Length > 0 && !HotkeyCombination.TryParse(text, out _))
        {
            Recheck();
            _owner.ShowStatus(string.Format(_text("Hotkeys.Error.SetInvalid"), text), LogLevel.Warning);
            return;
        }

        if (!CommitSets(choice.Id, ProfileHotkeysEnabled, row, text)) return;

        row.Combination = text;
        row.MarkSaved();
        Recheck();
        WarnIfProblem(row);
    }

    /// <summary>
    /// 문서에 세트를 쓴다. <paramref name="edited"/> 줄은 초안, 나머지는 저장한 값. 다시 등록은 <see cref="Sync"/> 가
    /// 하지만 편집 칸은 다시 읽지 않는다 - 다른 줄의 저장 안 한 변경과 줄 위치를 지켜야 한다.
    /// </summary>
    private bool CommitSets(string profileId, bool enabled, HotkeyEditRow? edited, string editedText)
    {
        var sets = new List<HotkeySet>();
        foreach (var r in Sets)
        {
            var (on, combination, action) = r == edited ? (r.Enabled, editedText, r.Action) : r.Saved;
            if (on && combination.Length > 0)
                sets.Add(new HotkeySet { Enabled = true, Combination = combination, Action = HotkeyActions.ToKey(action) });
        }

        _suppressReload = true;
        try
        {
            if (!_owner.SaveProfileHotkeys(profileId, enabled, sets)) return false;
        }
        finally
        {
            _suppressReload = false;
        }
        _loadedSignature = Signature(_owner.FindProfile(profileId));
        return true;
    }

    private void WarnIfProblem(HotkeyEditRow row)
    {
        if (!row.Enabled || !row.HasProblem) return;
        _owner.Warn(_text("Hotkeys.Warn.Title"),
            string.Format(_text("Hotkeys.Warn.Body"), row.Label, row.Combination.Trim(), row.Problem));
    }

    // --- 바로 검사 ----------------------------------------------------------------------------

    /// <summary>
    /// 모든 줄을 다시 검사한다. 한 줄이 바뀌면 그 줄과 겹치는 다른 줄의 결과도 달라지므로 전부 다시 본다.
    /// 시험 등록은 등록기가 한다(<see cref="IHotkeyRegistrar.Probe"/>): 다른 프로그램이나 Windows 가 쓰는 조합이 여기서 걸린다.
    /// </summary>
    public void Recheck()
    {
        var all = new[] { ApplyAll }.Concat(Sets).ToList();
        foreach (var row in all) row.Problem = Check(row, all);
    }

    private string Check(HotkeyEditRow row, IReadOnlyList<HotkeyEditRow> all)
    {
        if (!row.Enabled) return "";
        var text = row.Combination.Trim();
        if (text.Length == 0) return row == ApplyAll ? _text("Hotkeys.Check.Empty") : "";
        if (!HotkeyCombination.TryParse(text, out var combination)) return _text("Hotkeys.Check.Invalid");

        foreach (var other in all.Where(o => o != row && o.Enabled))
        {
            if (HotkeyCombination.TryParse(other.Combination.Trim(), out var theirs) && theirs == combination)
                return string.Format(_text("Hotkeys.Check.Duplicate"), other.Label);
        }

        var error = _services.Registrar?.Probe(combination) ?? 0;
        if (error == 0) return "";
        return error == 1409 ? _text("Hotkeys.Check.Blocked") : string.Format(_text("Hotkeys.Check.Failed"), error);
    }

    // --- 프로필 세트 ------------------------------------------------------------------------

    /// <summary>편집할 프로필. 목록이 다시 만들어져도 같은 프로필이 계속 선택되어 있다.</summary>
    public HotkeyProfileChoice? SelectedProfile
    {
        get => _selectedProfile;
        set
        {
            // 목록을 비우는 순간 화면이 null 을 써 넣는다. 그건 사용자의 선택이 아니다.
            if (value is null && _rebuildingChoices) return;
            if (!Set(ref _selectedProfile, value)) return;
            OnPropertyChanged(nameof(HasSelectedProfile));
            LoadEditor(force: true);
        }
    }

    public bool HasSelectedProfile => SelectedProfile is not null;

    /// <summary>프로필의 단축키 전체 스위치(<c>hotkey_enabled</c>). 바꾸면 바로 저장한다(오버레이 설정과 같다).</summary>
    public bool ProfileHotkeysEnabled
    {
        get => _profileHotkeysEnabled;
        set
        {
            if (!Set(ref _profileHotkeysEnabled, value) || _loading) return;
            if (SelectedProfile is not { } choice) return;
            if (!CommitSets(choice.Id, value, null, "")) SetLoading(() => ProfileHotkeysEnabled = !value);
        }
    }

    private void SetLoading(Action action)
    {
        _loading = true;
        try { action(); }
        finally { _loading = false; }
    }

    /// <summary>
    /// 선택한 프로필의 세트를 편집 줄에 읽어 온다. 문서가 우리 저장이 아닌 이유로 바뀐 게 아니면(같은 값) 다시 읽지 않는다 -
    /// 적용 횟수 저장 같은 무관한 변경이 사용자가 고치는 중인 값을 지우면 안 된다.
    /// </summary>
    private void LoadEditor(bool force)
    {
        if (_suppressReload) return;

        var profile = _selectedProfile is null ? null : _owner.FindProfile(_selectedProfile.Id);
        var signature = Signature(profile);
        if (!force && signature == _loadedSignature) return;
        _loadedSignature = signature;

        SetLoading(() =>
        {
            ProfileHotkeysEnabled = profile?.HotkeyEnabled ?? false;
            var effective = profile is null ? [] : HotkeyPlanner.EffectiveSets(profile);
            for (var i = 0; i < Sets.Count; i++)
            {
                var source = i < effective.Count ? effective[i] : null;
                var action = source is not null && HotkeyActions.TryParseProfileAction(source.Action, out var parsed)
                    ? parsed
                    : HotkeyAction.ApplyProfile;
                Sets[i].Load(source?.Enabled ?? false, source?.Combination ?? "", action);
            }
        });
        Recheck();
    }

    private static string Signature(Profile? profile)
    {
        if (profile is null) return "";
        return profile.HotkeyEnabled + "|" + string.Join(";", HotkeyPlanner.EffectiveSets(profile)
            .Select(s => $"{s.Enabled},{s.Combination},{s.Action}"));
    }

    // --- 등록 -------------------------------------------------------------------------------

    private const string ApplyAllRegistrationKey = "apply-all";

    private bool _capturing;
    private int _dialogs;

    private bool Suspended => _capturing || _dialogs > 0;

    /// <summary>
    /// 감지 중일 때. 등록된 조합을 누르면 등록이 먼저 키를 잡아 가서 칸이 그 키를 못 받고 동작이 실행되어 버린다
    /// (전체 적용 Ctrl+Alt+E 를 다시 감지하려다 창이 다 움직인다). 그래서 감지 중에는 등록을 푼다.
    /// </summary>
    public void SetCapturing(bool capturing)
    {
        _capturing = capturing;
        ApplySuspension();
    }

    /// <summary>편집 창처럼 단축키 칸이 든 모달 창이 열려 있는 동안 등록을 푼다. 짝을 맞춰 <see cref="EndDialog"/> 를 부른다.</summary>
    public void BeginDialog()
    {
        _dialogs++;
        ApplySuspension();
    }

    public void EndDialog()
    {
        _dialogs = Math.Max(0, _dialogs - 1);
        ApplySuspension();
    }

    private void ApplySuspension()
    {
        if (Suspended)
        {
            _services.Registrar?.Replace([]);
            // 풀려 있으니 다음 Sync 는 같은 계획이어도 다시 등록해야 한다.
            _lastAllRegistered = false;
        }
        else
        {
            Sync();
        }
    }

    private readonly Dictionary<string, bool> _registered = new();
    private IReadOnlyList<HotkeyBinding> _lastBindings = [];
    private IReadOnlyList<HotkeyFailure> _lastFailures = [];
    private bool _lastAllRegistered;

    private bool Registered(string key) => _registered.GetValueOrDefault(key);

    /// <summary>
    /// 문서와 전체 적용 단축키에서 등록 대상을 다시 뽑아 통째로 등록하고 목록을 갱신한다.
    /// 프로필 목록이 바뀌었으니 편집 콤보도 함께 다시 만든다. 끝나면 모든 줄을 다시 검사한다 - 다른 프로그램이
    /// 조합을 놓았거나 새로 잡았을 수 있다.
    /// </summary>
    public void Sync()
    {
        RebuildChoices();
        try
        {
            // 입력 중이거나 편집 창이 열려 있으면 등록을 풀어 둔다. 계획은 다시 뽑지 않고, 풀 때 한 번에 맞춘다.
            if (!Suspended) Register();
        }
        finally
        {
            Recheck();
        }
    }

    private void Register()
    {
        var plan = _owner.PlanHotkeys();
        var bindings = new List<HotkeyBinding>();
        if (_applyAll.Enabled && HotkeyCombination.TryParse(_applyAll.Combination, out var all))
        {
            bindings.Add(new HotkeyBinding(HotkeyAction.ApplyAllProfiles, all, _applyAll.Combination, null,
                _text("Hotkeys.ApplyAll.Label")));
        }
        bindings.AddRange(plan.Bindings);

        // 적용 횟수 저장처럼 단축키와 무관한 변경마다 등록을 지웠다 다시 하지 않는다 - 눌러서 실행하는 도중에
        // 자기 등록이 사라졌다 돌아온다. 같은 계획이고 전부 성공했으면 그대로 둔다(실패가 있으면 다시 시도한다).
        if (_lastAllRegistered && bindings.SequenceEqual(_lastBindings) && plan.Failures.SequenceEqual(_lastFailures))
            return;
        _lastBindings = bindings;
        _lastFailures = plan.Failures;

        Rows.Clear();
        _registered.Clear();
        ApplyAllState = "";

        var registrar = _services.Registrar;
        _lastAllRegistered = false;
        if (registrar is not null)
        {
            var results = registrar.Replace(bindings);
            _lastAllRegistered = results.All(r => r.Registered);
            foreach (var result in results)
            {
                var binding = result.Binding;
                var state = result.Registered ? _text("Hotkeys.State.Registered") : DescribeFailure(result.ErrorCode);
                if (binding.Action == HotkeyAction.ApplyAllProfiles)
                {
                    _registered[ApplyAllRegistrationKey] = result.Registered;
                    ApplyAllState = state;
                }
                else
                {
                    Rows.Add(new HotkeyStatusRow(binding.Label, binding.Text, ActionText(binding.Action), state, !result.Registered));
                }
            }
        }

        // 계획 단계에서 걸러진 것도 보인다 - 조용히 빠지면 왜 안 눌리는지 알 길이 없다.
        foreach (var failure in plan.Failures)
            Rows.Add(new HotkeyStatusRow(failure.Label, failure.Text, "", DescribeFailure(failure), IsProblem: true));

        if (_applyAll.Enabled && !HotkeyCombination.TryParse(_applyAll.Combination, out _))
            ApplyAllState = _text("Hotkeys.State.Invalid");
    }

    private void RebuildChoices()
    {
        var keep = SelectedProfile?.Id;
        _rebuildingChoices = true;
        try
        {
            ProfileChoices.Clear();
            foreach (var row in _owner.Profiles.Where(p => !p.IsUnreadable))
                ProfileChoices.Add(new HotkeyProfileChoice(row.Id, row.Name));
        }
        finally
        {
            _rebuildingChoices = false;
        }

        // 지운 프로필이면 비운다. 같은 프로필이면 record 값 비교가 같아 선택 알림이 없으므로 여기서 문서가 바뀌었는지 본다.
        SelectedProfile = keep is null ? null : ProfileChoices.FirstOrDefault(c => c.Id == keep);
        LoadEditor(force: false);
    }

    private string ActionText(HotkeyAction action) => _text("Hotkey.Action." + HotkeyActions.ToKey(action));

    private string DescribeFailure(int errorCode) => errorCode == 1409
        ? _text("Hotkeys.State.InUse")
        : string.Format(_text("Hotkeys.State.Failed"), errorCode);

    private string DescribeFailure(HotkeyFailure failure) => failure.Reason switch
    {
        HotkeyFailureReason.InvalidCombination => _text("Hotkeys.State.Invalid"),
        HotkeyFailureReason.UnknownAction => _text("Hotkeys.State.UnknownAction"),
        HotkeyFailureReason.Duplicate => _text("Hotkeys.State.Duplicate"),
        _ => DescribeFailure(failure.ErrorCode),
    };
}
