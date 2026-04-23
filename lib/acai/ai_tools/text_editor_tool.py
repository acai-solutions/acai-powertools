# Implementation of the TextEditorTool

from __future__ import annotations

import os
import shutil


class TextEditorTool:
    def __init__(self, base_dir: str = "", backup_dir: str = "") -> None:
        self.base_dir = base_dir or os.getcwd()
        self.backup_dir = backup_dir or os.path.join(self.base_dir, ".backups")
        os.makedirs(self.backup_dir, exist_ok=True)

    def _validate_path(self, file_path: str) -> str:
        abs_path = os.path.normpath(os.path.join(self.base_dir, file_path))
        if not abs_path.startswith(self.base_dir):
            raise ValueError(
                f"Access denied: Path '{file_path}' is outside the allowed directory"
            )
        return abs_path

    def _backup_file(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return ""
        file_name = os.path.basename(file_path)
        backup_path = os.path.join(
            self.backup_dir, f"{file_name}.{os.path.getmtime(file_path):.0f}"
        )
        shutil.copy2(file_path, backup_path)
        return backup_path

    def _restore_backup(self, file_path: str) -> str:
        file_name = os.path.basename(file_path)
        backups = [
            f for f in os.listdir(self.backup_dir) if f.startswith(file_name + ".")
        ]
        if not backups:
            raise FileNotFoundError(f"No backups found for {file_path}")

        latest_backup = sorted(backups, reverse=True)[0]
        backup_path = os.path.join(self.backup_dir, latest_backup)

        shutil.copy2(backup_path, file_path)
        return f"Successfully restored {file_path} from backup"

    def _count_matches(self, content: str, old_str: str) -> int:
        return content.count(old_str)

    @staticmethod
    def _format_lines(lines: list[str], start: int = 1) -> str:
        return "\n".join(f"{i}: {line}" for i, line in enumerate(lines, start))

    def _view_directory(self, abs_path: str) -> str:
        try:
            return "\n".join(os.listdir(abs_path))
        except PermissionError:
            raise PermissionError("Permission denied. Cannot list directory contents.")

    def _view_file(self, abs_path: str, view_range: list[int] | None) -> str:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")

        if view_range:
            start, end = view_range
            if end == -1:
                end = len(lines)
            return self._format_lines(lines[start - 1 : end], start)

        return self._format_lines(lines)

    def view(self, file_path: str, view_range: list[int] | None = None) -> str:
        abs_path = self._validate_path(file_path)

        if os.path.isdir(abs_path):
            return self._view_directory(abs_path)

        if not os.path.exists(abs_path):
            raise FileNotFoundError("File not found")

        return self._view_file(abs_path, view_range)

    def str_replace(self, file_path: str, old_str: str, new_str: str) -> str:
        try:
            abs_path = self._validate_path(file_path)

            if not os.path.exists(abs_path):
                raise FileNotFoundError("File not found")

            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            match_count = self._count_matches(content, old_str)

            if match_count == 0:
                raise ValueError(
                    "No match found for replacement. Please check your text and try again."
                )
            elif match_count > 1:
                raise ValueError(
                    f"Found {match_count} matches for replacement text. Please provide more context to make a unique match."
                )

            # Create backup before modifying
            self._backup_file(abs_path)

            # Perform the replacement
            new_content = content.replace(old_str, new_str)

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return "Successfully replaced text at exactly one location."

        except ValueError as e:
            raise ValueError(str(e))
        except PermissionError:
            raise PermissionError("Permission denied. Cannot modify file.")
        except Exception as e:
            raise type(e)(str(e))

    def create(self, file_path: str, file_text: str) -> str:
        try:
            abs_path = self._validate_path(file_path)

            # Check if file already exists
            if os.path.exists(abs_path):
                raise FileExistsError(
                    "File already exists. Use str_replace to modify it."
                )

            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)

            # Create the file
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(file_text)

            return f"Successfully created {file_path}"

        except ValueError as e:
            raise ValueError(str(e))
        except PermissionError:
            raise PermissionError("Permission denied. Cannot create file.")
        except Exception as e:
            raise type(e)(str(e))

    def insert(self, file_path: str, insert_line: int, new_str: str) -> str:
        try:
            abs_path = self._validate_path(file_path)

            if not os.path.exists(abs_path):
                raise FileNotFoundError("File not found")

            # Create backup before modifying
            self._backup_file(abs_path)

            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Handle line endings
            if lines and not lines[-1].endswith("\n"):
                new_str = "\n" + new_str

            # Insert at the beginning if insert_line is 0
            if insert_line == 0:
                lines.insert(0, new_str + "\n")
            # Insert after the specified line
            elif insert_line > 0 and insert_line <= len(lines):
                lines.insert(insert_line, new_str + "\n")
            else:
                raise IndexError(
                    f"Line number {insert_line} is out of range. File has {len(lines)} lines."
                )

            with open(abs_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            return f"Successfully inserted text after line {insert_line}"

        except ValueError as e:
            raise ValueError(str(e))
        except PermissionError:
            raise PermissionError("Permission denied. Cannot modify file.")
        except Exception as e:
            raise type(e)(str(e))

    def undo_edit(self, file_path: str) -> str:
        try:
            abs_path = self._validate_path(file_path)

            if not os.path.exists(abs_path):
                raise FileNotFoundError("File not found")

            return self._restore_backup(abs_path)

        except ValueError as e:
            raise ValueError(str(e))
        except FileNotFoundError:
            raise FileNotFoundError("No previous edits to undo")
        except PermissionError:
            raise PermissionError("Permission denied. Cannot restore file.")
        except Exception as e:
            raise type(e)(str(e))
