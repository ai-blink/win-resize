"""
Application Compatibility Testing and Optimization System
========================================================

Comprehensive testing framework for verifying window manipulation compatibility
across different application types including games, UWP apps, legacy applications,
browsers, and security-sensitive programs.

Key Features:
- Application type detection and classification
- Specialized handling for different app categories
- Permission and security constraint handling
- Performance optimization for specific app types
- Error recovery and fallback mechanisms
"""

import time
import threading
import psutil
from typing import Dict, List, Optional, Set, Tuple, NamedTuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging
import json

from .window_enumerator import WindowEnumerator, FilterMode, WindowType
from .window_manipulator import WindowManipulator, WindowConstraints
from .uwp_detector import default_uwp_detector

logger = logging.getLogger(__name__)

class ApplicationCategory(Enum):
    """Categories of applications for specialized handling."""
    GAME = "game"
    UWP_APP = "uwp_app"
    OFFICE_APP = "office_app"
    BROWSER = "browser"
    ANTICHEAT = "anticheat"
    SYSTEM_APP = "system_app"
    LEGACY_APP = "legacy_app"
    MEDIA_PLAYER = "media_player"
    IDE_EDITOR = "ide_editor"
    UNKNOWN = "unknown"

class CompatibilityLevel(Enum):
    """Compatibility test result levels."""
    FULL = "full_compatibility"          # All operations work perfectly
    PARTIAL = "partial_compatibility"    # Some limitations but functional
    LIMITED = "limited_compatibility"    # Basic operations only
    RESTRICTED = "restricted_access"     # Security/permission restrictions
    INCOMPATIBLE = "incompatible"       # Cannot manipulate window

@dataclass
class ApplicationSignature:
    """Signature information for application identification."""
    process_names: Set[str] = field(default_factory=set)
    window_classes: Set[str] = field(default_factory=set)
    window_title_patterns: Set[str] = field(default_factory=set)
    executable_paths: Set[str] = field(default_factory=set)
    company_names: Set[str] = field(default_factory=set)
    special_properties: Dict[str, any] = field(default_factory=dict)

@dataclass
class CompatibilityTestResult:
    """Results of compatibility testing for an application."""
    category: ApplicationCategory
    compatibility_level: CompatibilityLevel
    supported_operations: Set[str] = field(default_factory=set)
    failed_operations: Set[str] = field(default_factory=set)
    special_handling_required: bool = False
    recommended_constraints: Optional[WindowConstraints] = None
    performance_notes: List[str] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)
    test_duration: float = 0.0

class ApplicationClassifier:
    """
    Classifies applications into categories for specialized handling.
    """
    
    def __init__(self):
        """Initialize the application classifier with known signatures."""
        self._signatures: Dict[ApplicationCategory, ApplicationSignature] = {}
        self._initialize_signatures()
        
    def _initialize_signatures(self):
        """Initialize application signatures for classification."""
        
        # Gaming applications
        self._signatures[ApplicationCategory.GAME] = ApplicationSignature(
            process_names={
                "steam.exe", "steamwebhelper.exe", "gameoverlayui.exe",
                "origin.exe", "epicgameslauncher.exe", "battlenet.exe",
                "uplay.exe", "gog.exe", "minecraft.exe", "roblox.exe",
                "league of legends.exe", "valorant.exe", "csgo.exe",
                "dota2.exe", "wow.exe", "overwatch.exe"
            },
            window_classes={
                "Valve001", "SDL_app", "UnityWndClass", "UnrealWindow",
                "CryENGINE", "OGRE Render Window"
            },
            executable_paths={
                "steam", "steamapps", "epic games", "battle.net", "ubisoft"
            }
        )
        
        # UWP applications
        self._signatures[ApplicationCategory.UWP_APP] = ApplicationSignature(
            window_classes={
                "ApplicationFrameWindow", "Windows.UI.Core.CoreWindow",
                "WinUIDesktopWin32WindowClass"
            },
            executable_paths={"windowsapps"},
            special_properties={"is_uwp": True}
        )
        
        # Office applications
        self._signatures[ApplicationCategory.OFFICE_APP] = ApplicationSignature(
            process_names={
                "winword.exe", "excel.exe", "powerpnt.exe", "outlook.exe",
                "onenote.exe", "msaccess.exe", "visio.exe", "project.exe",
                "teams.exe", "lync.exe", "skype.exe"
            },
            company_names={"Microsoft Corporation"},
            window_classes={"OpusApp", "XLMAIN", "PP12FrameClass"}
        )
        
        # Browser applications
        self._signatures[ApplicationCategory.BROWSER] = ApplicationSignature(
            process_names={
                "chrome.exe", "firefox.exe", "msedge.exe", "iexplore.exe",
                "opera.exe", "brave.exe", "vivaldi.exe", "safari.exe"
            },
            window_classes={
                "Chrome_WidgetWin_1", "MozillaWindowClass", 
                "ApplicationFrameWindow"  # For Edge
            }
        )
        
        # Anti-cheat and security software
        self._signatures[ApplicationCategory.ANTICHEAT] = ApplicationSignature(
            process_names={
                "battleye.exe", "easyanticheat.exe", "vanguard.exe",
                "faceitac.exe", "esea.exe", "cevo.exe",
                "punkbuster.exe", "xigncode3.exe", "gameguard.exe"
            },
            special_properties={"high_security": True}
        )
        
        # Media players
        self._signatures[ApplicationCategory.MEDIA_PLAYER] = ApplicationSignature(
            process_names={
                "vlc.exe", "wmplayer.exe", "potplayer.exe", "mpc-hc64.exe",
                "spotify.exe", "itunes.exe", "foobar2000.exe"
            }
        )
        
        # IDEs and editors
        self._signatures[ApplicationCategory.IDE_EDITOR] = ApplicationSignature(
            process_names={
                "code.exe", "devenv.exe", "notepad++.exe", "sublime_text.exe",
                "atom.exe", "pycharm64.exe", "idea64.exe", "eclipse.exe"
            }
        )
    
    def classify_application(self, window_info, process_info=None) -> ApplicationCategory:
        """
        Classify an application based on window and process information.
        
        Args:
            window_info: Enhanced window information
            process_info: Optional process information
            
        Returns:
            ApplicationCategory for the application
        """
        try:
            # Check for UWP first
            if window_info.is_uwp_app:
                return ApplicationCategory.UWP_APP
            
            # Get process name
            process_name = ""
            if process_info:
                process_name = process_info.name.lower()
            elif window_info.process_info:
                process_name = window_info.process_info.name.lower()
            
            # Check each signature
            for category, signature in self._signatures.items():
                # Check process names
                if process_name and any(name.lower() in process_name for name in signature.process_names):
                    return category
                
                # Check window classes
                if window_info.class_name in signature.window_classes:
                    return category
                
                # Check window title patterns
                title_lower = window_info.title.lower()
                if any(pattern.lower() in title_lower for pattern in signature.window_title_patterns):
                    return category
                
                # Check executable paths
                if hasattr(window_info, 'process_info') and window_info.process_info:
                    exe_path = window_info.process_info.exe_path.lower()
                    if any(path.lower() in exe_path for path in signature.executable_paths):
                        return category
            
            return ApplicationCategory.UNKNOWN
            
        except Exception as e:
            logger.debug(f"Error classifying application: {e}")
            return ApplicationCategory.UNKNOWN

class CompatibilityTester:
    """
    Comprehensive compatibility testing framework for different application types.
    """
    
    def __init__(self):
        """Initialize the compatibility tester."""
        self.enumerator = WindowEnumerator()
        self.manipulator = WindowManipulator()
        self.classifier = ApplicationClassifier()
        self._test_results: Dict[int, CompatibilityTestResult] = {}
        self._test_operations = [
            "basic_move", "basic_resize", "center_window", "snap_left", "snap_right",
            "minimize", "maximize", "restore", "set_topmost", "transparency"
        ]
    
    def run_comprehensive_test(self) -> Dict[ApplicationCategory, List[CompatibilityTestResult]]:
        """
        Run comprehensive compatibility tests across all running applications.
        
        Returns:
            Dictionary mapping categories to test results
        """
        logger.info("Starting comprehensive application compatibility test")
        
        # Get all user windows
        windows = self.enumerator.enumerate_windows(
            FilterMode.USER_WINDOWS, 
            include_process_info=True
        )
        
        results_by_category: Dict[ApplicationCategory, List[CompatibilityTestResult]] = {}
        
        for window in windows:
            try:
                # Classify the application
                category = self.classifier.classify_application(window)
                
                # Run compatibility test
                test_result = self._test_window_compatibility(window, category)
                
                # Store results
                if category not in results_by_category:
                    results_by_category[category] = []
                results_by_category[category].append(test_result)
                
                logger.debug(f"Tested {window.title[:40]} - Category: {category.value}, "
                           f"Compatibility: {test_result.compatibility_level.value}")
                
            except Exception as e:
                logger.error(f"Error testing window {window.hwnd}: {e}")
        
        # Generate summary
        self._generate_compatibility_report(results_by_category)
        
        return results_by_category
    
    def _test_window_compatibility(self, window_info, category: ApplicationCategory) -> CompatibilityTestResult:
        """
        Test compatibility for a specific window.
        
        Args:
            window_info: Window information
            category: Application category
            
        Returns:
            CompatibilityTestResult with test outcomes
        """
        start_time = time.time()
        
        result = CompatibilityTestResult(
            category=category,
            compatibility_level=CompatibilityLevel.INCOMPATIBLE
        )
        
        # Get original window state for restoration
        original_rect = window_info.rect
        hwnd = window_info.hwnd
        
        try:
            # Test basic operations based on category
            if category == ApplicationCategory.ANTICHEAT:
                result = self._test_anticheat_compatibility(hwnd, result)
            elif category == ApplicationCategory.GAME:
                result = self._test_game_compatibility(hwnd, result)
            elif category == ApplicationCategory.UWP_APP:
                result = self._test_uwp_compatibility(hwnd, result)
            elif category == ApplicationCategory.BROWSER:
                result = self._test_browser_compatibility(hwnd, result)
            else:
                result = self._test_standard_compatibility(hwnd, result)
            
            # Restore original position if we moved it
            try:
                self.manipulator.move_window(
                    hwnd, original_rect.left, original_rect.top,
                    original_rect.width, original_rect.height
                )
            except:
                pass  # Ignore restoration errors
                
        except Exception as e:
            result.error_messages.append(f"Test error: {str(e)}")
            result.compatibility_level = CompatibilityLevel.INCOMPATIBLE
        
        result.test_duration = time.time() - start_time
        return result
    
    def _test_standard_compatibility(self, hwnd: int, result: CompatibilityTestResult) -> CompatibilityTestResult:
        """Test standard window compatibility."""
        operations_tested = 0
        operations_passed = 0
        
        test_cases = [
            ("basic_move", lambda: self.manipulator.move_window(hwnd, 200, 200)),
            ("basic_resize", lambda: self.manipulator.resize_window(hwnd, 600, 400)),
            ("center_window", lambda: self.manipulator.center_window(hwnd)),
            ("snap_left", lambda: self.manipulator.snap_to_edge(hwnd, "left")),
        ]
        
        for operation_name, test_func in test_cases:
            operations_tested += 1
            try:
                if test_func():
                    result.supported_operations.add(operation_name)
                    operations_passed += 1
                    time.sleep(0.1)  # Small delay between operations
                else:
                    result.failed_operations.add(operation_name)
            except Exception as e:
                result.failed_operations.add(operation_name)
                result.error_messages.append(f"{operation_name}: {str(e)}")
        
        # Determine compatibility level
        success_rate = operations_passed / operations_tested if operations_tested > 0 else 0
        
        if success_rate >= 0.9:
            result.compatibility_level = CompatibilityLevel.FULL
        elif success_rate >= 0.7:
            result.compatibility_level = CompatibilityLevel.PARTIAL
        elif success_rate >= 0.5:
            result.compatibility_level = CompatibilityLevel.LIMITED
        else:
            result.compatibility_level = CompatibilityLevel.INCOMPATIBLE
        
        return result
    
    def _test_game_compatibility(self, hwnd: int, result: CompatibilityTestResult) -> CompatibilityTestResult:
        """Test game-specific compatibility with special handling."""
        result.special_handling_required = True
        
        # Games often need special constraints
        game_constraints = WindowConstraints(
            min_width=640,
            min_height=480,
            keep_on_screen=True,
            respect_work_area=False  # Games might want full screen access
        )
        result.recommended_constraints = game_constraints
        
        # Test basic operations with game constraints
        operations_tested = 0
        operations_passed = 0
        
        try:
            # Test move with constraints
            operations_tested += 1
            if self.manipulator.move_window(hwnd, 100, 100, constraints=game_constraints):
                result.supported_operations.add("constrained_move")
                operations_passed += 1
            else:
                result.failed_operations.add("constrained_move")
            
            # Games might not support centering due to exclusive fullscreen
            operations_tested += 1
            try:
                if self.manipulator.center_window(hwnd):
                    result.supported_operations.add("center_window")
                    operations_passed += 1
                else:
                    result.failed_operations.add("center_window")
            except:
                result.failed_operations.add("center_window")
                result.performance_notes.append("Game may be in exclusive fullscreen mode")
        
        except Exception as e:
            result.error_messages.append(f"Game test error: {str(e)}")
        
        # Game-specific compatibility determination
        if operations_passed >= operations_tested * 0.5:
            result.compatibility_level = CompatibilityLevel.PARTIAL
            result.performance_notes.append("Games may have limited window manipulation in fullscreen mode")
        else:
            result.compatibility_level = CompatibilityLevel.LIMITED
            result.performance_notes.append("Game window manipulation restricted - likely exclusive fullscreen")
        
        return result
    
    def _test_uwp_compatibility(self, hwnd: int, result: CompatibilityTestResult) -> CompatibilityTestResult:
        """Test UWP application compatibility."""
        result.special_handling_required = True
        result.performance_notes.append("UWP apps have containerized window management")
        
        # UWP apps have different constraints
        uwp_constraints = WindowConstraints(
            min_width=320,
            min_height=240,
            keep_on_screen=True,
            respect_work_area=True
        )
        result.recommended_constraints = uwp_constraints
        
        # Test UWP-specific operations
        operations_tested = 0
        operations_passed = 0
        
        test_cases = [
            ("uwp_resize", lambda: self.manipulator.resize_window(hwnd, 800, 600)),
            ("uwp_center", lambda: self.manipulator.center_window(hwnd)),
        ]
        
        for operation_name, test_func in test_cases:
            operations_tested += 1
            try:
                if test_func():
                    result.supported_operations.add(operation_name)
                    operations_passed += 1
                else:
                    result.failed_operations.add(operation_name)
            except Exception as e:
                result.failed_operations.add(operation_name)
                result.error_messages.append(f"{operation_name}: {str(e)}")
        
        # UWP compatibility determination
        if operations_passed >= operations_tested * 0.7:
            result.compatibility_level = CompatibilityLevel.PARTIAL
        else:
            result.compatibility_level = CompatibilityLevel.LIMITED
        
        return result
    
    def _test_browser_compatibility(self, hwnd: int, result: CompatibilityTestResult) -> CompatibilityTestResult:
        """Test browser-specific compatibility."""
        # Browsers usually have good compatibility but special tab handling
        result.performance_notes.append("Browser windows support standard operations")
        
        return self._test_standard_compatibility(hwnd, result)
    
    def _test_anticheat_compatibility(self, hwnd: int, result: CompatibilityTestResult) -> CompatibilityTestResult:
        """Test anti-cheat software compatibility."""
        result.special_handling_required = True
        result.performance_notes.append("Anti-cheat software may block window manipulation")
        
        # Very limited testing for anti-cheat software
        try:
            # Just try to get window info - don't attempt manipulation
            window_info = self.manipulator.get_window_constraints_info(hwnd)
            if window_info:
                result.supported_operations.add("info_query")
                result.compatibility_level = CompatibilityLevel.RESTRICTED
            else:
                result.compatibility_level = CompatibilityLevel.INCOMPATIBLE
        except Exception as e:
            result.error_messages.append(f"Anti-cheat restriction: {str(e)}")
            result.compatibility_level = CompatibilityLevel.INCOMPATIBLE
        
        return result
    
    def _generate_compatibility_report(self, results: Dict[ApplicationCategory, List[CompatibilityTestResult]]):
        """Generate and save compatibility report."""
        report = {
            "test_timestamp": time.time(),
            "total_applications_tested": sum(len(apps) for apps in results.values()),
            "categories": {}
        }
        
        for category, test_results in results.items():
            if not test_results:
                continue
                
            category_stats = {
                "count": len(test_results),
                "compatibility_distribution": {},
                "common_supported_operations": set(),
                "common_failed_operations": set(),
                "average_test_duration": 0
            }
            
            # Calculate statistics
            for result in test_results:
                compat_level = result.compatibility_level.value
                category_stats["compatibility_distribution"][compat_level] = \
                    category_stats["compatibility_distribution"].get(compat_level, 0) + 1
                
                category_stats["common_supported_operations"].update(result.supported_operations)
                category_stats["common_failed_operations"].update(result.failed_operations)
                category_stats["average_test_duration"] += result.test_duration
            
            if test_results:
                category_stats["average_test_duration"] /= len(test_results)
            
            # Convert sets to lists for JSON serialization
            category_stats["common_supported_operations"] = list(category_stats["common_supported_operations"])
            category_stats["common_failed_operations"] = list(category_stats["common_failed_operations"])
            
            report["categories"][category.value] = category_stats
        
        # Save report
        report_path = Path("compatibility_report.json")
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Compatibility report saved to {report_path}")
        except Exception as e:
            logger.error(f"Failed to save compatibility report: {e}")
        
        # Print summary
        self._print_compatibility_summary(report)
    
    def _print_compatibility_summary(self, report: Dict):
        """Print compatibility test summary to console."""
        print("\n" + "="*70)
        print("APPLICATION COMPATIBILITY TEST SUMMARY")
        print("="*70)
        
        print(f"Total applications tested: {report['total_applications_tested']}")
        
        for category_name, stats in report["categories"].items():
            print(f"\n[{category_name.upper()}] - {stats['count']} applications:")
            
            # Show compatibility distribution
            for compat_level, count in stats["compatibility_distribution"].items():
                percentage = (count / stats["count"]) * 100
                print(f"  {compat_level}: {count} ({percentage:.1f}%)")
            
            # Show common operations
            if stats["common_supported_operations"]:
                ops = ", ".join(stats["common_supported_operations"][:3])
                print(f"  Supported: {ops}{'...' if len(stats['common_supported_operations']) > 3 else ''}")
            
            print(f"  Avg test time: {stats['average_test_duration']:.3f}s")

# Default instance
default_compatibility_tester = CompatibilityTester()

# Convenience functions
def run_compatibility_test() -> Dict[ApplicationCategory, List[CompatibilityTestResult]]:
    """Run comprehensive compatibility test using default tester."""
    return default_compatibility_tester.run_comprehensive_test()

def classify_window(window_info) -> ApplicationCategory:
    """Classify a window using default classifier."""
    return default_compatibility_tester.classifier.classify_application(window_info)