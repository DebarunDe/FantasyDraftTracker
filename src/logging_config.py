import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the Fantasy Draft Simulator."""
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "draft_simulator.log"

    # Root logger
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return  # Already configured

    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # File handler with rotation (5MB max, keep 3 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger(__name__).info("Logging initialized (level=%s)", log_level)
