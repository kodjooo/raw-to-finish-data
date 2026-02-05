import logging
from pathlib import Path

from app.core import logging as logging_utils


def test_setup_logging_writes_to_file(tmp_path: Path) -> None:
    log_path = tmp_path / "processor.log"
    logging_utils.setup_logging(logging.INFO, log_file_path=log_path)
    logger = logging_utils.get_logger("test")
    logger.info("hello", event="file-test")
    logging.shutdown()

    content = log_path.read_text(encoding="utf-8")
    assert "file-test" in content
