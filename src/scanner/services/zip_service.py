import logging
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

    def unzip(self, zip_path: Path, destination: Path) -> None:
        """Extract zip_path into the destination directory."""
        logger.info("Attempting extraction of %s to %s", zip_path, destination)
        try:
            with ZipFile(zip_path, "r") as archive:
                file_list = archive.namelist()
                logger.debug(
                    "Zip contains %d files/directories",
                    len(file_list),
                )

                archive.extractall(destination)
                logger.info("Extraction completed successfully")

                dirs = [n for n in file_list if n.endswith("/")]
                if dirs:
                    logger.info(
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
