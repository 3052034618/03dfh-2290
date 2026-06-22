"""会话状态管理 - 支持分步命令间的数据衔接"""

import os
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib


class SessionManager:
    def __init__(self, state_dir: str = "./data/state"):
        self.state_dir = state_dir
        Path(self.state_dir).mkdir(parents=True, exist_ok=True)
        self.state_file = os.path.join(self.state_dir, "session_state.pkl")
        self.meta_file = os.path.join(self.state_dir, "session_meta.json")
        self.state: Dict[str, Any] = {}
        self.meta: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "rb") as f:
                    self.state = pickle.load(f)
            except Exception:
                self.state = {}

        if os.path.exists(self.meta_file):
            try:
                with open(self.meta_file, "r", encoding="utf-8") as f:
                    self.meta = json.load(f)
            except Exception:
                self.meta = {}

    def _save(self):
        try:
            with open(self.state_file, "wb") as f:
                pickle.dump(self.state, f, protocol=pickle.HIGHEST_PROTOCOL)
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(self.meta, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存会话状态失败: {e}")

    def set(self, key: str, value: Any):
        self.state[key] = value
        self.meta[f"{key}_saved_at"] = datetime.now().isoformat()
        self._save()

    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def has(self, key: str) -> bool:
        return key in self.state

    def clear_key(self, key: str):
        if key in self.state:
            del self.state[key]
        if f"{key}_saved_at" in self.meta:
            del self.meta[f"{key}_saved_at"]
        self._save()

    def clear_all(self):
        self.state = {}
        self.meta = {
            "cleared_at": datetime.now().isoformat(),
        }
        self._save()

    def set_params(self, store_ids=None, month=None):
        params = {
            "store_ids": store_ids,
            "month": month,
            "updated_at": datetime.now().isoformat(),
        }
        self.meta["params"] = params
        self._save()

    def get_params(self) -> Dict[str, Any]:
        return self.meta.get("params", {})

    def get_status(self) -> Dict[str, Any]:
        status = {
            "has_importer": self.has("importer"),
            "has_validator": self.has("validator"),
            "has_exceptions": self.has("exceptions"),
            "has_trial_results": self.has("trial_results"),
            "has_processor": self.has("processor"),
            "is_confirmed": self.state.get("confirmed", False),
            "params": self.get_params(),
            "unhandled_exceptions": self.count_unhandled_exceptions(),
        }
        return status

    def count_unhandled_exceptions(self) -> int:
        exceptions = self.get("exceptions", [])
        if not exceptions:
            return 0
        return len([e for e in exceptions if not e.get("handled", False)])

    def has_unhandled_exceptions(self) -> bool:
        return self.count_unhandled_exceptions() > 0

    def get_data_signature(self, data: Any) -> str:
        raw = str(data) if not isinstance(data, (bytes, bytearray)) else data
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        return hashlib.md5(raw).hexdigest()

    def print_status(self):
        status = self.get_status()
        print("\n===== 当前会话状态 =====")
        params = status.get("params", {})
        if params:
            if params.get("store_ids"):
                print(f"门店范围: {', '.join(params['store_ids'])}")
            else:
                print("门店范围: 全部")
            print(f"核算月份: {params.get('month') or '未指定(全部)'}")
        print(f"数据已导入: {'[OK]' if status['has_importer'] else '[--]'}")
        print(f"规则已校验: {'[OK]' if status['has_validator'] else '[--]'}")
        print(f"发现异常数: {len(self.get('exceptions', []))}")
        print(f"待处理异常: {status['unhandled_exceptions']}")
        print(f"试算已完成: {'[OK]' if status['has_trial_results'] else '[--]'}")
        print(f"结果已确认: {'[OK]' if status['is_confirmed'] else '[--]'}")
        print("======================\n")
