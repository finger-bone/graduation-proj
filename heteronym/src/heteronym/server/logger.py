import loguru

logger = loguru.logger
logger.add("debug.log", level="DEBUG")
