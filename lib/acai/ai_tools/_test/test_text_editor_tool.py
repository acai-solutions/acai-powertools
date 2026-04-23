import os
import unittest

from acai.ai_tools.text_editor_tool import TextEditorTool


class TestPathValidation(unittest.TestCase):
    def test_path_traversal_rejected(self):
        tool = TextEditorTool(base_dir=os.path.normpath("/safe/dir"))
        with self.assertRaises(ValueError):
            tool._validate_path("../../etc/passwd")

    def test_valid_path_accepted(self):
        tool = TextEditorTool(base_dir=os.path.normpath("/safe/dir"))
        result = tool._validate_path("subdir/file.txt")
        self.assertTrue(result.startswith(os.path.normpath("/safe/dir")))


class TestCreate(unittest.TestCase):
    def test_create_new_file(self, tmp_path=None):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            result = tool.create("test.txt", "hello world")
            self.assertIn("Successfully created", result)
            with open(os.path.join(td, "test.txt")) as f:
                self.assertEqual(f.read(), "hello world")

    def test_create_existing_file_raises(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "first")
            with self.assertRaises(FileExistsError):
                tool.create("test.txt", "second")

    def test_create_nested_directory(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            result = tool.create("sub/deep/file.txt", "nested content")
            self.assertIn("Successfully created", result)
            self.assertTrue(os.path.exists(os.path.join(td, "sub", "deep", "file.txt")))


class TestView(unittest.TestCase):
    def test_view_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "line1\nline2\nline3")
            content = tool.view("test.txt")
            self.assertIn("1: line1", content)
            self.assertIn("2: line2", content)
            self.assertIn("3: line3", content)

    def test_view_with_range(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "line1\nline2\nline3\nline4")
            content = tool.view("test.txt", view_range=[2, 3])
            self.assertNotIn("1: line1", content)
            self.assertIn("2: line2", content)
            self.assertIn("3: line3", content)
            self.assertNotIn("4: line4", content)

    def test_view_directory(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("a.txt", "aaa")
            tool.create("b.txt", "bbb")
            content = tool.view(".")
            self.assertIn("a.txt", content)
            self.assertIn("b.txt", content)

    def test_view_nonexistent_raises(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            with self.assertRaises(FileNotFoundError):
                tool.view("nope.txt")


class TestStrReplace(unittest.TestCase):
    def test_replace_unique_match(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "hello world")
            result = tool.str_replace("test.txt", "hello", "goodbye")
            self.assertIn("Successfully replaced", result)
            with open(os.path.join(td, "test.txt")) as f:
                self.assertEqual(f.read(), "goodbye world")

    def test_replace_no_match_raises(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "hello world")
            with self.assertRaises(ValueError):
                tool.str_replace("test.txt", "missing", "new")

    def test_replace_multiple_matches_raises(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "aaa bbb aaa")
            with self.assertRaises(ValueError):
                tool.str_replace("test.txt", "aaa", "ccc")

    def test_replace_creates_backup(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "original content")
            tool.str_replace("test.txt", "original", "modified")
            backups = os.listdir(tool.backup_dir)
            backup_files = [f for f in backups if f.startswith("test.txt.")]
            self.assertGreater(len(backup_files), 0)


class TestInsert(unittest.TestCase):
    def test_insert_at_beginning(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "line1\nline2\n")
            tool.insert("test.txt", 0, "new_first_line")
            with open(os.path.join(td, "test.txt")) as f:
                content = f.read()
            self.assertTrue(content.startswith("new_first_line"))

    def test_insert_in_middle(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "line1\nline2\nline3\n")
            tool.insert("test.txt", 2, "inserted")
            with open(os.path.join(td, "test.txt")) as f:
                lines = f.readlines()
            line_texts = [line.strip() for line in lines]
            self.assertIn("inserted", line_texts)

    def test_insert_out_of_range_raises(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "line1\n")
            with self.assertRaises(IndexError):
                tool.insert("test.txt", 999, "too far")


class TestUndoEdit(unittest.TestCase):
    def test_undo_restores_previous_content(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "original")
            tool.str_replace("test.txt", "original", "modified")
            tool.undo_edit("test.txt")
            with open(os.path.join(td, "test.txt")) as f:
                self.assertEqual(f.read(), "original")

    def test_undo_no_backup_raises(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tool = TextEditorTool(base_dir=td)
            tool.create("test.txt", "content")
            with self.assertRaises(FileNotFoundError):
                tool.undo_edit("test.txt")


class TestFormatLines(unittest.TestCase):
    def test_format_lines(self):
        result = TextEditorTool._format_lines(["a", "b", "c"], start=1)
        self.assertEqual(result, "1: a\n2: b\n3: c")

    def test_format_lines_custom_start(self):
        result = TextEditorTool._format_lines(["x", "y"], start=5)
        self.assertEqual(result, "5: x\n6: y")


class TestCountMatches(unittest.TestCase):
    def test_single_match(self):
        tool = TextEditorTool()
        self.assertEqual(tool._count_matches("hello world", "hello"), 1)

    def test_no_match(self):
        tool = TextEditorTool()
        self.assertEqual(tool._count_matches("hello world", "xyz"), 0)

    def test_multiple_matches(self):
        tool = TextEditorTool()
        self.assertEqual(tool._count_matches("aaa", "a"), 3)


if __name__ == "__main__":
    unittest.main()
