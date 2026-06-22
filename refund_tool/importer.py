"""数据导入模块"""

import os
import json
import pandas as pd
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from .models import (
    Order, ConsumptionRecord, RefundApplication,
    OrderStatus, RefundStatus,
)
from .utils import parse_date, parse_float, parse_int, get_month_range


class DataImporter:
    def __init__(self, input_dir: str = "./data/input"):
        self.input_dir = input_dir
        self.orders: Dict[str, Order] = {}
        self.consumption_records: List[ConsumptionRecord] = []
        self.refund_applications: Dict[str, RefundApplication] = {}
        self.store_list: List[str] = []
        self.import_stats: Dict[str, int] = {}
        self.filtered_month: Optional[str] = None

    def import_all(self, store_ids: Optional[List[str]] = None,
                   month: Optional[str] = None) -> Tuple[int, int, int]:
        self.filtered_month = month
        order_count = self.import_orders(store_ids, month)
        record_count = self.import_consumption_records(store_ids, month)
        refund_count = self.import_refund_applications(store_ids, month)
        return order_count, record_count, refund_count

    def import_orders(self, store_ids: Optional[List[str]] = None,
                      month: Optional[str] = None) -> int:
        files = self._find_files("订单")
        count = 0
        for f in files:
            try:
                df = pd.read_excel(f) if f.endswith(('.xlsx', '.xls')) else pd.read_csv(f)
                for _, row in df.iterrows():
                    order = self._parse_order(row)
                    if order and self._filter_store(order.store_id, store_ids) \
                            and self._filter_month(order.purchased_at, month):
                        if order.order_id not in self.orders:
                            self.orders[order.order_id] = order
                            count += 1
                            if order.store_id not in self.store_list:
                                self.store_list.append(order.store_id)
            except Exception as e:
                print(f"导入订单文件失败: {f}, 错误: {e}")
        self.import_stats['orders'] = count
        return count

    def import_consumption_records(self, store_ids: Optional[List[str]] = None,
                                   month: Optional[str] = None) -> int:
        files = self._find_files("消费|划扣|记录")
        count = 0
        for f in files:
            try:
                df = pd.read_excel(f) if f.endswith(('.xlsx', '.xls')) else pd.read_csv(f)
                for _, row in df.iterrows():
                    record = self._parse_consumption_record(row)
                    if record and self._filter_store(record.store_id, store_ids) \
                            and self._filter_month(record.consumed_at, month):
                        self.consumption_records.append(record)
                        count += 1
                        if record.store_id not in self.store_list:
                            self.store_list.append(record.store_id)
            except Exception as e:
                print(f"导入消费记录失败: {f}, 错误: {e}")
        self.import_stats['consumption_records'] = count
        return count

    def import_refund_applications(self, store_ids: Optional[List[str]] = None,
                                   month: Optional[str] = None) -> int:
        files = self._find_files("退款|退项")
        count = 0
        for f in files:
            try:
                df = pd.read_excel(f) if f.endswith(('.xlsx', '.xls')) else pd.read_csv(f)
                for _, row in df.iterrows():
                    refund = self._parse_refund_application(row)
                    if refund and self._filter_store(refund.store_id, store_ids) \
                            and self._filter_month(refund.applied_at, month):
                        if refund.refund_id not in self.refund_applications:
                            self.refund_applications[refund.refund_id] = refund
                            count += 1
                            if refund.store_id not in self.store_list:
                                self.store_list.append(refund.store_id)
            except Exception as e:
                print(f"导入退款申请失败: {f}, 错误: {e}")
        self.import_stats['refund_applications'] = count
        return count

    def _find_files(self, pattern: str) -> List[str]:
        import re
        results = []
        if not os.path.exists(self.input_dir):
            return results
        for root, _, files in os.walk(self.input_dir):
            for file in files:
                if file.startswith('~$'):
                    continue
                if re.search(pattern, file, re.IGNORECASE) and file.endswith(('.xlsx', '.xls', '.csv')):
                    results.append(os.path.join(root, file))
        return sorted(results)

    def _filter_store(self, store_id: str, store_ids: Optional[List[str]]) -> bool:
        if not store_ids or 'all' in store_ids:
            return True
        return store_id in store_ids

    def _filter_month(self, date_obj: datetime, month_str: Optional[str]) -> bool:
        if not month_str or month_str in ['all', '全部', '']:
            return True
        try:
            parts = month_str.split('-')
            if len(parts) == 2:
                year, month = int(parts[0]), int(parts[1])
                start, end = get_month_range(year, month)
                return start <= date_obj <= end
        except (ValueError, IndexError):
            pass
        return True

    def _parse_is_package(self, raw_value) -> bool:
        if raw_value is None:
            return False
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, (int, float)):
            return int(raw_value) == 1
        s = str(raw_value).strip().lower()
        true_values = {'1', '是', 'true', 'yes', 'y', '套餐', '是套餐', 'true', 't'}
        false_values = {'0', '否', 'false', 'no', 'n', '普通', '不是', '不是套餐', 'f', '', 'nan', 'none', 'null'}
        if s in true_values:
            return True
        if s in false_values:
            return False
        return False

    def _parse_order(self, row: pd.Series) -> Optional[Order]:
        try:
            order_id = self._get_value(row, ['订单号', '订单ID', 'order_id', 'id'])
            if not order_id or str(order_id).strip() == '':
                return None
            order_id = str(order_id).strip()

            is_package = self._parse_is_package(self._get_value(row, ['是否套餐', 'is_package', '套餐标志']))
            package_items_raw = self._get_value(row, [
                '套餐明细', '套餐项目', 'package_items', '套餐内容', '包含项目'
            ])
            gifts_raw = self._get_value(row, [
                '赠品信息', '赠品', 'gifts', '赠送项目', '赠品明细'
            ])

            package_items = self._parse_items_json(package_items_raw, 'package')
            gifts = self._parse_items_json(gifts_raw, 'gift')

            if not is_package and (len(package_items) > 0 or len(gifts) > 0):
                is_package = True

            order = Order(
                order_id=order_id,
                store_id=str(self._get_value(row, ['门店ID', '门店编号', 'store_id']) or 'S001'),
                store_name=str(self._get_value(row, ['门店名称', '门店', 'store_name']) or '未知门店'),
                customer_id=str(self._get_value(row, ['客户ID', '客户编号', 'customer_id']) or ''),
                customer_name=str(self._get_value(row, ['客户姓名', '客户', 'customer_name']) or ''),
                item_id=str(self._get_value(row, ['项目ID', '项目编号', 'item_id']) or ''),
                item_name=str(self._get_value(row, ['项目名称', '项目', 'item_name']) or ''),
                item_type=str(self._get_value(row, ['项目类型', '类型', 'item_type']) or '单次'),
                original_price=parse_float(self._get_value(row, ['原价', 'original_price', '标价'])),
                discount_rate=parse_float(self._get_value(row, ['折扣率', '折扣', 'discount_rate'])) or 1.0,
                actual_price=parse_float(self._get_value(row, ['实付单价', '实付', 'actual_price', '成交价'])),
                purchase_quantity=parse_int(self._get_value(row, ['购买数量', '数量', 'quantity', 'purchase_quantity'])),
                purchased_at=parse_date(str(self._get_value(row, ['购买日期', '下单时间', 'purchased_at', '订单日期']))) or datetime.now(),
                consultant_id=str(self._get_value(row, ['咨询师ID', '咨询师编号', 'consultant_id']) or ''),
                consultant_name=str(self._get_value(row, ['咨询师姓名', '咨询师', 'consultant_name']) or ''),
                is_package=is_package,
                package_items=package_items,
                gifts=gifts,
                status=OrderStatus.NORMAL,
                remarks=str(self._get_value(row, ['备注', 'remarks', '说明']) or ''),
            )

            if order.actual_price == 0 and order.original_price > 0:
                order.actual_price = round(order.original_price * order.discount_rate, 2)

            return order
        except Exception as e:
            print(f"解析订单行失败: {e}")
            return None

    def _parse_items_json(self, raw_value, item_type: str) -> List[Dict]:
        items = []
        if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
            return items
        raw_str = str(raw_value).strip()
        if not raw_str or raw_str in ['nan', 'NaN', 'None', '']:
            return items

        try:
            parsed = json.loads(raw_str)
            if isinstance(parsed, list):
                for it in parsed:
                    if isinstance(it, dict):
                        items.append({
                            'id': str(it.get('id', it.get('item_id', ''))),
                            'name': str(it.get('name', it.get('item_name', ''))),
                            'price': parse_float(it.get('price', it.get('amount', 0))),
                            'quantity': parse_float(it.get('quantity', it.get('qty', 1))),
                        })
            return items
        except (json.JSONDecodeError, TypeError):
            pass

        try:
            parts = raw_str.split(';')
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                sub_parts = [p.strip() for p in part.split('|')]
                name = sub_parts[0] if len(sub_parts) > 0 else ''
                price = parse_float(sub_parts[1]) if len(sub_parts) > 1 else 0.0
                qty = parse_float(sub_parts[2]) if len(sub_parts) > 2 else 1
                if name:
                    items.append({
                        'id': '',
                        'name': name,
                        'price': price,
                        'quantity': qty,
                    })
            return items
        except Exception:
            pass

        return items

    def _parse_consumption_record(self, row: pd.Series) -> Optional[ConsumptionRecord]:
        try:
            record_id = self._get_value(row, ['记录ID', '记录编号', 'record_id', 'id', '消费单号'])
            if not record_id or str(record_id).strip() == '':
                return None
            record_id = str(record_id).strip()

            record = ConsumptionRecord(
                record_id=record_id,
                order_id=str(self._get_value(row, ['订单号', '订单ID', 'order_id']) or ''),
                store_id=str(self._get_value(row, ['门店ID', '门店编号', 'store_id']) or 'S001'),
                store_name=str(self._get_value(row, ['门店名称', '门店', 'store_name']) or '未知门店'),
                customer_id=str(self._get_value(row, ['客户ID', '客户编号', 'customer_id']) or ''),
                customer_name=str(self._get_value(row, ['客户姓名', '客户', 'customer_name']) or ''),
                item_id=str(self._get_value(row, ['项目ID', '项目编号', 'item_id']) or ''),
                item_name=str(self._get_value(row, ['项目名称', '项目', 'item_name']) or ''),
                consume_quantity=parse_float(self._get_value(row, ['消费数量', '数量', 'consume_quantity'])),
                consume_amount=parse_float(self._get_value(row, ['消费金额', '金额', 'consume_amount'])),
                consumed_at=parse_date(str(self._get_value(row, ['消费日期', '消费时间', 'consumed_at', '划扣时间']))) or datetime.now(),
                doctor_id=str(self._get_value(row, ['医生ID', '医生编号', 'doctor_id']) or ''),
                doctor_name=str(self._get_value(row, ['医生姓名', '医生', 'doctor_name', '操作医生']) or ''),
                consultant_id=str(self._get_value(row, ['咨询师ID', '咨询师编号', 'consultant_id']) or ''),
                consultant_name=str(self._get_value(row, ['咨询师姓名', '咨询师', 'consultant_name']) or ''),
                doctor_commission=parse_float(self._get_value(row, ['医生提成', 'doctor_commission'])),
                consultant_commission=parse_float(self._get_value(row, ['咨询师提成', 'consultant_commission'])),
                remarks=str(self._get_value(row, ['备注', 'remarks', '说明']) or ''),
            )
            return record
        except Exception as e:
            print(f"解析消费记录失败: {e}")
            return None

    def _parse_refund_application(self, row: pd.Series) -> Optional[RefundApplication]:
        try:
            refund_id = self._get_value(row, ['退款单号', '退款ID', 'refund_id', 'id'])
            if not refund_id or str(refund_id).strip() == '':
                return None
            refund_id = str(refund_id).strip()

            status_str = str(self._get_value(row, ['状态', 'status', '审核状态']) or 'pending').lower()
            status_map = {
                'pending': RefundStatus.PENDING,
                '待处理': RefundStatus.PENDING,
                '待审核': RefundStatus.PENDING,
                'approved': RefundStatus.APPROVED,
                '已通过': RefundStatus.APPROVED,
                '已同意': RefundStatus.APPROVED,
                'rejected': RefundStatus.REJECTED,
                '已拒绝': RefundStatus.REJECTED,
                '已驳回': RefundStatus.REJECTED,
                'processed': RefundStatus.PROCESSED,
                '已处理': RefundStatus.PROCESSED,
                '已完成': RefundStatus.PROCESSED,
                'exception': RefundStatus.EXCEPTION,
                '异常': RefundStatus.EXCEPTION,
            }
            status = status_map.get(status_str, RefundStatus.PENDING)

            refund = RefundApplication(
                refund_id=refund_id,
                order_id=str(self._get_value(row, ['订单号', '订单ID', 'order_id']) or ''),
                store_id=str(self._get_value(row, ['门店ID', '门店编号', 'store_id']) or 'S001'),
                store_name=str(self._get_value(row, ['门店名称', '门店', 'store_name']) or '未知门店'),
                customer_id=str(self._get_value(row, ['客户ID', '客户编号', 'customer_id']) or ''),
                customer_name=str(self._get_value(row, ['客户姓名', '客户', 'customer_name']) or ''),
                item_id=str(self._get_value(row, ['项目ID', '项目编号', 'item_id']) or ''),
                item_name=str(self._get_value(row, ['项目名称', '项目', 'item_name']) or ''),
                refund_quantity=parse_float(self._get_value(row, ['退款数量', '退项数量', 'refund_quantity'])),
                refund_amount=parse_float(self._get_value(row, ['退款金额', '退项金额', 'refund_amount', '申请金额'])),
                apply_reason=str(self._get_value(row, ['退款原因', '申请原因', 'apply_reason', '原因']) or ''),
                applied_at=parse_date(str(self._get_value(row, ['申请日期', '申请时间', 'applied_at'])) or datetime.now()),
                applicant=str(self._get_value(row, ['申请人', 'applicant', '经办人']) or ''),
                status=status,
                handler_opinion=str(self._get_value(row, ['处理意见', '审核意见', 'handler_opinion']) or ''),
            )
            return refund
        except Exception as e:
            print(f"解析退款申请失败: {e}")
            return None

    def _get_value(self, row: pd.Series, possible_names: List[str]):
        for name in possible_names:
            if name in row.index:
                val = row[name]
                if pd.notna(val):
                    return val
            lower_name = name.lower()
            for col in row.index:
                if col.lower() == lower_name and pd.notna(row[col]):
                    return row[col]
        return None

    def get_order_by_id(self, order_id: str) -> Optional[Order]:
        return self.orders.get(order_id)

    def get_consumptions_by_order(self, order_id: str) -> List[ConsumptionRecord]:
        return [r for r in self.consumption_records if r.order_id == order_id]

    def get_refund_by_id(self, refund_id: str) -> Optional[RefundApplication]:
        return self.refund_applications.get(refund_id)

    def get_summary(self) -> Dict[str, int]:
        summary = {
            "订单数": len(self.orders),
            "消费记录数": len(self.consumption_records),
            "退款申请数": len(self.refund_applications),
            "门店数": len(self.store_list),
        }
        if self.filtered_month:
            summary["核算月份"] = self.filtered_month
        return summary
