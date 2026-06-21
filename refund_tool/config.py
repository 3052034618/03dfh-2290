"""配置管理模块"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._load_config()
        self._ensure_directories()

    def _load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        else:
            self.config = self._default_config()
            self.save()

    def _default_config(self) -> Dict[str, Any]:
        return {
            "default_store": "all",
            "default_month": "current",
            "input_dir": "./data/input",
            "output_dir": "./data/output",
            "log_dir": "./data/logs",
            "validation_rules": {
                "allow_consume_exceed_purchase": False,
                "allow_refund_exceed_remaining": False,
                "min_refund_amount": 0,
                "max_refund_ratio": 1.0,
                "check_package_split": True,
                "check_doctor_commission": True,
                "check_consultant_commission": True,
                "check_gift_deduction": True,
            },
            "commission_rules": {
                "doctor_commission_rate": 0.15,
                "consultant_commission_rate": 0.1,
                "package_split_method": "average",
            },
            "voucher": {
                "prefix": "TK",
                "digit_length": 6,
                "start_number": 1,
            },
        }

    def _ensure_directories(self):
        dirs = [
            self.config.get("input_dir", "./data/input"),
            self.config.get("output_dir", "./data/output"),
            self.config.get("log_dir", "./data/logs"),
        ]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        keys = key.split(".")
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def save(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)

    def get_input_dir(self) -> str:
        return self.config.get("input_dir", "./data/input")

    def get_output_dir(self) -> str:
        return self.config.get("output_dir", "./data/output")

    def get_log_dir(self) -> str:
        return self.config.get("log_dir", "./data/logs")
