"""ho-ho-helper: a fair and friendly Secret Santa organizer."""

from importlib.metadata import PackageNotFoundError, version

from ho_ho_helper.secret_santa import NoValidAssignmentError, secret_santa

try:
    __version__ = version("ho-ho-helper")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0.0.0"

__all__ = ["NoValidAssignmentError", "__version__", "secret_santa"]
