"""医美退款退项批处理工具 - 主入口"""

import click
from colorama import init, Fore, Style

from refund_tool.cli import RefundCLI
from refund_tool import __version__


init(autoreset=True)

cli_instance = RefundCLI()


@click.group(help="医美退款退项批处理工具 - 面向连锁机构总部财务专员")
@click.version_option(__version__, prog_name="退款核算工具")
def main():
    """医美退款退项批处理工具"""
    pass


@main.command(help="配置向导 - 交互式设置参数")
def config():
    """配置向导"""
    cli_instance.run_wizard()


@main.command("status", help="查看当前会话状态")
def status_cmd():
    """查看会话状态"""
    cli_instance.show_status()


@main.command("import-data", help="导入数据 - 导入订单、消费记录、退款申请")
@click.option("--store", "-s", multiple=True, help="门店ID，可多次指定，默认全部")
@click.option("--month", "-m", help="核算月份，格式: YYYY-MM (只保留该月内相关记录)")
def import_data(store, month):
    """导入数据"""
    store_list = list(store) if store else None
    cli_instance.import_data(store_list, month)
    cli_instance.show_status()


@main.command(help="规则校验 - 检查价格、折扣、提成、套餐、赠品等是否匹配")
def validate():
    """规则校验"""
    if not cli_instance.importer:
        cli_instance.import_data()
    cli_instance.validate()
    cli_instance.show_exceptions()


@main.command("exceptions", help="异常清单 - 查看所有异常记录")
@click.option("--pending", is_flag=True, help="只显示待处理异常")
def exceptions_cmd(pending):
    """异常清单"""
    if not cli_instance.exceptions:
        if not cli_instance.importer:
            cli_instance.import_data()
        cli_instance.validate()
    cli_instance.show_exceptions(only_unhandled=pending)


@main.command("handle-exceptions", help="处理异常 - 交互式逐条处理异常记录(必须全部处理)")
def handle_exceptions():
    """处理异常 - 必须全部处理完才能继续后续流程"""
    if not cli_instance.exceptions:
        if not cli_instance.importer:
            cli_instance.import_data()
        cli_instance.validate()
    count = cli_instance.handle_exceptions_interactive()
    if count > 0:
        remaining = len([e for e in cli_instance.exceptions if not e.get("handled")])
        if remaining > 0:
            click.echo(f"\n{Fore.YELLOW}提示: 还有 {remaining} 条异常未处理，下次可继续运行 handle-exceptions 命令处理{Style.RESET_ALL}")


@main.command(help="批量试算 - 计算所有退款的详细金额(含赠品扣减)")
def trial():
    """批量试算"""
    if not cli_instance.validator:
        if not cli_instance.importer:
            cli_instance.import_data()
        cli_instance.validate()
    cli_instance.trial_calculate()


@main.command("trial-detail", help="查看试算明细 - 含赠品扣减标识")
def trial_detail():
    """查看试算明细"""
    if not cli_instance.trial_results:
        if not cli_instance.validator:
            if not cli_instance.importer:
                cli_instance.import_data()
            cli_instance.validate()
        cli_instance.trial_calculate()
    cli_instance.show_trial_details()


@main.command(help="结果确认 - 异常必须全部处理后才能确认")
def confirm():
    """结果确认"""
    if not cli_instance.trial_results:
        click.echo("请先进行批量试算 (命令: trial)")
        return
    if not cli_instance.check_all_exceptions_handled():
        click.echo(f"{Fore.RED}请先使用 handle-exceptions 命令处理完全部异常{Style.RESET_ALL}")
        return
    cli_instance.confirm_results()


@main.command(help="冲减明细 - 查看业绩冲减明细")
def deduction():
    """冲减明细"""
    if not cli_instance.trial_results:
        click.echo("请先进行批量试算 (命令: trial)")
        return
    cli_instance.show_trial_details()


@main.command(help="凭证生成 - 生成退款凭证号")
def voucher():
    """凭证生成"""
    if not cli_instance.confirmed:
        if not cli_instance.trial_results:
            click.echo("请先进行批量试算 (命令: trial)")
            return
        if not cli_instance.check_all_exceptions_handled():
            click.echo(f"{Fore.RED}请先使用 handle-exceptions 命令处理完全部异常{Style.RESET_ALL}")
            return
        if not cli_instance.confirm_results():
            return
    if cli_instance.confirmed:
        cli_instance.generate_vouchers()


@main.command(help="导出结果 - 导出所有报表文件(支持空数据)")
def export():
    """导出结果"""
    if not cli_instance.processor:
        if not cli_instance.trial_results:
            click.echo("请先完成核算流程")
            return
        if not cli_instance.confirmed:
            if not click.confirm("结果尚未确认，仍要导出吗？", default=False):
                return
        else:
            cli_instance.generate_vouchers()
    cli_instance.export_results()


@main.command(help="日志回看 - 查看历史操作日志")
@click.option("--lines", "-n", default=50, help="显示行数")
def logs(lines):
    """日志回看"""
    cli_instance.show_logs(lines)


@main.command(help="统计概览 - 显示当前数据统计")
def stats():
    """统计概览"""
    cli_instance.show_stats()
    cli_instance.show_status()


@main.command("clear", help="清空会话状态 - 重新开始核算")
def clear_cmd():
    """清空会话"""
    cli_instance.clear_session()


@main.command(help="一键核算 - 执行完整核算流程")
@click.option("--store", "-s", multiple=True, help="门店ID，可多次指定")
@click.option("--month", "-m", help="核算月份，格式: YYYY-MM (严格按月份过滤)")
@click.option("--auto", is_flag=True, help="自动模式 (注：有异常时仍需人工处理，否则无法进入确认环节)")
def run(store, month, auto):
    """一键核算 - 完整流程"""
    store_list = list(store) if store else None

    if auto:
        click.echo("自动模式：将自动执行导入、校验、试算，但遇到异常时仍需处理")
        if not cli_instance.importer:
            cli_instance.import_data(store_list, month)
        if not cli_instance.validator:
            cli_instance.validate()
        if not cli_instance.trial_results:
            cli_instance.trial_calculate()
        if cli_instance.trial_results:
            unhandled = len([e for e in cli_instance.exceptions if not e.get("handled")])
            if unhandled > 0:
                click.echo(f"\n{Fore.YELLOW}自动模式提示: 检测到 {unhandled} 条未处理异常，请运行 handle-exceptions 处理后再 confirm 和 export{Style.RESET_ALL}")
                click.echo(f"可分步执行: python main.py handle-exceptions → confirm → voucher → export")
            else:
                if not cli_instance.confirmed:
                    cli_instance.processor.confirm_results()
                    cli_instance.confirmed = True
                cli_instance.generate_vouchers()
                cli_instance.export_results()
                click.echo(f"\n{Fore.GREEN}[OK] 自动核算完成！{Style.RESET_ALL}")
    else:
        cli_instance.run_full_process(store_list, month)


@main.command(help="显示版本信息")
def about():
    """关于"""
    click.echo(f"""
{Fore.CYAN}╔{'='*58}╗{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}      医美退款退项批处理工具 v{__version__}              {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}╠{'='*58}╣{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}  面向连锁机构总部财务专员                          {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}  • 按核算月份严格过滤数据                        {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}  • 套餐拆分校验 + 赠品扣减试算                    {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}  • 异常必须逐条处理，留下处理意见                 {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}  • 分步命令不丢数据，会话状态自动保存             {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}  • 空数据场景也能正常导出报表                     {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}╚{'='*58}╝{Style.RESET_ALL}

建议使用流程:
  1. python main.py import-data --month 2026-06    # 导入并按月份过滤
  2. python main.py validate                         # 规则校验
  3. python main.py handle-exceptions                # 处理异常(必须)
  4. python main.py trial                            # 批量试算
  5. python main.py confirm                          # 结果确认
  6. python main.py voucher                          # 生成凭证
  7. python main.py export                           # 导出报表
    """)


if __name__ == "__main__":
    main()
