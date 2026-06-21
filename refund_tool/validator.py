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
            if total_consumed > order.purchase_quantity:
                self._add_exception(
                    order.order_id,
                    ExceptionType.CONSUME_EXCEED_PURCHASE,
                    f"已消费次数({total_consumed})大于购买次数({order.purchase_quantity})",
                    order.store_id,
                    {"order_id": order.order_id, "item_name": order.item_name,
                     "purchased": order.purchase_quantity, "consumed": total_consumed}
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
                f"消费金额({total_consume_amount:.2f})与预期({expected_consume_amount:.2f})不符",
                order.store_id,
                {"order_id": order.order_id, "item_name": order.item_name,
                 "actual": total_consume_amount, "expected": expected_consume_amount}
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
                 "expected_price": expected_price}
            )

    def _validate_refund(self, refund: RefundApplication, order: Order,
                         consumption_records: List[ConsumptionRecord]):
        order_consumptions = [r for r in consumption_records if r.order_id == order.order_id]
        total_consumed = sum(r.consume_quantity for r in order_consumptions)

        remaining_quantity = order.purchase_quantity - total_consumed
        remaining_amount = remaining_quantity * order.actual_price

        if not self.rules.get("allow_refund_exceed_remaining", False):
            if refund.refund_quantity > remaining_quantity:
                self._add_exception(
                    refund.refund_id,
                    ExceptionType.REFUND_EXCEED_REMAINING,
                    f"退款数量({refund.refund_quantity})超过剩余数量({remaining_quantity:.2f})",
                    refund.store_id,
                    {"refund_id": refund.refund_id, "item_name": refund.item_name,
                     "refund_quantity": refund.refund_quantity,
                     "remaining_quantity": remaining_quantity,
                     "remaining_amount": remaining_amount}
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
                    {"refund_id": refund.refund_id, "item_name": refund.item_name,
                     "refund_amount": refund.refund_amount,
                     "expected_amount": expected_refund_amount}
                )
                refund.is_exception = True
                refund.status = RefundStatus.EXCEPTION

        if self.rules.get("check_package_split", True) and order.is_package:
            self._check_package_refund(refund, order)

        if not self.rules.get("allow_consume_exceed_purchase", False):
            if total_consumed > order.purchase_quantity:
                self._add_exception(
                    refund.refund_id,
                    ExceptionType.CONSUME_EXCEED_PURCHASE,
                    f"关联订单存在超消费: 已消费{total_consumed:.2f} > 购买{order.purchase_quantity}",
                    refund.store_id,
                    {"refund_id": refund.refund_id, "order_id": order.order_id,
                     "purchased": order.purchase_quantity, "consumed": total_consumed}
                )
                refund.is_exception = True
                refund.status = RefundStatus.EXCEPTION

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
                        f"医生提成({record.doctor_commission:.2f})与预期({expected:.2f})不符",
                        record.store_id,
                        {"record_id": record.record_id, "doctor_name": record.doctor_name,
                         "actual": record.doctor_commission, "expected": expected,
                         "consume_amount": record.consume_amount}
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
                        f"咨询师提成({record.consultant_commission:.2f})与预期({expected:.2f})不符",
                        record.store_id,
                        {"record_id": record.record_id, "consultant_name": record.consultant_name,
                         "actual": record.consultant_commission, "expected": expected,
                         "consume_amount": record.consume_amount}
                    )

    def _check_package_refund(self, refund: RefundApplication, order: Order):
        if order.is_package and len(order.package_items) > 0:
            method = self.commission_rules.get("package_split_method", "average")
            if method == "average":
                item_count = len(order.package_items)
                if item_count > 0:
                    per_item_amt = refund.refund_amount / item_count
                    for pkg_item in order.package_items:
                        if pkg_item.get("price", 0) > 0 and abs(pkg_item.get("price") - per_item_amt) > 0.01:
                            self._add_exception(
                                refund.refund_id,
                                ExceptionType.PACKAGE_SPLIT_ERROR,
                                f"套餐项目拆分金额不均: {pkg_item.get('name', '')}",
                                refund.store_id,
                                {"refund_id": refund.refund_id,
                                 "package_item": pkg_item.get("name", ""),
                                 "item_price": pkg_item.get("price", 0),
                                 "average_price": per_item_amt}
                            )
                            break

    def _add_exception(self, related_id: str, exception_type: ExceptionType,
                       message: str, store_id: str = "",
                       details: Optional[Dict] = None):
        exception = {
            "related_id": related_id,
            "type": exception_type.value,
            "type_name": self._get_exception_name(exception_type),
            "message": message,
            "store_id": store_id,
            "details": details or {},
            "detected_at": datetime.now(),
            "handled": False,
            "handler_opinion": "",
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

    def get_exceptions_by_type(self, exception_type: ExceptionType) -> List[Dict]:
        return [e for e in self.exceptions if e["type"] == exception_type.value]

    def get_exceptions_by_store(self, store_id: str) -> List[Dict]:
        return [e for e in self.exceptions if e["store_id"] == store_id]

    def get_unhandled_exceptions(self) -> List[Dict]:
        return [e for e in self.exceptions if not e["handled"]]

    def get_exception_summary(self) -> Dict[str, int]:
        summary = {}
        for e in self.exceptions:
            t = e["type_name"]
            summary[t] = summary.get(t, 0) + 1
        return summary

    def calculate_refund_result(self, refund: RefundApplication, order: Order,
                                consumption_records: List[ConsumptionRecord]) -> RefundResult:
        order_consumptions = [r for r in consumption_records if r.order_id == order.order_id]
        total_consumed = sum(r.consume_quantity for r in order_consumptions)

        remaining_quantity = order.purchase_quantity - total_consumed
        remaining_amount = remaining_quantity * order.actual_price

        actual_refund_qty = min(refund.refund_quantity, remaining_quantity)
        original_refund_amt = actual_refund_qty * order.actual_price

        doc_rate = self.commission_rules.get("doctor_commission_rate", 0.15)
        cons_rate = self.commission_rules.get("consultant_commission_rate", 0.1)

        doc_deduction = original_refund_amt * doc_rate
        cons_deduction = original_refund_amt * cons_rate

        gift_deduction = 0.0
        if order.gifts and len(order.gifts) > 0:
            for gift in order.gifts:
                gift_price = float(gift.get("price", 0))
                gift_quantity = float(gift.get("quantity", 0))
                refund_ratio = actual_refund_qty / order.purchase_quantity if order.purchase_quantity > 0 else 0
                gift_deduction += gift_price * gift_quantity * refund_ratio

        net_refund = original_refund_amt - doc_deduction - cons_deduction - gift_deduction

        new_remaining_qty = remaining_quantity - actual_refund_qty
        new_remaining_amt = new_remaining_qty * order.actual_price

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
            original_refund_amount=original_refund_amt,
            final_refund_amount=original_refund_amt,
            doctor_commission_deduction=doc_deduction,
            consultant_commission_deduction=cons_deduction,
            gift_deduction_amount=gift_deduction,
            net_refund_amount=net_refund,
            remaining_quantity=new_remaining_qty,
            remaining_amount=new_remaining_amt,
            processed_at=datetime.now(),
            remarks=refund.apply_reason,
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
