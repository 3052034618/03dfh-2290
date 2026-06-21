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


@main.command(help="导入数据 - 导入订单、消费记录、退款申请")
@click.option("--store", "-s", multiple=True, help="门店ID，可多次指定，默认全部")
@click.option("--month", "-m", help="核算月份，格式: YYYY-MM")
def import_data(store, month):
    """导入数据"""
    store_list = list(store) if store else None
    cli_instance.import_data(store_list, month)


@main.command(help="规则校验 - 检查价格、折扣、提成等是否匹配")
def validate():
    """规则校验"""
    if not cli_instance.importer:
        cli_instance.import_data()
    cli_instance.validate()
    cli_instance.show_exceptions()


@main.command(help="异常清单 - 查看所有异常记录")
def exceptions():
    """异常清单"""
    if not cli_instance.exceptions:
        if not cli_instance.importer:
            cli_instance.import_data()
        cli_instance.validate()
    cli_instance.show_exceptions()


@main.command(help="处理异常 - 交互式处理异常记录")
def handle_exceptions():
    """处理异常"""
    if not cli_instance.exceptions:
        if not cli_instance.importer:
            cli_instance.import_data()
        cli_instance.validate()
    cli_instance.handle_exceptions_interactive()


@main.command(help="批量试算 - 计算所有退款的详细金额")
def trial():
    """批量试算"""
    if not cli_instance.validator:
        if not cli_instance.importer:
            cli_instance.import_data()
        cli_instance.validate()
    cli_instance.trial_calculate()


@main.command(help="查看试算明细")
def trial_detail():
    """查看试算明细"""
    if not cli_instance.trial_results:
        if not cli_instance.validator:
            if not cli_instance.importer:
                cli_instance.import_data()
            cli_instance.validate()
        cli_instance.trial_calculate()
    cli_instance.show_trial_details()


@main.command(help="结果确认 - 确认试算结果")
def confirm():
    """结果确认"""
    if not cli_instance.trial_results:
        click.echo("请先进行批量试算")
        return
    cli_instance.confirm_results()


@main.command(help="冲减明细 - 查看业绩冲减明细")
def deduction():
    """冲减明细"""
    if not cli_instance.trial_results:
        click.echo("请先进行批量试算")
        return
    cli_instance.show_trial_details()


@main.command(help="凭证生成 - 生成退款凭证")
def voucher():
    """凭证生成"""
    if not cli_instance.confirmed:
        if not cli_instance.trial_results:
            click.echo("请先进行批量试算")
            return
        cli_instance.confirm_results()
    if cli_instance.confirmed:
        cli_instance.generate_vouchers()


@main.command(help="导出结果 - 导出所有报表文件")
def export():
    """导出结果"""
    if not cli_instance.processor:
        click.echo("请先完成核算")
        return
    if not cli_instance.confirmed:
        cli_instance.confirm_results()
    if cli_instance.confirmed:
        cli_instance.export_results()


@main.command(help="日志回看 - 查看历史操作日志")
@click.option("--lines", "-n", default=50, help="显示行数")
def logs(lines):
    """日志回看"""
    cli_instance.show_logs(lines)


@main.command(help="统计概览 - 显示当前数据统计")
def stats():
    """统计概览"""
    if not cli_instance.importer:
        click.echo("暂无数据，请先导入")
        return
    cli_instance.show_stats()


@main.command(help="一键核算 - 执行完整核算流程")
@click.option("--store", "-s", multiple=True, help="门店ID，可多次指定")
@click.option("--month", "-m", help="核算月份，格式: YYYY-MM")
@click.option("--auto", is_flag=True, help="自动模式，跳过确认步骤")
def run(store, month, auto):
    """一键核算 - 完整流程"""
    store_list = list(store) if store else None

    if auto:
        click.echo("自动模式执行中...")
        cli_instance.import_data(store_list, month)
        cli_instance.validate()
        cli_instance.trial_calculate()
        if cli_instance.trial_results:
            cli_instance.processor.confirm_results()
            cli_instance.confirmed = True
            cli_instance.generate_vouchers()
            cli_instance.export_results()
            click.echo(f"\n{Fore.GREEN}✓ 自动核算完成！{Style.RESET_ALL}")
    else:
        cli_instance.run_full_process(store_list, month)


@main.command(help="显示版本信息")
def about():
    """关于"""
    click.echo(f"""
{Fore.CYAN}╔{'='*50}╗{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}      医美退款退项批处理工具 v{__version__}        {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}╠{'='*50}╣{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}  面向连锁机构总部财务专员                 {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}  支持多门店、批量核算、规则校验           {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}║{Style.RESET_ALL}  输出退款核算表、业绩冲减表、待复核名单   {Fore.CYAN}║{Style.RESET_ALL}
{Fore.CYAN}╚{'='*50}╝{Style.RESET_ALL}
    """)


if __name__ == "__main__":
    main()
