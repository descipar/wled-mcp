"""The shared symlink helper skips for a missing privilege and never hides a real error."""

import pytest

from tests.symlink_support import symlink_or_skip


def fail_with(error):
    def raiser(*_args, **_kwargs):
        raise error

    return raiser


def test_a_host_without_the_symlink_privilege_skips_with_a_reason(tmp_path, monkeypatch):
    error = OSError(1314, "A required privilege is not held by the client")
    monkeypatch.setattr(type(tmp_path), "symlink_to", fail_with(error))
    with pytest.raises(pytest.skip.Exception, match="cannot create symbolic links"):
        symlink_or_skip(tmp_path / "link", tmp_path)


@pytest.mark.parametrize("error", [FileExistsError("taken"), FileNotFoundError("no parent")])
def test_a_real_error_is_not_turned_into_a_skip(tmp_path, monkeypatch, error):
    monkeypatch.setattr(type(tmp_path), "symlink_to", fail_with(error))
    with pytest.raises(type(error)):
        symlink_or_skip(tmp_path / "link", tmp_path)
