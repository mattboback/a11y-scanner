# src/scanner/services/html_discovery_service.py
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class HtmlDiscoveryService:
    """Service that discovers HTML files under a given directory."""

    def __init__(self, scan_dir: Path):
        if not isinstance(scan_dir, Path):
            raise TypeError("scan_dir must be a Path object")
        self.scan_dir = scan_dir
        logger.debug(
            "HtmlDiscoveryService initialized with scan_dir: %s",
            self.scan_dir,
        )

    def discover_html_files(self) -> list[dict[str, Path]]:
        """Recursively discover all HTML files relative to scan_dir."""
        logger.info(
            "Recursively discovering HTML files in: %s",
            self.scan_dir,
        )
        if not self.scan_dir.is_dir():
            logger.error(
                "Scan directory does not exist or is not a directory: %s",
                self.scan_dir,
            )
            return []

        html_paths: list[dict[str, Path]] = []
        for pattern in ("*.html", "*.htm"):
            for abs_path in self.scan_dir.rglob(pattern):
                if not abs_path.is_file():
                    continue

                try:
                    relative_path = abs_path.relative_to(self.scan_dir)
                    entry = {
                        "absolute": abs_path.resolve(),
                        "relative": relative_path,
                    }
                    html_paths.append(entry)
                    logger.debug(
                        "Found HTML: Rel=%s,\nAbs=%s",
                        relative_path,
                        abs_path.resolve(),
                    )
                except ValueError:
                    logger.warning(
                        "Could not determine relative path\nfor %s against base %s. "
                        "Skipping.",
                        abs_path,
                        self.scan_dir,
                    )

        count = len(html_paths)
        logger.info(
            "Found %d HTML file(s) in %s",
            count,
            self.scan_dir,
        )

        if count:
            sample_limit = 5
            sample = [str(e["relative"]) for e in html_paths[:sample_limit]]
            logger.debug("Sample relative paths: %s", sample)

            if count > sample_limit:
                logger.debug(
                    "... and %d more.",
                    count - sample_limit,
                )

        return html_paths
