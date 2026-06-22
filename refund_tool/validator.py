"""规则校验引擎"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime

from .models import (
    Order, ConsumptionRecord, RefundApplication,
    ExceptionType, RefundStatus, RefundResult,
)
from .utils import parse_float


class ValidationEngine:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.rules = self.config.get("validation_rules", {})
        self.commission_rules = self.config.get("commission_rules", {})
        self.exceptions: List[Dict] = []
        self.validation_results: Dict[str, List[Dict]] = {}

    def validate_all(self, orders: Dict[str, Order],
                     consumption_records: List[ConsumptionRecord],
                     refund_applications: Dict[str, RefundApplication]) -> List[Dict]:
        self.exceptions = []

        for order_id, order in orders.items():
            self._validate_order(order, consumption_records, refund_applications)

        for refund_id, refund in refund_applications.items():
            order = orders.get(refund.order_id)
            if order:
                self._validate_refund(refund, order, consumption_records)
            else:
                self._add_exception(
                    refund.refund_id,
                    ExceptionType.RECORD_NOT_FOUND,
                    f"退款申请关联的订单不存在: {refund.order_id}",
                    refund.store_id,
                    {"refund_id": refund.refund_id, "missing_order_id": refund.order_id}
                )
                refund.is_exception = True
                refund.status = RefundStatus.EXCEPTION

        return self.exceptions

    def _validate_order(self, order: Order,
                        consumption_records: List[ConsumptionRecord],
                        refund_applications: Dict[str, RefundApplication]):
        order_consumptions = [r for r in consumption_records if r.order_id == order.order_id]

        total_consumed = sum(r.consume_quantity for r in order_consumptions)
        total_consume_amount = sum(r.consume_amount for r in order_consumptions)

        if not self.rules.get("allow_consume_exceed_purchase", False):
            if total_consumed > order.purchase_quantity + 1e-6:
                self._add_exception(
                    order.order_id,
                    ExceptionType.CONSUME_EXCEED_PURCHASE,
                    f"已消费次数({total_consumed:.2f})大于购买次数({order.purchase_quantity})",
                    order.store_id,
                    {"order_id": order.order_id, "item_name": order.item_name,
                     "purchased": order.purchase_quantity, "consumed": total_consumed,
                     "exceed_count": round(total_consumed - order.purchase_quantity, 2)}
                )

        if self.rules.get("check_doctor_commission", True):
            self._check_doctor_commission(order, order_consumptions)

        if self.rules.get("check_consultant_commission", True):
            self._check_consultant_commission(order, order_consumptions)

        expected_consume_amount = total_consumed * order.actual_price
        if abs(total_consume_amount - expected_consume_amount) > 0.01:
            self._add_exception(
                order.order_id,
                ExceptionType.PRICE_MISMATCH,
                f"消费金额合计({total_consume_amount:.2f})与预期({expected_consume_amount:.2f})不符",
                order.store_id,
                {"order_id": order.order_id, "item_name": order.item_name,
                 "actual": total_consume_amount, "expected": expected_consume_amount,
                 "diff": round(total_consume_amount - expected_consume_amount, 2)}
            )

        expected_price = order.original_price * order.discount_rate
        if abs(order.actual_price - expected_price) > 0.01 and order.discount_rate > 0:
            self._add_exception(
                order.order_id,
                ExceptionType.DISCOUNT_MISMATCH,
                f"实付单价({order.actual_price:.2f})与原价*折扣({expected_price:.2f})不符",
                order.store_id,
                {"order_id": order.order_id, "item_name": order.item_name,
                 "original_price": order.original_price,
                 "discount_rate": order.discount_rate,
                 "actual_price": order.actual_price,
                 "expected_price": expected_price,
                 "diff": round(order.actual_price - expected_price, 2)}
            )

        if self.rules.get("check_package_split", True) and order.is_package:
            self._check_package_order(order)

        if self.rules.get("check_gift_deduction", True) and order.gifts:
            self._check_gift_validity(order)

    def _check_package_order(self, order: Order):
        if not order.package_items or len(order.package_items) == 0:
            self._add_exception(
                order.order_id,
                ExceptionType.PACKAGE_SPLIT_ERROR,
                f"订单标记为套餐但缺少套餐明细",
                order.store_id,
                {"order_id": order.order_id, "item_name": order.item_name}
            )
            return

        total_package_price = 0.0
        for pkg_item in order.package_items:
            item_price = float(pkg_item.get("price", 0))
            item_qty = float(pkg_item.get("quantity", 1))
            total_package_price += item_price * item_qty

        expected_total = order.actual_price * order.purchase_quantity
        if abs(total_package_price - expected_total) > 0.01:
            self._add_exception(
                order.order_id,
                ExceptionType.PACKAGE_SPLIT_ERROR,
                f"套餐明细合计金额({total_package_price:.2f})与套餐总价({expected_total:.2f})不符",
                order.store_id,
                {"order_id": order.order_id, "item_name": order.item_name,
                 "package_items_total": total_package_price,
                 "expected_total": expected_total,
                 "diff": round(total_package_price - expected_total, 2),
                 "package_item_count": len(order.package_items)}
            )

        method = self.commission_rules.get("package_split_method", "average")
        if method == "average" and len(order.package_items) > 1:
            prices = [float(pi.get("price", 0)) for pi in order.package_items]
            avg_price = sum(prices) / len(prices)
            max_price = max(prices)
            if max_price > 0 and (max_price - min(prices)) / max_price > 0.3:
                self._add_exception(
                    order.order_id,
                    ExceptionType.PACKAGE_SPLIT_ERROR,
                    f"套餐项目价格差异过大，均价分摊不合理",
                    order.store_id,
                    {"order_id": order.order_id, "item_name": order.item_name,
                     "average_price": round(avg_price, 2),
                     "max_price": max_price,
                     "min_price": min(prices),
                     "diff_ratio": round((max_price - min(prices)) / max_price, 2)}
                )

    def _check_gift_validity(self, order: Order):
        total_order_value = order.actual_price * order.purchase_quantity
        total_gift_value = 0.0
        for gift in order.gifts:
            gift_price = float(gift.get("price", 0))
            gift_qty = float(gift.get("quantity", 1))
            gift_name = gift.get("name", "")
            total_gift_value += gift_price * gift_qty

            if gift_price < 0:
                self._add_exception(
                    order.order_id,
                    ExceptionType.GIFT_DEDUCTION_ERROR,
                    f"赠品[{gift_name}]价格为负数",
                    order.store_id,
                    {"order_id": order.order_id, "item_name": order.item_name,
                     "gift_name": gift_name, "gift_price": gift_price}
                )

            if gift_qty <= 0:
                self._add_exception(
                    order.order_id,
                    ExceptionType.GIFT_DEDUCTION_ERROR,
                    f"赠品[{gift_name}]数量不合法({gift_qty})",
                    order.store_id,
                    {"order_id": order.order_id, "item_name": order.item_name,
                     "gift_name": gift_name, "gift_qty": gift_qty}
                )

        if total_gift_value > 0 and total_order_value > 0:
            gift_ratio = total_gift_value / total_order_value
            if gift_ratio > 0.5:
                self._add_exception(
                    order.order_id,
                    ExceptionType.GIFT_DEDUCTION_ERROR,
                    f"赠品总价值({total_gift_value:.2f})占订单金额({total_order_value:.2f})的{gift_ratio*100:.1f}%，比例异常",
                    order.store_id,
                    {"order_id": order.order_id, "item_name": order.item_name,
                     "total_gift_value": total_gift_value,
                     "total_order_value": total_order_value,
                     "gift_ratio": round(gift_ratio, 2)}
                )

    def _validate_refund(self, refund: RefundApplication, order: Order,
                         consumption_records: List[ConsumptionRecord]):
        order_consumptions = [r for r in consumption_records if r.order_id == order.order_id]
        total_consumed = sum(r.consume_quantity for r in order_consumptions)

        remaining_quantity = order.purchase_quantity - total_consumed
        remaining_amount = remaining_quantity * order.actual_price

        if not self.rules.get("allow_consume_exceed_purchase", False):
            if total_consumed > order.purchase_quantity + 1e-6:
                self._add_exception(
                    refund.refund_id,
                    ExceptionType.CONSUME_EXCEED_PURCHASE,
                    f"关联订单存在超消费: 已消费{total_consumed:.2f} > 购买{order.purchase_quantity}",
                    refund.store_id,
                    {"refund_id": refund.refund_id, "order_id": order.order_id,
                     "item_name": order.item_name,
                     "purchased": order.purchase_quantity,
                     "consumed": total_consumed,
                     "exceed": round(total_consumed - order.purchase_quantity, 2)}
                )
                refund.is_exception = True
                refund.status = RefundStatus.EXCEPTION

        if not self.rules.get("allow_refund_exceed_remaining", False):
            if refund.refund_quantity > remaining_quantity + 1e-6:
                self._add_exception(
                    refund.refund_id,
                    ExceptionType.REFUND_EXCEED_REMAINING,
                    f"退款数量({refund.refund_quantity:.2f})超过剩余数量({remaining_quantity:.2f})",
                    refund.store_id,
                    {"refund_id": refund.refund_id, "order_id": order.order_id,
                     "item_name": refund.item_name,
                     "refund_quantity": refund.refund_quantity,
                     "remaining_quantity": remaining_quantity,
                     "remaining_amount": remaining_amount,
                     "exceed_qty": round(refund.refund_quantity - remaining_quantity, 2)}
                )
                refund.is_exception = True
                refund.status = RefundStatus.EXCEPTION

            expected_refund_amount = refund.refund_quantity * order.actual_price
            if refund.refund_amount > expected_refund_amount + 0.01:
                self._add_exception(
                    refund.refund_id,
                    ExceptionType.REFUND_EXCEED_REMAINING,
                    f"退款金额({refund.refund_amount:.2f})超过剩余价值({expected_refund_amount:.2f})",
                    refund.store_id,
                    {"refund_id": refund.refund_id, "order_id": order.order_id,
                     "item_name": refund.item_name,
                     "refund_amount": refund.refund_amount,
                     "expected_amount": expected_refund_amount,
                     "exceed_amt": round(refund.refund_amount - expected_refund_amount, 2)}
                )
                refund.is_exception = True
                refund.status = RefundStatus.EXCEPTION

        if self.rules.get("check_package_split", True) and order.is_package:
            self._check_package_refund(refund, order)

        if self.rules.get("check_gift_deduction", True) and order.gifts:
            self._check_gift_refund(refund, order)

    def _check_package_refund(self, refund: RefundApplication, order: Order):
        if not order.package_items or len(order.package_items) == 0:
            return

        method = self.commission_rules.get("package_split_method", "average")
        refund_ratio = refund.refund_quantity / order.purchase_quantity if order.purchase_quantity > 0 else 0

        if method == "average":
            item_count = len(order.package_items)
            if item_count > 0:
                per_item_refund = refund.refund_amount / item_count if item_count > 0 else 0
                for idx, pkg_item in enumerate(order.package_items):
                    pkg_price = float(pkg_item.get("price", 0))
                    pkg_qty = float(pkg_item.get("quantity", 1))
                    expected_refund_for_item = pkg_price * pkg_qty * refund_ratio
                    if abs(per_item_refund - expected_refund_for_item) > 0.01 and pkg_price > 0:
                        self._add_exception(
                            refund.refund_id,
                            ExceptionType.PACKAGE_SPLIT_ERROR,
                            f"套餐项目[{pkg_item.get('name', f'第{idx+1}项')}]退款分摊不符，平均分摊({per_item_refund:.2f})与按比例分摊({expected_refund_for_item:.2f})不一致",
                            refund.store_id,
                            {"refund_id": refund.refund_id,
                             "order_id": order.order_id,
                             "package_item": pkg_item.get("name", f"第{idx+1}项"),
                             "item_price": pkg_price,
                             "item_qty": pkg_qty,
                             "refund_ratio": round(refund_ratio, 4),
                             "average_split": round(per_item_refund, 2),
                             "proportional_split": round(expected_refund_for_item, 2)}
                        )
                        break

    def _check_gift_refund(self, refund: RefundApplication, order: Order):
        refund_ratio = refund.refund_quantity / order.purchase_quantity if order.purchase_quantity > 0 else 0
        if refund_ratio > 1:
            refund_ratio = 1.0

        total_gift_deduction = 0.0
        for gift in order.gifts:
            gift_price = float(gift.get("price", 0))
            gift_qty = float(gift.get("quantity", 1))
            gift_name = gift.get("name", "未命名赠品")
            expected_deduction = gift_price * gift_qty * refund_ratio
            total_gift_deduction += expected_deduction

        if total_gift_deduction > refund.refund_amount:
            self._add_exception(
                refund.refund_id,
                ExceptionType.GIFT_DEDUCTION_ERROR,
                f"赠品扣减额({total_gift_deduction:.2f})大于退款金额({refund.refund_amount:.2f})",
                refund.store_id,
                {"refund_id": refund.refund_id,
                 "order_id": order.order_id,
                 "item_name": refund.item_name,
                 "refund_amount": refund.refund_amount,
                 "gift_deduction": round(total_gift_deduction, 2),
                 "refund_ratio": round(refund_ratio, 4)}
            )

    def _check_doctor_commission(self, order: Order,
                                 consumptions: List[ConsumptionRecord]):
        rate = self.commission_rules.get("doctor_commission_rate", 0.15)
        for record in consumptions:
            if record.doctor_commission > 0:
                expected = record.consume_amount * rate
                if abs(record.doctor_commission - expected) > 0.01:
                    self._add_exception(
                        record.record_id,
                        ExceptionType.DOCTOR_COMMISSION_MISMATCH,
                        f"医生提成({record.doctor_commission:.2f})与预期({expected:.2f})不符，"
                        f"提成比例应为{rate*100:.1f}%",
                        record.store_id,
                        {"record_id": record.record_id,
                         "order_id": record.order_id,
                         "doctor_name": record.doctor_name,
                         "actual": record.doctor_commission,
                         "expected": round(expected, 2),
                         "diff": round(record.doctor_commission - expected, 2),
                         "consume_amount": record.consume_amount,
                         "commission_rate": rate}
                    )

    def _check_consultant_commission(self, order: Order,
                                     consumptions: List[ConsumptionRecord]):
        rate = self.commission_rules.get("consultant_commission_rate", 0.1)
        for record in consumptions:
            if record.consultant_commission > 0:
                expected = record.consume_amount * rate
                if abs(record.consultant_commission - expected) > 0.01:
                    self._add_exception(
                        record.record_id,
                        ExceptionType.CONSULTANT_COMMISSION_MISMATCH,
                        f"咨询师提成({record.consultant_commission:.2f})与预期({expected:.2f})不符，"
                        f"提成比例应为{rate*100:.1f}%",
                        record.store_id,
                        {"record_id": record.record_id,
                         "order_id": record.order_id,
                         "consultant_name": record.consultant_name,
                         "actual": record.consultant_commission,
                         "expected": round(expected, 2),
                         "diff": round(record.consultant_commission - expected, 2),
                         "consume_amount": record.consume_amount,
                         "commission_rate": rate}
                    )

    def _add_exception(self, related_id: str, exception_type: ExceptionType,
                       message: str, store_id: str = "",
                       details: Optional[Dict] = None):
        exception = {
            "exception_id": f"EXC_{len(self.exceptions)+1:04d}",
            "related_id": related_id,
            "type": exception_type.value,
            "type_name": self._get_exception_name(exception_type),
            "severity": self._get_exception_severity(exception_type),
            "message": message,
            "store_id": store_id,
            "details": details or {},
            "detected_at": datetime.now(),
            "handled": False,
            "handler_opinion": "",
            "handled_at": None,
            "handler": "",
        }
        self.exceptions.append(exception)

    def _get_exception_name(self, exception_type: ExceptionType) -> str:
        names = {
            ExceptionType.CONSUME_EXCEED_PURCHASE: "超消费次数",
            ExceptionType.REFUND_EXCEED_REMAINING: "退款超剩余价值",
            ExceptionType.PRICE_MISMATCH: "价格不匹配",
            ExceptionType.DISCOUNT_MISMATCH: "折扣不匹配",
            ExceptionType.PACKAGE_SPLIT_ERROR: "套餐拆分错误",
            ExceptionType.DOCTOR_COMMISSION_MISMATCH: "医生提成不匹配",
            ExceptionType.CONSULTANT_COMMISSION_MISMATCH: "咨询师提成不匹配",
            ExceptionType.GIFT_DEDUCTION_ERROR: "赠品扣减错误",
            ExceptionType.RECORD_NOT_FOUND: "记录未找到",
            ExceptionType.DUPLICATE_REFUND: "重复退款",
        }
        return names.get(exception_type, exception_type.value)

    def _get_exception_severity(self, exception_type: ExceptionType) -> str:
        high = [
            ExceptionType.CONSUME_EXCEED_PURCHASE,
            ExceptionType.REFUND_EXCEED_REMAINING,
            ExceptionType.RECORD_NOT_FOUND,
            ExceptionType.DUPLICATE_REFUND,
        ]
        medium = [
            ExceptionType.PACKAGE_SPLIT_ERROR,
            ExceptionType.GIFT_DEDUCTION_ERROR,
            ExceptionType.PRICE_MISMATCH,
        ]
        if exception_type in high:
            return "高"
        elif exception_type in medium:
            return "中"
        return "低"

    def get_exceptions_by_type(self, exception_type: ExceptionType) -> List[Dict]:
        return [e for e in self.exceptions if e["type"] == exception_type.value]

    def get_exceptions_by_store(self, store_id: str) -> List[Dict]:
        return [e for e in self.exceptions if e["store_id"] == store_id]

    def get_unhandled_exceptions(self) -> List[Dict]:
        return [e for e in self.exceptions if not e["handled"]]

    def has_unhandled_high_severity(self) -> bool:
        for e in self.exceptions:
            if not e["handled"] and e.get("severity") == "高":
                return True
        return False

    def get_exception_summary(self) -> Dict[str, Dict]:
        summary = {}
        for e in self.exceptions:
            t = e["type_name"]
            if t not in summary:
                summary[t] = {"总数": 0, "待处理": 0, "高": 0, "中": 0, "低": 0}
            summary[t]["总数"] += 1
            if not e["handled"]:
                summary[t]["待处理"] += 1
            sev = e.get("severity", "低")
            summary[t][sev] = summary[t].get(sev, 0) + 1
        return summary

    def calculate_refund_result(self, refund: RefundApplication, order: Order,
                                consumption_records: List[ConsumptionRecord]) -> RefundResult:
        order_consumptions = [r for r in consumption_records if r.order_id == order.order_id]
        total_consumed = sum(r.consume_quantity for r in order_consumptions)

        remaining_quantity = max(order.purchase_quantity - total_consumed, 0)
        remaining_amount = remaining_quantity * order.actual_price

        actual_refund_qty = min(refund.refund_quantity, remaining_quantity)
        if actual_refund_qty < 0:
            actual_refund_qty = 0
        original_refund_amt = actual_refund_qty * order.actual_price

        doc_rate = self.commission_rules.get("doctor_commission_rate", 0.15)
        cons_rate = self.commission_rules.get("consultant_commission_rate", 0.1)

        doc_deduction = round(original_refund_amt * doc_rate, 2)
        cons_deduction = round(original_refund_amt * cons_rate, 2)

        gift_deduction = 0.0
        gift_details = []
        if order.gifts and len(order.gifts) > 0:
            refund_ratio = actual_refund_qty / order.purchase_quantity if order.purchase_quantity > 0 else 0
            if refund_ratio > 1:
                refund_ratio = 1.0
            for gift in order.gifts:
                gift_price = float(gift.get("price", 0))
                gift_qty = float(gift.get("quantity", 1))
                gift_name = gift.get("name", "未命名赠品")
                deduction = round(gift_price * gift_qty * refund_ratio, 2)
                gift_deduction += deduction
                gift_details.append({
                    "name": gift_name,
                    "price": gift_price,
                    "quantity": gift_qty,
                    "refund_ratio": round(refund_ratio, 4),
                    "deduction": deduction,
                })

        total_deductions = doc_deduction + cons_deduction + gift_deduction
        net_refund = round(max(original_refund_amt - total_deductions, 0), 2)

        new_remaining_qty = max(remaining_quantity - actual_refund_qty, 0)
        new_remaining_amt = round(new_remaining_qty * order.actual_price, 2)

        remarks = refund.apply_reason
        if gift_deduction > 0:
            gift_desc = "; ".join([
                f"{g['name']}扣{g['deduction']:.2f}" for g in gift_details
            ])
            remarks = f"{remarks} [赠品扣减: {gift_desc}]" if remarks else f"[赠品扣减: {gift_desc}]"

        return RefundResult(
            refund_id=refund.refund_id,
            order_id=order.order_id,
            store_id=refund.store_id,
            store_name=refund.store_name,
            customer_id=order.customer_id,
            customer_name=order.customer_name,
            item_id=order.item_id,
            item_name=order.item_name,
            refund_quantity=actual_refund_qty,
            original_refund_amount=round(original_refund_amt, 2),
            final_refund_amount=round(original_refund_amt, 2),
            doctor_commission_deduction=doc_deduction,
            consultant_commission_deduction=cons_deduction,
            gift_deduction_amount=gift_deduction,
            net_refund_amount=net_refund,
            remaining_quantity=new_remaining_qty,
            remaining_amount=new_remaining_amt,
            processed_at=datetime.now(),
            remarks=remarks,
        )

    def batch_calculate(self, refund_applications: Dict[str, RefundApplication],
                        orders: Dict[str, Order],
                        consumption_records: List[ConsumptionRecord]) -> List[RefundResult]:
        results = []
        for refund_id, refund in refund_applications.items():
            if refund.is_exception:
                continue
            order = orders.get(refund.order_id)
            if not order:
                continue
            result = self.calculate_refund_result(refund, order, consumption_records)
            results.append(result)
        return results

    def mark_exception_handled(self, exception_id: str, opinion: str,
                               handler: str = "财务专员") -> bool:
        for e in self.exceptions:
            if e.get("exception_id") == exception_id:
                e["handled"] = True
                e["handler_opinion"] = opinion
                e["handled_at"] = datetime.now()
                e["handler"] = handler
                return True
        return False
