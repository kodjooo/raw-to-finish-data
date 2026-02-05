import logging
import os
from pathlib import Path
from time import time

from app.core import logging as logging_utils


def test_setup_logging_writes_to_file(tmp_path: Path) -> None:
    log_path = tmp_path / "processor.log"
    logging_utils.setup_logging(logging.INFO, log_file_path=log_path)
    logger = logging_utils.get_logger("test")
    logger.info("hello", event="file-test")
    logging.shutdown()

    content = log_path.read_text(encoding="utf-8")
    assert "file-test" in content


def test_setup_logging_cleans_old_logs(tmp_path: Path) -> None:
    old_log = tmp_path / "processor.log.2024-01-01"
    new_log = tmp_path / "processor.log.2026-02-05"
    old_log.write_text("old", encoding="utf-8")
    new_log.write_text("new", encoding="utf-8")
    old_mtime = time() - 60 * 60 * 24 * 8
    os.utime(old_log, (old_mtime, old_mtime))

    log_path = tmp_path / "processor.log"
    logging_utils.setup_logging(logging.INFO, log_file_path=log_path)

    assert not old_log.exists()
    assert new_log.exists()
