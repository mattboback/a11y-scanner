import logging
import os
import sys
from pathlib import Path
from zipfile import ZipFile

logger = logging.getLogger(__name__)


class ZipService:
    """Service to detect a single .zip in a directory and extract it."""

    def __init__(self, *, unzip_dir: Path, scan_dir: Path):
        """
        Args:
            unzip_dir: Directory to search for zip files.
            scan_dir: Directory where zip contents will be extracted.
        """
        self.unzip_dir = unzip_dir
        self.scan_dir = scan_dir

    def detect_zip(self) -> Path:
        """Search unzip_dir for a .zip file and return its Path."""
        logger.info("Checking %s for any valid zip files", self.unzip_dir)
        zips = list(self.unzip_dir.glob("*.zip"))
        logger.info("Found the following zip(s): %s", zips)

        if not zips:
            raise FileNotFoundError(f"No zip files found in {self.unzip_dir}")

        zip_path = zips[0]
        logger.info("Zip file detected: %s", zip_path)
        return zip_path

    def _is_safe_path(self, base_path: Path, target_path: Path) -> bool:
        """
        Check if target_path is safe to extract (prevents Zip Slip).
        Returns False if the path tries to escape the base directory.
        """
        try:
            # Resolve both paths to absolute, normalized forms
            base_abs = base_path.resolve()
            target_abs = target_path.resolve()

            # Check if target is within base (common_path should equal base)
            common = Path(os.path.commonpath([base_abs, target_abs]))
            return common == base_abs
        except (ValueError, OSError):
            return False

    def _sanitize_archive_member(self, member_name: str) -> str | None:
        """
        Sanitize a zip member name, rejecting dangerous paths.
        Returns None if the member should be skipped.
        """
        # Reject absolute paths
        if os.path.isabs(member_name):
            logger.warning("Rejecting absolute path in archive: %s", member_name)
            return None

        # Reject paths with parent directory references
        if ".." in Path(member_name).parts:
            logger.warning("Rejecting path with '..' in archive: %s", member_name)
            return None

        # Normalize the path
        normalized = os.path.normpath(member_name)

        # Double-check no traversal after normalization
        if normalized.startswith("..") or os.path.isabs(normalized):
            logger.warning("Rejecting unsafe normalized path: %s", normalized)
            return None

        return normalized

    def unzip(self, zip_path: Path, destination: Path) -> None:
        """
        Extract zip_path into the destination directory with Zip Slip protection.
        Only extracts members with safe, relative paths.
        """
        logger.info("Attempting extraction of %s to %s", zip_path, destination)

        # Ensure destination directory exists
        destination.mkdir(parents=True, exist_ok=True)

        try:
            with ZipFile(zip_path, "r") as archive:
                # Guard against zip bombs by limiting total uncompressed size
                try:
                    MAX_UNCOMPRESSED = 500 * 1024 * 1024  # 500 MB
                    total_uncompressed = sum(info.file_size for info in archive.infolist())
                    if total_uncompressed > MAX_UNCOMPRESSED:
                        raise RuntimeError(
                            f"Archive expands to {total_uncompressed} bytes (> {MAX_UNCOMPRESSED}). Aborting."
                        )
                except Exception:
                    # If size computation fails, continue but log a warning
                    logger.warning("Could not compute uncompressed archive size for guard check")

                file_list = archive.namelist()
                logger.debug(
                    "Zip contains %d files/directories",
                    len(file_list),
                )

                # Safe extraction with path validation
                extracted_count = 0
                skipped_count = 0

                for member in archive.infolist():
                    # Sanitize the member name
                    safe_name = self._sanitize_archive_member(member.filename)
                    if safe_name is None:
                        skipped_count += 1
                        continue

                    # Compute the target path
                    target_path = destination / safe_name

                    # Verify it's within the destination (double-check)
                    if not self._is_safe_path(destination, target_path):
                        logger.warning(
                            "Rejecting path that escapes destination: %s",
                            member.filename,
                        )
                        skipped_count += 1
                        continue

                    # Extract the member
                    if member.is_dir():
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        # Ensure parent directory exists
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        # Extract file content
                        with archive.open(member) as source:
                            content = source.read()
                            target_path.write_bytes(content)

                    extracted_count += 1

                logger.info(
                    "Extraction completed: %d files extracted, %d skipped",
                    extracted_count,
                    skipped_count,
                )

                if skipped_count > 0:
                    logger.warning(
                        "%d files were skipped due to unsafe paths", skipped_count
                    )

                dirs = [n for n in file_list if n.endswith("/")]
                if dirs:
                    logger.debug(
                        "Zip contains %d directories: %s",
                        len(dirs),
                        dirs[:5],
                    )
        except OSError as error:
            raise RuntimeError(f"Failed to extract {zip_path}") from error

    def run(self) -> None:
        """Detect a zip, unzip it, and log the extracted items."""
        try:
            zip_path = self.detect_zip()
            self.unzip(zip_path, self.scan_dir)

            extracted_items = list(self.scan_dir.glob("**/*"))
            logger.info(
                "Extracted %d items to %s",
                len(extracted_items),
                self.scan_dir,
            )

            for extracted in extracted_items[:10]:
                logger.info("Extracted item: %s", extracted)

            if not any(self.scan_dir.iterdir()):
                raise RuntimeError("Extraction resulted in empty directory")
        except FileNotFoundError as fnf:
            logger.error("No zip found: %s", fnf)
            raise
        except Exception as error:
            logger.error("Zip extraction failed: %s", error)
            raise


if __name__ == "__main__":
    # Standalone invocation for testing/development
    from scanner.core.logging_setup import setup_logging
    from scanner.core.settings import Settings

    setup_logging()
    settings = Settings()

    logger.info("Running ZipService in standalone mode")
    logger.info("Settings: %s", settings)

    service = ZipService(
        unzip_dir=settings.unzip_dir,
        scan_dir=settings.scan_dir,
    )

    try:
        service.run()
        for path in settings.scan_dir.iterdir():
            logger.info("Extracted: %s", path)
        sys.exit(0)
    except Exception as error:
        logger.error("ZipService failed: %s", error)
        sys.exit(1)
