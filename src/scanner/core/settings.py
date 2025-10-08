import logging
from pathlib import Path

logger = logging.getLogger(__name__)
# Basic config in case logging wasn't set up earlier
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class Settings:
    """
    Configuration settings for the scanner application.
    Paths are derived relative to a base path. By default, this is the
    current working directory, making paths portable for CLI tools.
    """

    def __init__(self, root_path: Path | None = None):
        """
        Initializes settings.
        Args:
            root_path: An optional Path object. If provided, this path
                       is used as the base for deriving data directories.
                       If None (default), paths are generated relative to the
                       current working directory (e.g., 'data/scan').
        """
        if root_path is None:
            # Default to relative paths from the CWD. This is more robust for
            # external tools and container environments.
            self._base_path: Path = Path(".")
            logger.debug("Settings initialized using relative base path: '.'")
        else:
            # For tests or specific cases, use the provided path and resolve it.
            self._base_path: Path = root_path.resolve()
            logger.debug(
                "Settings initialized using provided base path: %s", self._base_path
            )

        self._data_dir: Path = self._base_path / "data"
        self._scan_dir: Path = self._data_dir / "scan"
        self._unzip_dir: Path = self._data_dir / "unzip"
        self._results_dir: Path = self._data_dir / "results"

        self._port: int = 8000

    @property
    def base_path(self) -> Path:
        """The base path used for deriving other paths."""
        return self._base_path

    @property
    def data_dir(self) -> Path:
        """Path to the main data directory."""
        return self._data_dir

    @property
    def scan_dir(self) -> Path:
        """Path to the directory for storing extracted scan files."""
        return self._scan_dir

    @property
    def unzip_dir(self) -> Path:
        """Path to the directory containing the zip file to be processed."""
        return self._unzip_dir

    @property
    def results_dir(self) -> Path:
        """Path to the directory for storing scan results."""
        return self._results_dir

    @property
    def port(self) -> int:
        """Port number (currently unused, potential future use)."""
        return self._port

    def __repr__(self):
        # Format paths nicely for representation using repr() for quotes
        return (
            "Settings(\n"
            f"  base_path={str(self.base_path)!r},\n"
            f"  data_dir={str(self.data_dir)!r},\n"
            f"  scan_dir={str(self.scan_dir)!r},\n"
            f"  unzip_dir={str(self.unzip_dir)!r},\n"
            f"  results_dir={str(self.results_dir)!r},\n"
            f"  port={self.port}\n"
            ")"
        )


if __name__ == "__main__":
    # Example usage
    settings = Settings()
