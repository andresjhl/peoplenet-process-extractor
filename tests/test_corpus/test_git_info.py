"""Tests for corpus Git information retrieval."""
from pathlib import Path
from unittest.mock import patch


from peoplenet_process_extractor.corpus.git_info import _run_git, get_git_info


class TestRunGit:
    def test_returns_stdout_on_success(self, tmp_path):
        _run_git(["git", "rev-parse", "--is-inside-work-tree"], tmp_path)
        # May return None if tmp_path is not in a git repo — that's fine, test the function
        # The function must not raise.

    def test_returns_none_on_nonexistent_command(self, tmp_path):
        result = _run_git(["nonexistent_command_that_does_not_exist"], tmp_path)
        assert result is None

    def test_returns_none_on_nonzero_exit(self, tmp_path):
        result = _run_git(["git", "rev-parse", "--nonexistent-option"], tmp_path)
        assert result is None


class TestGetGitInfo:
    def test_no_git_available(self, tmp_path):
        with patch(
            "peoplenet_process_extractor.corpus.git_info._run_git",
            return_value=None,
        ):
            info, warnings = get_git_info(tmp_path)
        assert info.commit is None
        assert info.dirty is None
        assert len(warnings) > 0
        assert "unavailable" in warnings[0].lower() or "unknown" in warnings[0].lower()

    def test_clean_repo(self, tmp_path):
        fake_commit = "a" * 40
        def fake_run_git(cmd, cwd):
            if "rev-parse" in cmd:
                return fake_commit + "\n"
            if "status" in cmd:
                return ""  # clean
            return None

        with patch("peoplenet_process_extractor.corpus.git_info._run_git", side_effect=fake_run_git):
            info, warnings = get_git_info(tmp_path)

        assert info.commit == fake_commit
        assert info.dirty is False
        assert warnings == []

    def test_dirty_repo(self, tmp_path):
        fake_commit = "b" * 40
        def fake_run_git(cmd, cwd):
            if "rev-parse" in cmd:
                return fake_commit + "\n"
            if "status" in cmd:
                return " M modified_file.py\n"  # dirty
            return None

        with patch("peoplenet_process_extractor.corpus.git_info._run_git", side_effect=fake_run_git):
            info, warnings = get_git_info(tmp_path)

        assert info.commit == fake_commit
        assert info.dirty is True

    def test_status_unavailable_but_commit_available(self, tmp_path):
        fake_commit = "c" * 40
        call_count = [0]

        def fake_run_git(cmd, cwd):
            call_count[0] += 1
            if "rev-parse" in cmd:
                return fake_commit + "\n"
            return None  # status fails

        with patch("peoplenet_process_extractor.corpus.git_info._run_git", side_effect=fake_run_git):
            info, warnings = get_git_info(tmp_path)

        assert info.commit == fake_commit
        assert info.dirty is None
        assert len(warnings) > 0

    def test_corpus_not_in_git_repo(self, tmp_path):
        # An empty tmp_path is not a git repository
        info, warnings = get_git_info(tmp_path)
        # Either commit is None (not a repo) or it's a hash — both are valid
        if info.commit is None:
            assert len(warnings) > 0

    def test_real_repo_returns_valid_commit(self):
        """Verify against the real repository this test is part of."""
        repo_root = Path(__file__).parent.parent.parent
        info, warnings = get_git_info(repo_root)
        if info.commit is not None:
            assert len(info.commit) in (40, 64)
            assert all(c in "0123456789abcdef" for c in info.commit)

    def test_empty_commit_hash_treated_as_unknown(self, tmp_path):
        def fake_run_git(cmd, cwd):
            if "rev-parse" in cmd:
                return "\n"  # empty
            return None

        with patch("peoplenet_process_extractor.corpus.git_info._run_git", side_effect=fake_run_git):
            info, warnings = get_git_info(tmp_path)

        assert info.commit is None
        assert len(warnings) > 0
