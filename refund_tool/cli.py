"""命令行界面模块 - 集成会话状态持久化"""

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
from .session import SessionManager
from .utils import format_amount, format_date


init(autoreset=True)


class RefundCLI:
    def __init__(self):
        self.config = ConfigManager()
        self.logger = LogManager(self.config.get_log_dir())
        self.session = SessionManager(os.path.join(
            os.path.dirname(self.config.get_log_dir()), "state"
        ))

        self.importer: Optional[DataImporter] = self.session.get("importer")
        self.validator: Optional[ValidationEngine] = self.session.get("validator")
        self.processor: Optional[ResultProcessor] = self.session.get("processor")
        self.exceptions: List[dict] = self.session.get("exceptions", [])
        self.trial_results = self.session.get("trial_results", [])
        self.confirmed: bool = self.session.get("confirmed", False)

    def _persist(self):
        self.session.set("importer", self.importer)
        self.session.set("validator", self.validator)
        self.session.set("processor", self.processor)
        self.session.set("exceptions", self.exceptions)
        self.session.set("trial_results", self.trial_results)
        self.session.set("confirmed", self.confirmed)

    def print_header(self, title: str):
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f"{Fore.CYAN}  {title}")
        print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")

    def print_success(self, msg: str):
        print(f"{Fore.GREEN}[OK] {msg}{Style.RESET_ALL}")

    def print_error(self, msg: str):
        print(f"{Fore.RED}[ERR] {msg}{Style.RESET_ALL}")

    def print_warning(self, msg: str):
        print(f"{Fore.YELLOW}[!] {msg}{Style.RESET_ALL}")

    def print_info(self, msg: str):
        print(f"{Fore.BLUE}[i] {msg}{Style.RESET_ALL}")

    def show_status(self):
        self.session.print_status()

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
                    month: Optional[str] = None) -> Optional[DataImporter]:
        """导入数据"""
        self.print_header("数据导入")

        if self.importer:
            self.print_info("检测到已有导入数据，将重新导入")

        self.importer = DataImporter(self.config.get_input_dir())

        self.print_info(f"输入目录: {self.config.get_input_dir()}")
        store_display = '全部' if not store_ids or 'all' in store_ids else ', '.join(store_ids)
        self.print_info(f"门店范围: {store_display}")
        self.print_info(f"核算月份: {month or '未指定（全部）'}")

        order_count, record_count, refund_count = self.importer.import_all(store_ids, month)

        self.print_success(f"导入订单: {order_count} 条")
        self.print_success(f"导入消费记录: {record_count} 条")
        self.print_success(f"导入退款申请: {refund_count} 条")

        summary = self.importer.get_summary()
        self.print_info(f"涉及门店: {summary['门店数']} 家")
        if month:
            self.print_info(f"已按月份过滤: {month}")

        if order_count == 0 and record_count == 0 and refund_count == 0:
            self.print_warning("未找到任何数据，请检查输入目录下是否存在Excel/CSV文件")

        self.session.set_params(store_ids, month)
        self.validator = None
        self.exceptions = []
        self.trial_results = []
        self.confirmed = False
        self.processor = None
        self._persist()

        self.logger.log_operation("import", f"订单:{order_count}, 消费记录:{record_count}, 退款申请:{refund_count}, 月份:{month}")

        return self.importer

    def validate(self) -> Optional[List[dict]]:
        """规则校验"""
        self.print_header("规则校验")

        if not self.importer:
            self.print_error("请先导入数据 (命令: import-data)")
            return None

        self.validator = ValidationEngine(self.config.config)

        self.exceptions = self.validator.validate_all(
            self.importer.orders,
            self.importer.consumption_records,
            self.importer.refund_applications,
        )

        self.trial_results = []
        self.confirmed = False
        self.processor = None
        self._persist()

        if not self.exceptions:
            self.print_success("校验通过，未发现异常")
        else:
            unhandled = len([e for e in self.exceptions if not e.get("handled")])
            self.print_warning(f"发现 {len(self.exceptions)} 条异常（待处理: {unhandled}）")
            summary = self.validator.get_exception_summary()

            table_data = []
            for k, v in summary.items():
                table_data.append([k, v["总数"], v["待处理"], v.get("高", 0), v.get("中", 0), v.get("低", 0)])
            print(tabulate(table_data, headers=["异常类型", "总数", "待处理", "高危", "中危", "低危"], tablefmt="simple"))

        self.logger.log_operation("validate", f"发现异常:{len(self.exceptions)}条")
        return self.exceptions

    def show_exceptions(self, only_unhandled: bool = False):
        """显示异常清单"""
        display_exceptions = self.exceptions
        if only_unhandled:
            display_exceptions = [e for e in self.exceptions if not e.get("handled")]

        if not display_exceptions:
            self.print_info("暂无异常数据")
            return

        title = f"待处理异常清单 (共 {len(display_exceptions)} 条)" if only_unhandled else f"异常清单 (共 {len(self.exceptions)} 条)"
        self.print_header(title)

        table_data = []
        for i, e in enumerate(display_exceptions, 1):
            sev_color = Fore.RED if e.get("severity") == "高" else (Fore.YELLOW if e.get("severity") == "中" else Fore.WHITE)
            table_data.append([
                i,
                e.get("exception_id", ""),
                e.get("related_id", ""),
                sev_color + e.get("severity", "低") + Style.RESET_ALL,
                e.get("type_name", ""),
                e.get("message", "")[:40],
                e.get("store_id", ""),
                Fore.GREEN + "已处理" + Style.RESET_ALL if e.get("handled") else Fore.RED + "待处理" + Style.RESET_ALL,
            ])

        print(tabulate(
            table_data,
            headers=["序号", "异常ID", "关联单号", "严重度", "异常类型", "异常描述", "门店", "状态"],
            tablefmt="simple",
            maxcolwidths=[5, 10, 12, 6, 12, 40, 6, 8],
        ))

    def handle_exceptions_interactive(self) -> int:
        """交互式处理异常"""
        if not self.exceptions:
            self.print_info("暂无异常需要处理")
            return 0

        unhandled = [e for e in self.exceptions if not e.get("handled")]
        if not unhandled:
            self.print_info("所有异常已处理完成")
            return 0

        self.print_header(f"异常处理 (待处理 {len(unhandled)} 条)")

        total = len(unhandled)
        processed = 0
        for idx, e in enumerate(self.exceptions):
            if e.get("handled"):
                continue

            processed += 1
            sev_display = f"[{e.get('severity', '低')}]"
            sev_color = Fore.RED if e.get("severity") == "高" else (Fore.YELLOW if e.get("severity") == "中" else "")

            print(f"\n{Fore.CYAN}--- [{processed}/{total}] {sev_color}{sev_display}{Style.RESET_ALL} ---")
            print(f"异常ID: {e.get('exception_id', '')}")
            print(f"关联单号: {e.get('related_id', '')}")
            print(f"异常类型: {e.get('type_name', '')}")
            print(f"所属门店: {e.get('store_id', '')}")
            print(f"异常描述: {e.get('message', '')}")
            if e.get("details"):
                detail_str = ", ".join([f"{k}={v}" for k, v in list(e["details"].items())[:5]])
                print(f"详细信息: {detail_str}")

            print()
            print("请选择处理方式:")
            print("  [1] 调整后通过 - 标记为已处理（保留该笔数据）")
            print("  [2] 不予退款 - 标记为已处理（剔除该笔）")
            print("  [3] 门店核实后再处理 - 标记待复核")
            print("  [4] 输入自定义处理意见")
            if processed < total:
                print("  [s] 跳过此条")
            print("  [q] 退出处理流程")

            while True:
                action = click.prompt("请输入选项", default="1", type=str).strip().lower()
                if action in ["1", "2", "3", "4", "s", "q", "skip", "quit", "exit"]:
                    break
                self.print_warning("输入无效，请重新选择")

            if action in ["q", "quit", "exit"]:
                self.print_warning(f"已退出处理，剩余 {total - processed} 条未处理")
                break
            if action in ["s", "skip"]:
                continue

            opinions = {
                "1": "财务核实：数据属实，调整后通过退款",
                "2": "财务裁定：依据异常情况，不予退款",
                "3": "待门店补充材料核实后再处理",
            }

            if action == "4":
                opinion = click.prompt("请输入处理意见", default="", type=str)
                if not opinion.strip():
                    opinion = "已人工复核，标记为处理"
            else:
                opinion = opinions[action]
                extra = click.prompt(f"补充说明(可留空)", default="", type=str)
                if extra.strip():
                    opinion = f"{opinion}；{extra.strip()}"

            handler = click.prompt("处理人姓名", default="财务专员", type=str)

            e["handled"] = True
            e["handler_opinion"] = opinion
            e["handler"] = handler
            e["handled_at"] = datetime.now()

            if self.validator:
                self.validator.mark_exception_handled(
                    e.get("exception_id", ""), opinion, handler
                )

            self.print_success(f"已处理：{opinion[:30]}")

        self._persist()

        still_unhandled = len([e for e in self.exceptions if not e.get("handled")])
        self.print_info(f"当前异常处理状态：已处理 {len(self.exceptions) - still_unhandled}/{len(self.exceptions)}，待处理 {still_unhandled}")

        if still_unhandled > 0:
            self.print_warning("[!] 仍有待处理异常，无法进行结果确认！")

        return processed

    def check_all_exceptions_handled(self) -> bool:
        """检查是否所有异常都已处理"""
        if not self.exceptions:
            return True
        unhandled = [e for e in self.exceptions if not e.get("handled")]
        if unhandled:
            high_sev = [e for e in unhandled if e.get("severity") == "高"]
            if high_sev:
                self.print_error(f"存在 {len(high_sev)} 条高危异常未处理，不允许进入结果确认")
            else:
                self.print_warning(f"存在 {len(unhandled)} 条异常未处理")
            return False
        return True

    def trial_calculate(self):
        """批量试算"""
        self.print_header("批量试算")

        if not self.validator or not self.importer:
            if not self.importer:
                self.print_error("请先导入数据 (命令: import-data)")
            else:
                self.print_info("未发现校验结果，将自动执行校验")
                self.validate()
            if not self.validator:
                return None

        if not self.check_all_exceptions_handled():
            self.print_error("请先处理所有异常后再进行试算 (命令: handle-exceptions)")
            return None

        normal_refunds = {
            rid: r for rid, r in self.importer.refund_applications.items()
            if not r.is_exception
        }

        if not normal_refunds:
            self.print_warning("没有可试算的退款申请（全部为异常或已排除）")
            self.trial_results = []
            self.confirmed = False
            self.processor = None
            self._persist()
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

        self.confirmed = False
        self._persist()

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
                    format_amount(info["doc_deduction"]),
                    format_amount(info["cons_deduction"]),
                    format_amount(info["gift_deduction"]),
                    format_amount(info["net_refund"]),
                ])
            print(tabulate(
                store_data,
                headers=["门店", "笔数", "应退金额", "医生扣减", "咨询师扣减", "赠品扣减", "实退金额"],
                tablefmt="simple",
            ))

        self.logger.log_operation("trial_calculate", f"试算{summary['total_count']}笔，应退{summary['total_refund_amount']:.2f}")

        return summary

    def show_trial_details(self):
        """显示试算明细"""
        if not self.trial_results:
            self.print_info("暂无试算数据，请先执行试算 (命令: trial)")
            return

        self.print_header(f"试算明细 (共 {len(self.trial_results)} 笔)")

        table_data = []
        for i, r in enumerate(self.trial_results[:50], 1):
            has_gift = "[赠]" if r.gift_deduction_amount > 0 else ""
            table_data.append([
                i,
                r.refund_id,
                r.store_name,
                r.customer_name,
                r.item_name,
                r.refund_quantity,
                format_amount(r.final_refund_amount),
                format_amount(r.doctor_commission_deduction),
                format_amount(r.consultant_commission_deduction),
                format_amount(r.gift_deduction_amount),
                format_amount(r.net_refund_amount),
                has_gift,
            ])

        print(tabulate(
            table_data,
            headers=["序号", "退款单号", "门店", "客户", "项目", "数量", "应退金额", "医生扣减", "咨询扣减", "赠品扣减", "实退金额", "有赠品"],
            tablefmt="simple",
            maxcolwidths=[5, 12, 10, 8, 15, 6, 12, 10, 10, 10, 12, 6],
        ))

        if len(self.trial_results) > 50:
            self.print_info(f"共 {len(self.trial_results)} 条，仅显示前 50 条")

    def confirm_results(self) -> bool:
        """结果确认"""
        self.print_header("结果确认")

        if not self.trial_results:
            self.print_error("请先进行批量试算 (命令: trial)")
            return False

        if not self.check_all_exceptions_handled():
            self.print_error("存在未处理异常，请先完成异常处理 (命令: handle-exceptions)")
            return False

        self.print_info(f"共有 {len(self.trial_results)} 笔退款待确认")

        total_refund = sum(r.final_refund_amount for r in self.trial_results)
        total_doc = sum(r.doctor_commission_deduction for r in self.trial_results)
        total_cons = sum(r.consultant_commission_deduction for r in self.trial_results)
        total_gift = sum(r.gift_deduction_amount for r in self.trial_results)
        total_net = sum(r.net_refund_amount for r in self.trial_results)

        summary = [
            ["退款笔数", len(self.trial_results)],
            ["应退总金额", format_amount(total_refund)],
            ["医生提成扣减合计", format_amount(total_doc)],
            ["咨询师提成扣减合计", format_amount(total_cons)],
            ["赠品扣减合计", format_amount(total_gift)],
            ["实退总金额", format_amount(total_net)],
        ]
        print(tabulate(summary, headers=["项目", "数值"], tablefmt="simple"))

        if self.confirmed:
            self.print_warning("该批次结果已经确认过，如需重新确认请先重新试算")
            if not click.confirm("是否覆盖原有确认？", default=False):
                return True

        confirm = click.confirm("\n是否确认以上退款结果？确认后将无法修改", default=False)
        if confirm:
            if not self.processor:
                self.processor = ResultProcessor(
                    self.config.get_output_dir(),
                    self.config.get("voucher", {}),
                )
                self.processor.set_trial_calculate(self.trial_results)
            self.processor.confirm_results()
            self.confirmed = True
            self._persist()
            self.print_success("结果已确认，可继续生成凭证和导出报表")
            self.logger.log_operation("confirm", f"确认{len(self.trial_results)}笔退款")
        else:
            self.print_warning("未确认结果，可修改后重新确认")

        return self.confirmed

    def generate_vouchers(self):
        """生成凭证"""
        self.print_header("凭证生成")

        if not self.confirmed:
            self.print_error("请先确认结果 (命令: confirm)")
            return []

        if not self.processor:
            self.print_error("处理状态异常，请重新执行试算和确认")
            return []

        vouchers = self.processor.generate_vouchers()
        self._persist()

        self.print_success(f"生成凭证 {len(vouchers)} 张")

        if vouchers:
            table_data = []
            for v in vouchers[:30]:
                table_data.append([
                    v.voucher_number,
                    v.store_name,
                    v.customer_name,
                    v.item_name,
                    format_amount(v.refund_amount),
                    format_amount(v.doctor_commission_deduction),
                    format_amount(v.consultant_commission_deduction),
                    format_amount(v.gift_deduction),
                    format_amount(v.net_amount),
                ])
            print(tabulate(
                table_data,
                headers=["凭证号", "门店", "客户", "项目", "退款金额", "医生扣减", "咨询扣减", "赠品扣减", "实退金额"],
                tablefmt="simple",
                maxcolwidths=[10, 10, 8, 15, 12, 10, 10, 10, 12],
            ))

            if len(vouchers) > 30:
                self.print_info(f"共 {len(vouchers)} 张凭证，仅显示前 30 张")

        self.logger.log_operation("voucher", f"生成{len(vouchers)}张凭证")

        return vouchers

    def export_results(self) -> Optional[dict]:
        """导出结果"""
        self.print_header("结果导出")

        if not self.processor:
            self.print_error("请先完成核算流程 (import → validate → handle → trial → confirm)")
            return None

        if not self.confirmed:
            if not click.confirm("结果尚未确认，仍要导出吗？", default=False):
                return None

        files = self.processor.export_all(self.exceptions)

        total_files = len(files)
        export_count = 0
        for name, path in files.items():
            if os.path.exists(path):
                size_kb = os.path.getsize(path) / 1024
                self.print_success(f"{name}: {path} ({size_kb:.1f}KB)")
                export_count += 1
            else:
                self.print_warning(f"{name}: 导出失败，文件未生成")

        self.logger.log_operation("export", f"导出{export_count}/{total_files}个文件")

        if export_count == total_files:
            self.print_success(f"\n全部 {total_files} 个文件导出成功！")
        else:
            self.print_warning(f"\n部分文件导出失败: {export_count}/{total_files}")

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
            choice = click.prompt("\n请选择要查看的日志编号 (0退出)", default="1", type=int)
            if choice == 0:
                return
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

    def clear_session(self):
        """清空会话状态"""
        self.print_warning("将清空当前会话中的所有中间数据（导入数据、校验结果、试算结果等）")
        if click.confirm("确认清空？", default=False):
            self.importer = None
            self.validator = None
            self.processor = None
            self.exceptions = []
            self.trial_results = []
            self.confirmed = False
            self.session.clear_all()
            self.print_success("会话已清空")

    def run_full_process(self, store_ids: Optional[List[str]] = None,
                         month: Optional[str] = None):
        """完整流程"""
        self.print_header("退款核算完整流程")

        self.show_status()

        if not self.importer:
            self.import_data(store_ids, month)
        else:
            self.print_info("使用已导入的数据")

        if not self.validator:
            self.validate()
        elif not self.exceptions:
            self.print_info("使用已有的校验结果")
        self.show_exceptions()

        while True:
            unhandled = len([e for e in self.exceptions if not e.get("handled")])
            if unhandled == 0:
                break
            self.print_warning(f"\n[!] 当前有 {unhandled} 条异常未处理，必须全部处理才能进入结果确认")
            if click.confirm(f"是否现在处理异常？({unhandled}条待处理)", default=True):
                self.handle_exceptions_interactive()
            else:
                self.print_warning("已取消完整流程，下次可继续处理")
                return

        if not self.trial_results or not self.processor:
            self.trial_calculate()
        if not self.trial_results:
            self.print_warning("无可核算的退款，流程结束")
            return

        if click.confirm("\n是否查看试算明细？", default=False):
            self.show_trial_details()

        if not self.confirmed:
            if not self.confirm_results():
                self.print_warning("结果未确认，流程中止")
                return

        if click.confirm("是否生成凭证？", default=True):
            self.generate_vouchers()

        if click.confirm("是否导出结果报表？", default=True):
            self.export_results()
            self.print_success("\n[OK] 核算流程全部完成！")
        else:
            self.print_info("\n流程完成，结果可随时使用 export 命令导出")

        self.show_status()

    def show_stats(self):
        """显示统计信息"""
        self.print_header("统计概览")

        if not self.importer:
            self.print_info("暂无数据，请先导入 (命令: import-data)")
            self.show_status()
            return

        summary = self.importer.get_summary()
        table_data = [[k, v] for k, v in summary.items()]
        print(tabulate(table_data, headers=["项目", "数量/数值"], tablefmt="simple"))

        if self.exceptions:
            unhandled = len([e for e in self.exceptions if not e.get("handled")])
            print(f"\n发现异常: {Fore.RED}{len(self.exceptions)}{Style.RESET_ALL} 条"
                  f"（待处理: {Fore.YELLOW}{unhandled}{Style.RESET_ALL}）")

        if self.trial_results:
            total_net = sum(r.net_refund_amount for r in self.trial_results)
            print(f"试算退款笔数: {Fore.GREEN}{len(self.trial_results)}{Style.RESET_ALL} 笔"
                  f"，实退总额: {Fore.GREEN}{format_amount(total_net)}{Style.RESET_ALL}")
            if self.confirmed:
                self.print_success("结果状态: 已确认 [OK]")
            else:
                self.print_warning("结果状态: 待确认")
