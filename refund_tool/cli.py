"""命令行界面模块"""

import os
import sys
from datetime import datetime
from typing import List, Optional

import click
from tabulate import tabulate
from colorama import init, Fore, Style

from .config import ConfigManager
from .importer import DataImporter
from .validator import ValidationEngine
from .processor import ResultProcessor
from .logger import LogManager
from .utils import format_amount, format_date


init(autoreset=True)


class RefundCLI:
    def __init__(self):
        self.config = ConfigManager()
        self.importer: Optional[DataImporter] = None
        self.validator: Optional[ValidationEngine] = None
        self.processor: Optional[ResultProcessor] = None
        self.logger = LogManager(self.config.get_log_dir())
        self.exceptions = []
        self.trial_results = []
        self.confirmed = False

    def print_header(self, title: str):
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f"{Fore.CYAN}  {title}")
        print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")

    def print_success(self, msg: str):
        print(f"{Fore.GREEN}✓ {msg}{Style.RESET_ALL}")

    def print_error(self, msg: str):
        print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")

    def print_warning(self, msg: str):
        print(f"{Fore.YELLOW}⚠ {msg}{Style.RESET_ALL}")

    def print_info(self, msg: str):
        print(f"{Fore.BLUE}ℹ {msg}{Style.RESET_ALL}")

    def run_wizard(self):
        """配置向导"""
        self.print_header("退款核算配置向导")

        print("请按提示输入配置信息（直接回车使用默认值）\n")

        input_dir = click.prompt(
            "请输入数据输入目录",
            default=self.config.get_input_dir(),
            type=str,
        )
        self.config.set("input_dir", input_dir)

        output_dir = click.prompt(
            "请输入结果输出目录",
            default=self.config.get_output_dir(),
            type=str,
        )
        self.config.set("output_dir", output_dir)

        log_dir = click.prompt(
            "请输入日志目录",
            default=self.config.get_log_dir(),
            type=str,
        )
        self.config.set("log_dir", log_dir)

        doc_rate = click.prompt(
            "请输入医生提成比例(如0.15表示15%)",
            default=str(self.config.get("commission_rules.doctor_commission_rate", 0.15)),
            type=float,
        )
        self.config.set("commission_rules.doctor_commission_rate", doc_rate)

        cons_rate = click.prompt(
            "请输入咨询师提成比例(如0.1表示10%)",
            default=str(self.config.get("commission_rules.consultant_commission_rate", 0.1)),
            type=float,
        )
        self.config.set("commission_rules.consultant_commission_rate", cons_rate)

        voucher_prefix = click.prompt(
            "请输入凭证号前缀",
            default=self.config.get("voucher.prefix", "TK"),
            type=str,
        )
        self.config.set("voucher.prefix", voucher_prefix)

        self.config.save()
        self.print_success("配置已保存")

    def import_data(self, store_ids: Optional[List[str]] = None,
                    month: Optional[str] = None):
        """导入数据"""
        self.print_header("数据导入")

        self.importer = DataImporter(self.config.get_input_dir())

        self.print_info(f"输入目录: {self.config.get_input_dir()}")
        self.print_info(f"门店范围: {'全部' if not store_ids or 'all' in store_ids else ', '.join(store_ids)}")

        order_count, record_count, refund_count = self.importer.import_all(store_ids, month)

        self.print_success(f"导入订单: {order_count} 条")
        self.print_success(f"导入消费记录: {record_count} 条")
        self.print_success(f"导入退款申请: {refund_count} 条")

        summary = self.importer.get_summary()
        self.print_info(f"涉及门店: {summary['门店数']} 家")

        self.logger.log_operation("import", f"订单:{order_count}, 消费记录:{record_count}, 退款申请:{refund_count}")

        return order_count, record_count, refund_count

    def validate(self):
        """规则校验"""
        self.print_header("规则校验")

        if not self.importer:
            self.print_error("请先导入数据")
            return []

        self.validator = ValidationEngine(self.config.config)

        self.exceptions = self.validator.validate_all(
            self.importer.orders,
            self.importer.consumption_records,
            self.importer.refund_applications,
        )

        if not self.exceptions:
            self.print_success("校验通过，未发现异常")
        else:
            self.print_warning(f"发现 {len(self.exceptions)} 条异常")
            summary = self.validator.get_exception_summary()

            table_data = [[k, v] for k, v in summary.items()]
            print(tabulate(table_data, headers=["异常类型", "数量"], tablefmt="simple"))

        self.logger.log_operation("validate", f"发现异常:{len(self.exceptions)}条")

        return self.exceptions

    def show_exceptions(self):
        """显示异常清单"""
        if not self.exceptions:
            self.print_info("暂无异常数据")
            return

        self.print_header(f"异常清单 (共 {len(self.exceptions)} 条)")

        table_data = []
        for i, e in enumerate(self.exceptions, 1):
            table_data.append([
                i,
                e["related_id"],
                e["type_name"],
                e["message"],
                e.get("store_id", ""),
                "已处理" if e.get("handled") else "待处理",
            ])

        print(tabulate(
            table_data,
            headers=["序号", "关联单号", "异常类型", "异常描述", "门店", "状态"],
            tablefmt="simple",
            maxcolwidths=[5, 15, 15, 30, 8, 8],
        ))

    def handle_exceptions_interactive(self):
        """交互式处理异常"""
        if not self.exceptions:
            return

        unhandled = [e for e in self.exceptions if not e.get("handled")]
        if not unhandled:
            self.print_info("所有异常已处理")
            return

        self.print_header(f"异常处理 (待处理 {len(unhandled)} 条)")

        for i, e in enumerate(self.exceptions):
            if e.get("handled"):
                continue

            print(f"\n{Fore.YELLOW}--- 第 {i+1} 条异常 ---{Style.RESET_ALL}")
            print(f"关联单号: {e['related_id']}")
            print(f"异常类型: {e['type_name']}")
            print(f"异常描述: {e['message']}")
            if e.get("details"):
                print(f"详细信息: {e['details']}")

            print()
            action = click.prompt(
                "请选择处理方式: [1]跳过 [2]标记为已处理 [3]输入处理意见 [q]退出",
                default="1",
                type=str,
            )

            if action == "q":
                break
            elif action == "2":
                e["handled"] = True
                e["handler_opinion"] = "标记为已处理"
                self.print_success("已标记为已处理")
            elif action == "3":
                opinion = click.prompt("请输入处理意见", type=str)
                e["handled"] = True
                e["handler_opinion"] = opinion
                self.print_success("处理意见已保存")
            else:
                continue

        unhandled_count = len([e for e in self.exceptions if not e.get("handled")])
        self.print_info(f"剩余待处理: {unhandled_count} 条")

    def trial_calculate(self):
        """批量试算"""
        self.print_header("批量试算")

        if not self.validator or not self.importer:
            self.print_error("请先完成数据导入和规则校验")
            return None

        normal_refunds = {
            rid: r for rid, r in self.importer.refund_applications.items()
            if not r.is_exception
        }

        if not normal_refunds:
            self.print_warning("没有可试算的退款申请（全部为异常）")
            return None

        self.trial_results = self.validator.batch_calculate(
            normal_refunds,
            self.importer.orders,
            self.importer.consumption_records,
        )

        self.processor = ResultProcessor(
            self.config.get_output_dir(),
            self.config.get("voucher", {}),
        )
        summary = self.processor.set_trial_calculate(self.trial_results)

        self.print_success(f"试算完成，共 {summary['total_count']} 笔退款")

        table_data = [
            ["应退总金额", format_amount(summary["total_refund_amount"])],
            ["医生提成扣减", format_amount(summary["total_doctor_commission_deduction"])],
            ["咨询师提成扣减", format_amount(summary["total_consultant_commission_deduction"])],
            ["赠品扣减", format_amount(summary["total_gift_deduction"])],
            ["实退总金额", format_amount(summary["total_net_refund"])],
        ]
        print(tabulate(table_data, headers=["项目", "金额"], tablefmt="simple"))

        if summary["by_store"]:
            print(f"\n{Fore.CYAN}按门店汇总:{Style.RESET_ALL}")
            store_data = []
            for store_id, info in summary["by_store"].items():
                store_data.append([
                    info["store_name"],
                    info["count"],
                    format_amount(info["refund_amount"]),
                    format_amount(info["net_refund"]),
                ])
            print(tabulate(store_data, headers=["门店", "笔数", "应退金额", "实退金额"], tablefmt="simple"))

        self.logger.log_operation("trial_calculate", f"试算{summary['total_count']}笔，应退{summary['total_refund_amount']:.2f}")

        return summary

    def show_trial_details(self):
        """显示试算明细"""
        if not self.trial_results:
            self.print_info("暂无试算数据")
            return

        self.print_header("试算明细")

        table_data = []
        for i, r in enumerate(self.trial_results[:50], 1):
            table_data.append([
                i,
                r.refund_id,
                r.store_name,
                r.customer_name,
                r.item_name,
                r.refund_quantity,
                format_amount(r.final_refund_amount),
                format_amount(r.net_refund_amount),
            ])

        print(tabulate(
            table_data,
            headers=["序号", "退款单号", "门店", "客户", "项目", "数量", "应退金额", "实退金额"],
            tablefmt="simple",
            maxcolwidths=[5, 12, 10, 8, 15, 6, 12, 12],
        ))

        if len(self.trial_results) > 50:
            self.print_info(f"共 {len(self.trial_results)} 条，仅显示前 50 条")

    def confirm_results(self):
        """结果确认"""
        self.print_header("结果确认")

        if not self.trial_results:
            self.print_error("请先进行批量试算")
            return False

        print(f"共有 {len(self.trial_results)} 笔退款待确认")
        print(f"应退总金额: {format_amount(sum(r.final_refund_amount for r in self.trial_results))}")
        print(f"实退总金额: {format_amount(sum(r.net_refund_amount for r in self.trial_results))}")

        confirm = click.confirm("\n是否确认以上退款结果？", default=False)
        if confirm:
            self.processor.confirm_results()
            self.confirmed = True
            self.print_success("结果已确认")
            self.logger.log_operation("confirm", f"确认{len(self.trial_results)}笔退款")
        else:
            self.print_warning("未确认结果")

        return confirm

    def generate_vouchers(self):
        """生成凭证"""
        self.print_header("凭证生成")

        if not self.processor or not self.confirmed:
            self.print_error("请先确认结果")
            return []

        vouchers = self.processor.generate_vouchers()
        self.print_success(f"生成凭证 {len(vouchers)} 张")

        table_data = []
        for v in vouchers[:20]:
            table_data.append([
                v.voucher_number,
                v.store_name,
                v.customer_name,
                v.item_name,
                format_amount(v.refund_amount),
                format_amount(v.net_amount),
            ])

        print(tabulate(
            table_data,
            headers=["凭证号", "门店", "客户", "项目", "退款金额", "实退金额"],
            tablefmt="simple",
        ))

        return vouchers

    def export_results(self):
        """导出结果"""
        self.print_header("结果导出")

        if not self.processor:
            self.print_error("请先完成核算")
            return {}

        files = self.processor.export_all(self.exceptions)

        for name, path in files.items():
            self.print_success(f"{name}: {path}")

        self.logger.log_operation("export", f"导出{len(files)}个文件")

        return files

    def show_logs(self, lines: int = 50):
        """日志回看"""
        self.print_header("日志回看")

        log_files = self.logger.get_log_files()
        if not log_files:
            self.print_info("暂无日志文件")
            return

        print("可用日志文件:")
        for i, f in enumerate(log_files, 1):
            size_kb = f["size"] / 1024
            print(f"  [{i}] {f['filename']} ({size_kb:.1f}KB) - {f['modified'].strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            choice = click.prompt("\n请选择要查看的日志编号", default="1", type=int)
            if 1 <= choice <= len(log_files):
                selected = log_files[choice - 1]
                content = self.logger.read_log(selected["filename"], lines)
                print(f"\n{Fore.CYAN}{selected['filename']} (最近{lines}行):{Style.RESET_ALL}")
                print("-" * 60)
                for line in content:
                    print(line.rstrip())
                print("-" * 60)
        except (ValueError, click.Abort):
            pass

    def run_full_process(self, store_ids: Optional[List[str]] = None,
                         month: Optional[str] = None):
        """完整流程"""
        self.print_header("退款核算完整流程")

        self.import_data(store_ids, month)
        self.validate()

        if self.exceptions:
            self.show_exceptions()
            if click.confirm("\n是否现在处理异常？", default=True):
                self.handle_exceptions_interactive()

        self.trial_calculate()

        if self.trial_results:
            if click.confirm("\n是否查看试算明细？", default=False):
                self.show_trial_details()

            if self.confirm_results():
                self.generate_vouchers()
                self.export_results()
                self.print_success("\n核算流程已完成！")
            else:
                self.print_warning("\n流程已中止，结果未确认")
        else:
            self.print_warning("无可核算的退款")

    def show_stats(self):
        """显示统计信息"""
        self.print_header("统计概览")

        if not self.importer:
            self.print_info("暂无数据，请先导入")
            return

        summary = self.importer.get_summary()
        table_data = [[k, v] for k, v in summary.items()]
        print(tabulate(table_data, headers=["项目", "数量"], tablefmt="simple"))

        if self.exceptions:
            print(f"\n异常数: {Fore.RED}{len(self.exceptions)}{Style.RESET_ALL}")

        if self.trial_results:
            print(f"试算退款笔数: {Fore.GREEN}{len(self.trial_results)}{Style.RESET_ALL}")
