"""结果处理模块 - 批量试算、结果确认、冲减明细"""

import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from .models import (
    RefundResult, Voucher, RefundStatus, RefundApplication,
)
from .utils import format_amount, ensure_dir, sanitize_filename


class ResultProcessor:
    def __init__(self, output_dir: str = "./data/output", voucher_config: dict = None):
        self.output_dir = output_dir
        self.voucher_config = voucher_config or {}
        self.refund_results: List[RefundResult] = []
        self.confirmed_results: List[RefundResult] = []
        self.vouchers: List[Voucher] = []
        self.voucher_counter = self.voucher_config.get("start_number", 1)
        ensure_dir(self.output_dir)

    def set_trial_calculate(self, results: List[RefundResult]) -> Dict:
        self.refund_results = results
        summary = self._calculate_summary(results)
        return summary

    def _calculate_summary(self, results: List[RefundResult]) -> Dict:
        total_refund_amount = sum(r.final_refund_amount for r in results)
        total_doc_deduction = sum(r.doctor_commission_deduction for r in results)
        total_cons_deduction = sum(r.consultant_commission_deduction for r in results)
        total_gift_deduction = sum(r.gift_deduction_amount for r in results)
        total_net_refund = sum(r.net_refund_amount for r in results)

        by_store: Dict[str, Dict] = {}
        for r in results:
            store_key = r.store_id
            if store_key not in by_store:
                by_store[store_key] = {
                    "store_name": r.store_name,
                    "count": 0,
                    "refund_amount": 0,
                    "doc_deduction": 0,
                    "cons_deduction": 0,
                    "gift_deduction": 0,
                    "net_refund": 0,
                }
            by_store[store_key]["count"] += 1
            by_store[store_key]["refund_amount"] += r.final_refund_amount
            by_store[store_key]["doc_deduction"] += r.doctor_commission_deduction
            by_store[store_key]["cons_deduction"] += r.consultant_commission_deduction
            by_store[store_key]["gift_deduction"] += r.gift_deduction_amount
            by_store[store_key]["net_refund"] += r.net_refund_amount

        return {
            "total_count": len(results),
            "total_refund_amount": total_refund_amount,
            "total_doctor_commission_deduction": total_doc_deduction,
            "total_consultant_commission_deduction": total_cons_deduction,
            "total_gift_deduction": total_gift_deduction,
            "total_net_refund": total_net_refund,
            "by_store": by_store,
        }

    def confirm_results(self, result_ids: Optional[List[str]] = None) -> int:
        count = 0
        for result in self.refund_results:
            if result_ids is None or result.refund_id in result_ids:
                if result.refund_id not in [r.refund_id for r in self.confirmed_results]:
                    self.confirmed_results.append(result)
                    count += 1
        return count

    def is_confirmed(self) -> bool:
        return len(self.confirmed_results) > 0

    def generate_vouchers(self, results: Optional[List[RefundResult]] = None) -> List[Voucher]:
        if results is None:
            results = self.confirmed_results

        vouchers = []
        for result in results:
            voucher = Voucher(
                voucher_number=self._generate_voucher_number(),
                voucher_date=result.processed_at,
                store_id=result.store_id,
                store_name=result.store_name,
                refund_id=result.refund_id,
                order_id=result.order_id,
                customer_id=result.customer_id,
                customer_name=result.customer_name,
                item_name=result.item_name,
                refund_amount=result.final_refund_amount,
                doctor_commission_deduction=result.doctor_commission_deduction,
                consultant_commission_deduction=result.consultant_commission_deduction,
                gift_deduction=result.gift_deduction_amount,
                net_amount=result.net_refund_amount,
                generated_at=datetime.now(),
            )
            result.voucher_number = voucher.voucher_number
            vouchers.append(voucher)
            self.vouchers.append(voucher)

        return vouchers

    def _generate_voucher_number(self) -> str:
        prefix = self.voucher_config.get("prefix", "TK")
        digit_length = self.voucher_config.get("digit_length", 6)
        number = str(self.voucher_counter).zfill(digit_length)
        self.voucher_counter += 1
        return f"{prefix}{number}"

    def export_refund_table(self, results: Optional[List[RefundResult]] = None,
                            filename: str = "") -> str:
        if results is None:
            results = self.confirmed_results

        if not filename:
            filename = f"退款核算表_{datetime.now().strftime('%Y%m%d')}.xlsx"
        filepath = os.path.join(self.output_dir, sanitize_filename(filename))

        columns = [
            "退款单号", "订单号", "门店ID", "门店名称", "客户ID", "客户姓名",
            "项目ID", "项目名称", "退款数量", "应退金额", "医生提成扣减",
            "咨询师提成扣减", "赠品扣减", "实退金额", "剩余数量", "剩余金额",
            "凭证号", "处理时间", "备注",
        ]
        data = []
        for r in results:
            data.append({
                "退款单号": r.refund_id,
                "订单号": r.order_id,
                "门店ID": r.store_id,
                "门店名称": r.store_name,
                "客户ID": r.customer_id,
                "客户姓名": r.customer_name,
                "项目ID": r.item_id,
                "项目名称": r.item_name,
                "退款数量": r.refund_quantity,
                "应退金额": r.original_refund_amount,
                "医生提成扣减": r.doctor_commission_deduction,
                "咨询师提成扣减": r.consultant_commission_deduction,
                "赠品扣减": r.gift_deduction_amount,
                "实退金额": r.net_refund_amount,
                "剩余数量": r.remaining_quantity,
                "剩余金额": r.remaining_amount,
                "凭证号": r.voucher_number,
                "处理时间": r.processed_at.strftime("%Y-%m-%d %H:%M:%S"),
                "备注": r.remarks,
            })

        df = pd.DataFrame(data, columns=columns) if data else pd.DataFrame(columns=columns)
        df.to_excel(filepath, index=False, engine="openpyxl")
        return filepath

    def export_performance_deduction(self, results: Optional[List[RefundResult]] = None,
                                     filename: str = "") -> str:
        if results is None:
            results = self.confirmed_results

        if not filename:
            filename = f"业绩冲减表_{datetime.now().strftime('%Y%m%d')}.xlsx"
        filepath = os.path.join(self.output_dir, sanitize_filename(filename))

        detail_columns = [
            "凭证号", "门店ID", "门店名称", "项目名称", "退款金额",
            "医生提成冲减", "咨询师提成冲减", "赠品成本冲减", "净业绩冲减",
            "退款单号", "订单号", "客户姓名",
        ]
        data = []
        for r in results:
            data.append({
                "凭证号": r.voucher_number,
                "门店ID": r.store_id,
                "门店名称": r.store_name,
                "项目名称": r.item_name,
                "退款金额": r.final_refund_amount,
                "医生提成冲减": r.doctor_commission_deduction,
                "咨询师提成冲减": r.consultant_commission_deduction,
                "赠品成本冲减": r.gift_deduction_amount,
                "净业绩冲减": r.net_refund_amount,
                "退款单号": r.refund_id,
                "订单号": r.order_id,
                "客户姓名": r.customer_name,
            })

        df = pd.DataFrame(data, columns=detail_columns) if data else pd.DataFrame(columns=detail_columns)

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="业绩冲减明细", index=False)

            if data:
                summary_by_store = df.groupby(["门店ID", "门店名称"], dropna=False).agg({
                    "退款金额": "sum",
                    "医生提成冲减": "sum",
                    "咨询师提成冲减": "sum",
                    "赠品成本冲减": "sum",
                    "净业绩冲减": "sum",
                }).reset_index()
            else:
                summary_by_store = pd.DataFrame(
                    columns=["门店ID", "门店名称", "退款金额", "医生提成冲减",
                             "咨询师提成冲减", "赠品成本冲减", "净业绩冲减"]
                )
            summary_by_store.to_excel(writer, sheet_name="按门店汇总", index=False)

            if data:
                summary_by_item = df.groupby("项目名称", dropna=False).agg({
                    "退款金额": "sum",
                    "净业绩冲减": "sum",
                }).reset_index()
            else:
                summary_by_item = pd.DataFrame(columns=["项目名称", "退款金额", "净业绩冲减"])
            summary_by_item.to_excel(writer, sheet_name="按项目汇总", index=False)

        return filepath

    def export_review_list(self, exceptions: List[Dict],
                           filename: str = "") -> str:
        exceptions = exceptions or []

        if not filename:
            filename = f"待复核名单_{datetime.now().strftime('%Y%m%d')}.xlsx"
        filepath = os.path.join(self.output_dir, sanitize_filename(filename))

        columns = [
            "异常ID", "关联单号", "严重程度", "异常类型", "异常描述",
            "门店ID", "发现时间", "处理状态", "处理意见", "处理人", "详细信息",
        ]
        data = []
        for e in exceptions:
            if e.get("handled", False):
                continue
            data.append({
                "异常ID": e.get("exception_id", ""),
                "关联单号": e.get("related_id", ""),
                "严重程度": e.get("severity", "低"),
                "异常类型": e.get("type_name", ""),
                "异常描述": e.get("message", ""),
                "门店ID": e.get("store_id", ""),
                "发现时间": e["detected_at"].strftime("%Y-%m-%d %H:%M:%S")
                    if isinstance(e.get("detected_at"), datetime)
                    else str(e.get("detected_at", "")),
                "处理状态": "已处理" if e.get("handled", False) else "待处理",
                "处理意见": e.get("handler_opinion", ""),
                "处理人": e.get("handler", ""),
                "详细信息": str(e.get("details", {})),
            })

        df = pd.DataFrame(data, columns=columns) if data else pd.DataFrame(columns=columns)
        df.to_excel(filepath, index=False, engine="openpyxl")
        return filepath

    def export_exception_report(self, exceptions: List[Dict],
                                filename: str = "") -> str:
        exceptions = exceptions or []

        if not filename:
            filename = f"异常报告_{datetime.now().strftime('%Y%m%d')}.xlsx"
        filepath = os.path.join(self.output_dir, sanitize_filename(filename))

        base_columns = [
            "异常ID", "关联单号", "严重程度", "异常类型", "异常描述",
            "门店ID", "发现时间", "处理状态", "处理意见", "处理人", "处理时间",
        ]
        data = []
        for e in exceptions:
            details = e.get("details", {}) or {}
            row = {
                "异常ID": e.get("exception_id", ""),
                "关联单号": e.get("related_id", ""),
                "严重程度": e.get("severity", "低"),
                "异常类型": e.get("type_name", ""),
                "异常描述": e.get("message", ""),
                "门店ID": e.get("store_id", ""),
                "发现时间": e["detected_at"].strftime("%Y-%m-%d %H:%M:%S")
                    if isinstance(e.get("detected_at"), datetime)
                    else str(e.get("detected_at", "")),
                "处理状态": "已处理" if e.get("handled", False) else "待处理",
                "处理意见": e.get("handler_opinion", ""),
                "处理人": e.get("handler", ""),
                "处理时间": e["handled_at"].strftime("%Y-%m-%d %H:%M:%S")
                    if isinstance(e.get("handled_at"), datetime)
                    else "",
            }
            for k, v in details.items():
                row[f"详情_{k}"] = v
            data.append(row)

        df = pd.DataFrame(data) if data else pd.DataFrame(columns=base_columns)

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="异常明细", index=False)

            if data:
                summary = df.groupby(["异常类型", "处理状态"], dropna=False).agg(
                    数量=("异常类型", "count"),
                ).reset_index()
            else:
                summary = pd.DataFrame(columns=["异常类型", "处理状态", "数量"])
            summary.to_excel(writer, sheet_name="异常汇总", index=False)

            sev_df = df.copy() if data else pd.DataFrame(columns=["严重程度", "数量"])
            if data:
                sev_summary = df.groupby("严重程度", dropna=False).agg(
                    数量=("严重程度", "count"),
                ).reset_index()
            else:
                sev_summary = pd.DataFrame(columns=["严重程度", "数量"])
            sev_summary.to_excel(writer, sheet_name="按严重程度", index=False)

        return filepath

    def export_all(self, exceptions: List[Dict]) -> Dict[str, str]:
        files = {}
        files["退款核算表"] = self.export_refund_table()
        files["业绩冲减表"] = self.export_performance_deduction()
        files["待复核名单"] = self.export_review_list(exceptions)
        files["异常报告"] = self.export_exception_report(exceptions)
        return files
