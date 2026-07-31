#!/usr/bin/env python3
"""Focused regression test for close-to-tray behavior."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC_DIR = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QApplication

from gui.main_window import WindowResizerMainWindow


class FakeTrayIcon:
    def __init__(self):
        self.messages = []
        self.hidden = False

    def isVisible(self):
        return True

    def showMessage(self, *args):
        self.messages.append(args)

    def hide(self):
        self.hidden = True


class CloseToTrayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindowResizerMainWindow()
        self.fake_tray_icon = FakeTrayIcon()
        self.window.tray_icon = self.fake_tray_icon

    def tearDown(self):
        if not self.window._quit_requested:
            self.window._quit_requested = True
            self.window.close()

    def test_close_hides_in_tray_and_explicit_exit_cleans_up(self):
        close_event = QCloseEvent()
        self.window.closeEvent(close_event)

        self.assertFalse(close_event.isAccepted())
        self.assertEqual(len(self.fake_tray_icon.messages), 1)

        self.window._quit_requested = True
        quit_event = QCloseEvent()
        self.window.closeEvent(quit_event)

        self.assertTrue(quit_event.isAccepted())
        self.assertTrue(self.fake_tray_icon.hidden)


if __name__ == "__main__":
    unittest.main()
