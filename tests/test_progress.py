import unittest

from app.core.enums import TaskStatus
from app.core.progress import get_progress


class ProgressTests(unittest.TestCase):
    def test_draft_saved_progress_is_100(self) -> None:
        self.assertEqual(get_progress(TaskStatus.DRAFT_SAVED), 100)

    def test_generating_progress_is_80(self) -> None:
        self.assertEqual(get_progress(TaskStatus.GENERATING), 80)


if __name__ == "__main__":
    unittest.main()
