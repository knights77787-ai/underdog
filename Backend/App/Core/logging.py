"""공통 로거 설정. 관측 디버깅용."""
import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """루트 로거 설정. main 시작 시 1회 호출."""
    level_value = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=level_value,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_logger(name: str) -> logging.Logger:
    """이름 붙인 로거 반환 (예: ws.endpoint, ws.persist)."""
    return logging.getLogger(name)
