import ctypes
import datetime
import os
import subprocess
import webbrowser
from typing import Any, Optional

from .clipboard import ClipboardManager
from .launcher import ApplicationLauncher
from .keyboard import KeyboardController
from .mouse import MouseController
from .window import WindowManager
from .workflow import DesktopWorkflow

try:
    import pyautogui
except ImportError:
    pyautogui = None


class DesktopController:
    """A reusable desktop controller for EchoDesk.

    DesktopController provides modular desktop actions such as moving the mouse,
    clicking buttons, typing text, opening applications and websites, taking
    screenshots, and querying the currently active window.
    """

    VALID_BUTTONS = {"left", "right", "middle"}

    def __init__(
        self,
        launcher: Optional[ApplicationLauncher] = None,
        mouse_controller: Optional[MouseController] = None,
        keyboard_controller: Optional[KeyboardController] = None,
        window_manager: Optional[WindowManager] = None,
        clipboard_manager: Optional[ClipboardManager] = None,
        workflow: Optional[DesktopWorkflow] = None,
    ) -> None:
        """Initialize the desktop controller."""
        self.pyautogui = pyautogui
        self.ctypes = ctypes if hasattr(ctypes, "windll") else None
        self.launcher = launcher or ApplicationLauncher()
        self.mouse = mouse_controller or MouseController()
        self.keyboard = keyboard_controller or KeyboardController()
        self.window_manager = window_manager or WindowManager()
        self.clipboard = clipboard_manager or ClipboardManager()
        self.workflow = workflow or DesktopWorkflow(self)

    def move_mouse(self, x: int, y: int) -> dict[str, Any]:
        """Move the mouse cursor to the specified screen coordinates."""
        return self.mouse.move(x, y)

    def click_mouse(self, button: str = "left") -> dict[str, Any]:
        """Perform a mouse click with the specified button."""
        return self.mouse.click(button)

    def double_click_mouse(self, button: str = "left") -> dict[str, Any]:
        """Perform a double click with the specified button."""
        return self.mouse.double_click(button)

    def drag_mouse(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 1.0) -> dict[str, Any]:
        """Drag the mouse from one coordinate to another."""
        return self.mouse.drag(start_x, start_y, end_x, end_y, duration)

    def scroll_mouse(self, amount: int) -> dict[str, Any]:
        """Scroll the mouse wheel by a given amount."""
        return self.mouse.scroll(amount)

    def mouse_position(self) -> dict[str, Any]:
        """Get the current mouse cursor position."""
        return self.mouse.position()

    def left_click(self) -> dict[str, Any]:
        """Perform a left mouse click."""
        return self.mouse.click("left")

    def right_click(self) -> dict[str, Any]:
        """Perform a right mouse click."""
        return self.mouse.click("right")

    def middle_click(self) -> dict[str, Any]:
        """Perform a middle mouse click."""
        return self.mouse.click("middle")

    def double_click(self) -> dict[str, Any]:
        """Perform a double mouse click."""
        return self.mouse.double_click("left")

    def scroll(self, amount: int) -> dict[str, Any]:
        """Scroll the mouse wheel by a given amount."""
        return self.mouse.scroll(amount)

    def type_text(self, text: str) -> dict[str, Any]:
        """Type text using the keyboard."""
        return self.keyboard.type_text(text)

    def press_key(self, key: str) -> dict[str, Any]:
        """Press a single keyboard key."""
        return self.keyboard.press_key(key)

    def hotkey(self, *keys: str) -> dict[str, Any]:
        """Press a key combination as a hotkey."""
        return self.keyboard.hotkey(*keys)

    def copy_text(self) -> dict[str, Any]:
        """Copy the current selection to the clipboard."""
        return self.keyboard.copy()

    def paste_text(self) -> dict[str, Any]:
        """Paste from the clipboard."""
        return self.keyboard.paste()

    def undo(self) -> dict[str, Any]:
        """Undo the last action."""
        return self.keyboard.undo()

    def redo(self) -> dict[str, Any]:
        """Redo the last undone action."""
        return self.keyboard.redo()

    def open_application(self, name: str) -> dict[str, Any]:
        """Open an application using the launcher subsystem."""
        return self.launcher.launch(name)

    def supported_applications(self) -> dict[str, Any]:
        """Return the supported desktop applications."""
        return self._success(
            "supported_applications",
            "Supported applications retrieved.",
            result=self.launcher.list_supported(),
        )

    def active_window(self) -> dict[str, Any]:
        """Return structured information about the currently active window."""
        return self.window_manager.active_window()

    def list_windows(self) -> dict[str, Any]:
        """Return a list of available window titles."""
        return self.window_manager.list_windows()

    def focus_window(self, title: str) -> dict[str, Any]:
        """Bring a window with the given title to the foreground."""
        return self.window_manager.focus_window(title)

    def minimize_window(self, title: str) -> dict[str, Any]:
        """Minimize a visible window by title."""
        return self.window_manager.minimize_window(title)

    def maximize_window(self, title: str) -> dict[str, Any]:
        """Maximize a visible window by title."""
        return self.window_manager.maximize_window(title)

    def restore_window(self, title: str) -> dict[str, Any]:
        """Restore a minimized or hidden window by title."""
        return self.window_manager.restore_window(title)

    def close_window(self, title: str, confirm: bool = False) -> dict[str, Any]:
        """Close a window safely by title with explicit confirmation."""
        return self.window_manager.close_window(title, confirm=confirm)

    def switch_window(self, title: str) -> dict[str, Any]:
        """Switch focus to another window by title."""
        return self.window_manager.switch_window(title)

    def get_clipboard(self) -> dict[str, Any]:
        """Read the current clipboard contents."""
        return self.clipboard.get_text()

    def set_clipboard(self, text: str) -> dict[str, Any]:
        """Write text to the clipboard."""
        return self.clipboard.set_text(text)

    def copy_clipboard(self) -> dict[str, Any]:
        """Copy the current clipboard contents into the clipboard manager context."""
        return self.clipboard.copy()

    def paste_clipboard(self) -> dict[str, Any]:
        """Return current clipboard content for paste operations."""
        return self.clipboard.paste()

    def clear_clipboard(self) -> dict[str, Any]:
        """Clear the clipboard contents."""
        return self.clipboard.clear()

    def clipboard_available(self) -> dict[str, Any]:
        """Check whether clipboard operations are available."""
        return self.clipboard.available()

    def execute_workflow(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        """Execute a workflow composed of desktop actions."""
        return self.workflow.execute(actions)

    def available_workflow_actions(self) -> list[str]:
        """Return the available desktop workflow actions."""
        return self.workflow.available_actions()

    def is_application_installed(self, name: str) -> dict[str, Any]:
        """Return whether the requested application is installed."""
        installed = self.launcher.is_installed(name)
        return self._success(
            "is_application_installed",
            f"Application '{name}' is {'installed' if installed else 'not installed'}.",
            result=installed,
        )

    def open_website(self, url: str) -> dict[str, Any]:
        """Open a website in the default web browser."""
        if not isinstance(url, str) or not url.strip():
            return self._error("No website URL was provided.")

        normalized = url.strip()
        if not normalized.startswith(("http://", "https://")):
            normalized = f"https://{normalized}"

        try:
            opened = webbrowser.open(normalized)
            if not opened:
                raise RuntimeError("Browser did not open the URL.")
        except Exception as exc:
            return self._error("Failed to open the website.", details=str(exc))

        return self._success("open_website", f"Opened website: {normalized}.")

    def close_application(self, name: str) -> dict[str, Any]:
        """Close an application by name."""
        if not isinstance(name, str) or not name.strip():
            return self._error("No application name was provided.")

        process_name = name.strip()
        try:
            if os.name == "nt":
                completed = subprocess.run(
                    ["taskkill", "/IM", process_name, "/F"],
                    capture_output=True,
                    text=True,
                )
            else:
                completed = subprocess.run(
                    ["pkill", "-f", process_name],
                    capture_output=True,
                    text=True,
                )

            if completed.returncode == 0:
                return self._success("close_application", f"Closed application: {process_name}.")

            return self._error(
                "Failed to close the application.",
                details=completed.stderr.strip() or completed.stdout.strip() or "No matching process found.",
            )
        except Exception as exc:
            return self._error("Failed to close the application.", details=str(exc))

    def take_screenshot(self) -> dict[str, Any]:
        """Take a screenshot and save it to a PNG file."""
        if self.pyautogui:
            try:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
                screenshot = self.pyautogui.screenshot()
                screenshot.save(filename)
                return self._success("take_screenshot", f"Screenshot saved to {filename}.", result=filename)
            except Exception as exc:
                return self._error("Failed to take a screenshot.", details=str(exc))

        return self._error("Screenshots are not supported in this environment.")

    def get_active_window(self) -> dict[str, Any]:
        """Return the title of the currently active window."""
        if self.pyautogui:
            window_getter = getattr(self.pyautogui, "getActiveWindow", None)
            if callable(window_getter):
                try:
                    window = window_getter()
                    title = getattr(window, "title", None)
                    if title:
                        return self._success("get_active_window", "Active window retrieved.", result=title)
                except Exception:
                    pass

        if self.ctypes and os.name == "nt":
            try:
                hwnd = self.ctypes.windll.user32.GetForegroundWindow()
                length = self.ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buffer = self.ctypes.create_unicode_buffer(length + 1)
                self.ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value
                if title:
                    return self._success("get_active_window", "Active window retrieved.", result=title)
            except Exception as exc:
                return self._error("Failed to get the active window.", details=str(exc))

        return self._error("Unable to determine the active window.")

    def click_element(self, element: Any, button: str = "left") -> dict[str, Any]:
        """Click a Vision ``UIElement`` at its center rather than a fixed point."""
        return self._act_on_element(element, "click", button=button)

    def double_click_element(self, element: Any) -> dict[str, Any]:
        """Double click a Vision ``UIElement`` at its semantic target location."""
        return self._act_on_element(element, "double_click")

    def right_click_element(self, element: Any) -> dict[str, Any]:
        """Open the context menu for a Vision ``UIElement``."""
        return self._act_on_element(element, "click", button="right")

    def select_menu_item(self, element: Any) -> dict[str, Any]:
        """Select a semantic menu item after it has been resolved by Vision."""
        return self.click_element(element)

    def type_into_element(self, element: Any, text: str) -> dict[str, Any]:
        """Focus an editable Vision ``UIElement`` and type into it."""
        if not bool(getattr(element, "editable", False)):
            return self._error("The selected UI element is not editable.")
        clicked = self.click_element(element)
        return self.type_text(text) if clicked.get("success") else clicked

    def hover_element(self, element: Any) -> dict[str, Any]:
        center = getattr(element, "center", None)
        return self.move_mouse(*center) if isinstance(center, tuple) and len(center) == 2 else self._error("Invalid UI element target.")

    def scroll_container(self, element: Any, amount: int) -> dict[str, Any]:
        hovered = self.hover_element(element)
        return self.scroll(amount) if hovered.get("success") else hovered

    def drag_element(self, element: Any, destination: Any, duration: float = 1.0) -> dict[str, Any]:
        start, end = getattr(element, "center", None), getattr(destination, "center", None)
        if not (isinstance(start, tuple) and isinstance(end, tuple)):
            return self._error("Invalid UI element target.")
        return self.drag_mouse(*start, *end, duration)

    def _act_on_element(self, element: Any, action: str, button: str = "left") -> dict[str, Any]:
        if not bool(getattr(element, "visible", False)) or not bool(getattr(element, "enabled", False)):
            return self._error("The selected UI element is not available.")
        center = getattr(element, "center", None)
        if not isinstance(center, tuple) or len(center) != 2:
            return self._error("Invalid UI element target.")
        moved = self.move_mouse(*center)
        if not moved.get("success"):
            return moved
        return self.double_click_mouse(button) if action == "double_click" else self.click_mouse(button)

    def _click(self, button: str) -> dict[str, Any]:
        if button not in self.VALID_BUTTONS:
            return self._error(f"Invalid mouse button: {button}.")

        if self.pyautogui:
            try:
                self.pyautogui.click(button=button)
                return self._success(f"{button}_click", f"Performed a {button} click.")
            except Exception as exc:
                return self._error(f"Failed to perform a {button} click.", details=str(exc))

        if self.ctypes:
            try:
                down_flag, up_flag = self._click_flags(button)
                self.ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
                self.ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)
                return self._success(f"{button}_click", f"Performed a {button} click.")
            except Exception as exc:
                return self._error(f"Failed to perform a {button} click.", details=str(exc))

        return self._error(f"Mouse clicks are not supported in this environment.")

    def _click_flags(self, button_name: str) -> tuple[int, int]:
        if button_name == "left":
            return 0x0002, 0x0004
        if button_name == "right":
            return 0x0008, 0x0010
        return 0x0020, 0x0040

    def _success(self, action: str, message: str, result: Any | None = None) -> dict[str, Any]:
        response = {"success": True, "action": action, "message": message}
        if result is not None:
            response["result"] = result
        return response

    def _error(self, message: str, details: str | None = None) -> dict[str, Any]:
        response = {"success": False, "action": "error", "message": message}
        if details:
            response["details"] = details
        return response
