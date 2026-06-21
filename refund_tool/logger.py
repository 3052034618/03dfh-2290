"""日志管理模块"""

import os
import logging
from datetime import datetime
from pathlib import Path


class LogManager:
    def __init__(self, log_dir: str = "./data/logs"):
        self.log_dir = log_dir
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        self.loggers = {}

    def get_logger(self, name: str = "refund_tool") -> logging.Logger:
        if name in self.loggers:
            return self.loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if not logger.handlers:
            log_file = os.path.join(self.log_dir, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(logging.INFO)

            ch = logging.StreamHandler()
            ch.setLevel(logging.WARNING)

            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)

            logger.addHandler(fh)
            logger.addHandler(ch)

        self.loggers[name] = logger
        return logger

    def log_operation(self, operation: str, details: str = ""):
        logger = self.get_logger("operations")
        logger.info(f"[{operation}] {details}")

    def log_validation(self, item_id: str, rule: str, result: str, details: str = ""):
        logger = self.get_logger("validation")
        logger.info(f"[{item_id}] [{rule}] {result} - {details}")

    def log_refund(self, refund_id: str, status: str, amount: float = 0):
        logger = self.get_logger("refund")
        logger.info(f"[{refund_id}] {status} - 金额: ¥{amount:.2f}")

    def get_log_files(self) -> list:
        logs = []
        if os.path.exists(self.log_dir):
            for f in sorted(os.listdir(self.log_dir), reverse=True):
                if f.endswith(".log"):
                    fpath = os.path.join(self.log_dir, f)
                    size = os.path.getsize(fpath)
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    logs.append({
                        "filename": f,
                        "path": fpath,
                        "size": size,
                        "modified": mtime,
                    })
        return logs

    def read_log(self, filename: str, lines: int = 100) -> list:
        fpath = os.path.join(self.log_dir, filename)
        if not os.path.exists(fpath):
            return []
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.readlines()
        return content[-lines:] if len(content) > lines else content
