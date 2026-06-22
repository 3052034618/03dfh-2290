"""数据模型定义"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class OrderStatus(Enum):
    NORMAL = "normal"
    REFUNDED = "refunded"
    PARTIAL_REFUNDED = "partial_refunded"
    PENDING = "pending"


class RefundStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSED = "processed"
    EXCEPTION = "exception"


class ExceptionType(Enum):
    CONSUME_EXCEED_PURCHASE = "consume_exceed_purchase"
    REFUND_EXCEED_REMAINING = "refund_exceed_remaining"
    PRICE_MISMATCH = "price_mismatch"
    DISCOUNT_MISMATCH = "discount_mismatch"
    PACKAGE_SPLIT_ERROR = "package_split_error"
    DOCTOR_COMMISSION_MISMATCH = "doctor_commission_mismatch"
    CONSULTANT_COMMISSION_MISMATCH = "consultant_commission_mismatch"
    GIFT_DEDUCTION_ERROR = "gift_deduction_error"
    RECORD_NOT_FOUND = "record_not_found"
    DUPLICATE_REFUND = "duplicate_refund"


@dataclass
class Order:
    order_id: str
    store_id: str
    store_name: str
    customer_id: str
    customer_name: str
    item_id: str
    item_name: str
    item_type: str
    original_price: float
    discount_rate: float
    actual_price: float
    purchase_quantity: int
    purchased_at: datetime
    consultant_id: str
    consultant_name: str
    is_package: bool = False
    package_items: List[Dict[str, Any]] = field(default_factory=list)
    gifts: List[Dict[str, Any]] = field(default_factory=list)
    status: OrderStatus = OrderStatus.NORMAL
    remarks: str = ""

    @property
    def total_amount(self) -> float:
        return self.actual_price * self.purchase_quantity


@dataclass
class ConsumptionRecord:
    record_id: str
    order_id: str
    store_id: str
    store_name: str
    customer_id: str
    customer_name: str
    item_id: str
    item_name: str
    consume_quantity: float
    consume_amount: float
    consumed_at: datetime
    doctor_id: str
    doctor_name: str
    consultant_id: str
    consultant_name: str
    doctor_commission: float = 0.0
    consultant_commission: float = 0.0
    is_package_item: bool = False
    package_order_id: str = ""
    remarks: str = ""


@dataclass
class RefundApplication:
    refund_id: str
    order_id: str
    store_id: str
    store_name: str
    customer_id: str
    customer_name: str
    item_id: str
    item_name: str
    refund_quantity: float
    refund_amount: float
    apply_reason: str
    applied_at: datetime
    applicant: str
    status: RefundStatus = RefundStatus.PENDING
    handler_opinion: str = ""
    handled_at: Optional[datetime] = None
    handler: str = ""
    exceptions: List[Dict[str, Any]] = field(default_factory=list)
    is_exception: bool = False


@dataclass
class RefundResult:
    refund_id: str
    order_id: str
    store_id: str
    store_name: str
    customer_id: str
    customer_name: str
    item_id: str
    item_name: str
    refund_quantity: float
    original_refund_amount: float
    final_refund_amount: float
    doctor_commission_deduction: float
    consultant_commission_deduction: float
    gift_deduction_amount: float
    net_refund_amount: float
    remaining_quantity: float
    remaining_amount: float
    processed_at: datetime
    voucher_number: str = ""
    remarks: str = ""
    is_exception_adjusted: bool = False
    exception_opinion: str = ""


@dataclass
class Voucher:
    voucher_number: str
    voucher_date: datetime
    store_id: str
    store_name: str
    refund_id: str
    order_id: str
    customer_id: str
    customer_name: str
    item_name: str
    refund_amount: float
    doctor_commission_deduction: float
    consultant_commission_deduction: float
    gift_deduction: float
    net_amount: float
    generated_at: datetime
    generated_by: str = "system"


@dataclass
class ValidationRule:
    rule_id: str
    rule_name: str
    rule_type: str
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Store:
    store_id: str
    store_name: str
    region: str = ""
    is_active: bool = True
