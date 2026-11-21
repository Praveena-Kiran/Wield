"""
Coding Studio: the apps, files, folders and websites you code with,
opened together. The list is editable (add / remove) and saved as the
"coding_flow" steps in flows.json.
"""

import json
from typing import Optional

from PySide6.QtWidgets import QWidget

from backend.automation.flow_manager import FlowManager
from backend.paths import user_config_path
from frontend.components.launch_list import LaunchListWidget
from frontend.pages.studio_page import StudioPage


FLOW = "coding_flow"


def _show_on_home(title, labels):
    """Keep the studio's app names on Home in step with its list."""

    path = user_config_path("studios.json")
    try:
        with open(path, encoding="utf-8") as f:
            studios = json.load(f)
        for studio in studios:
            if studio.get("title") == title:
                studio["apps"] = labels[:4]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(studios, f, indent=4, ensure_ascii=False)
    except (OSError, ValueError, AttributeError):
        pass


class CodingPage(StudioPage):
    """Coding Studio workspace."""

    def __init__(self, parent: Optional[QWidget] = None):

        super().__init__(
            "Coding Studio",
            "Open your whole coding setup in one go. Add the apps, project "
            "folders, files and websites you use.",
            parent,
        )

        self.flow_manager = FlowManager()

        self.launch_list = LaunchListWidget(
            "Your workspace",
            "Launch all opens everything below. Use + Add for anything else, "
            "like a project folder or your docs site.",
        )
        self.launch_list.set_items(self.flow_manager.flow_items(FLOW))
        self.launch_list.changed.connect(self._save)

        self.content_layout.addWidget(self.launch_list)
        self.content_layout.addStretch()

        # Kept for anything that still calls it (and the old button name).
        self.launch_button = self.launch_list.launch_button

    def _save(self, items):
        try:
            self.flow_manager.save_flow_items(FLOW, items, name="Coding Flow")
            _show_on_home("Coding Studio", [item["label"] for item in items])
            self.status_label.setText("Status: Saved.")
        except OSError as e:
            self.status_label.setText(f"Status: Couldn't save ({e}).")

    def _launch_workspace(self):
        return self.launch_list.launch()
