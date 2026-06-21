# 医美退款退项批处理工具

面向连锁机构总部财务专员，在月底集中核对多门店退项数据时使用的命令行批处理工具。

## 功能概览

### 10个核心功能

1. **导入订单文件** - 批量导入各门店订单数据
2. **导入消费记录** - 导入消费/划扣记录
3. **导入退款申请** - 导入退款/退项申请单
4. **规则校验** - 逐笔检查原价、折扣、套餐拆分、医生划扣、咨询师提成、赠品扣减
5. **异常清单** - 列出所有异常情况（超消费、超额退款等）
6. **批量试算** - 快速计算退款金额、提成扣减、赠品扣减
7. **结果确认** - 人工确认核算结果
8. **冲减明细** - 生成业绩冲减明细
9. **凭证生成** - 自动生成退款凭证号
10. **日志回看** - 历史操作日志查询

### 5个承载单元

1. **命令** - 完整的命令行操作接口
2. **配置向导** - 交互式参数设置
3. **结果表** - 退款核算表、业绩冲减表
4. **异常报告** - 异常清单、待复核名单
5. **确认清单** - 结果确认流程

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 生成示例数据（测试用）

```bash
python generate_sample_data.py
```

### 一键自动核算

```bash
python main.py run --auto
```

### 交互式完整流程

```bash
python main.py run
```

## 命令详解

### 1. 配置向导

```bash
python main.py config
```

交互式设置以下参数：
- 数据输入目录
- 结果输出目录
- 日志目录
- 医生提成比例
- 咨询师提成比例
- 凭证号前缀

### 2. 导入数据

```bash
# 导入全部门店数据
python main.py import-data

# 指定门店
python main.py import-data --store S001 --store S002

# 指定月份
python main.py import-data --month 2024-06
```

### 3. 规则校验

```bash
python main.py validate
```

校验规则：
- 已消费次数 > 购买次数 → 异常
- 退款金额 > 剩余价值 → 异常
- 实付单价 ≠ 原价 × 折扣 → 异常
- 医生提成 ≠ 消费金额 × 提成比例 → 异常
- 咨询师提成 ≠ 消费金额 × 提成比例 → 异常
- 套餐项目拆分不均 → 异常

### 4. 查看异常清单

```bash
python main.py exceptions
```

显示所有异常记录，包括：
- 关联单号
- 异常类型
- 异常描述
- 所属门店
- 处理状态

### 5. 交互式处理异常

```bash
python main.py handle-exceptions
```

逐条处理异常，支持：
- [1] 跳过
- [2] 标记为已处理
- [3] 输入处理意见

### 6. 批量试算

```bash
python main.py trial
```

试算结果包括：
- 应退总金额
- 医生提成扣减
- 咨询师提成扣减
- 赠品扣减
- 实退总金额
- 按门店汇总

### 7. 查看试算明细

```bash
python main.py trial-detail
```

### 8. 结果确认

```bash
python main.py confirm
```

人工确认试算结果，确认后可生成凭证和导出。

### 9. 凭证生成

```bash
python main.py voucher
```

自动生成连续编号的退款凭证，格式如：TK000001、TK000002...

### 10. 导出结果

```bash
python main.py export
```

导出4个Excel文件：
- **退款核算表** - 退款详细信息
- **业绩冲减表** - 含明细 sheet、按门店汇总、按项目汇总
- **待复核名单** - 需要人工复核的异常记录
- **异常报告** - 所有异常明细及汇总

### 11. 日志回看

```bash
# 查看最近50行
python main.py logs

# 查看最近100行
python main.py logs --lines 100
```

### 12. 统计概览

```bash
python main.py stats
```

### 13. 版本信息

```bash
python main.py about
```

## 数据文件格式

### 订单文件（支持 .xlsx / .csv）

必填字段：
- 订单号
- 门店ID / 门店名称
- 客户ID / 客户姓名
- 项目ID / 项目名称
- 原价
- 实付单价
- 购买数量
- 购买日期
- 咨询师ID / 咨询师姓名

可选字段：
- 折扣率
- 项目类型
- 是否套餐
- 备注

### 消费记录文件

必填字段：
- 记录ID
- 订单号
- 门店ID / 门店名称
- 客户ID / 客户姓名
- 项目ID / 项目名称
- 消费数量
- 消费金额
- 消费日期
- 医生ID / 医生姓名
- 咨询师ID / 咨询师姓名

可选字段：
- 医生提成
- 咨询师提成
- 备注

### 退款申请文件

必填字段：
- 退款单号
- 订单号
- 门店ID / 门店名称
- 客户ID / 客户姓名
- 项目ID / 项目名称
- 退款数量
- 退款金额
- 退款原因
- 申请日期
- 申请人

可选字段：
- 状态
- 处理意见

> 提示：字段名称支持中英文多种写法，工具会自动识别匹配。

## 目录结构

```
.
├── main.py                  # 主入口
├── config.yaml              # 配置文件
├── requirements.txt         # 依赖列表
├── generate_sample_data.py  # 示例数据生成脚本
├── refund_tool/             # 核心模块
│   ├── __init__.py
│   ├── models.py            # 数据模型
│   ├── config.py            # 配置管理
│   ├── utils.py             # 工具函数
│   ├── logger.py            # 日志管理
│   ├── importer.py          # 数据导入
│   ├── validator.py         # 规则校验引擎
│   ├── processor.py         # 结果处理
│   └── cli.py               # 命令行界面
└── data/
    ├── input/               # 输入数据目录
    ├── output/              # 输出结果目录
    └── logs/                # 日志目录
```

## 配置说明

`config.yaml` 配置项：

```yaml
default_store: all           # 默认门店范围
default_month: current       # 默认月份

input_dir: ./data/input      # 输入目录
output_dir: ./data/output    # 输出目录
log_dir: ./data/logs         # 日志目录

validation_rules:            # 校验规则
  allow_consume_exceed_purchase: false    # 允许超消费
  allow_refund_exceed_remaining: false    # 允许超额退款
  check_package_split: true               # 检查套餐拆分
  check_doctor_commission: true           # 检查医生提成
  check_consultant_commission: true       # 检查咨询师提成
  check_gift_deduction: true              # 检查赠品扣减

commission_rules:            # 提成规则
  doctor_commission_rate: 0.15           # 医生提成比例
  consultant_commission_rate: 0.1        # 咨询师提成比例
  package_split_method: average          # 套餐拆分方式

voucher:                     # 凭证配置
  prefix: TK                 # 凭证号前缀
  digit_length: 6            # 数字位数
  start_number: 1            # 起始编号
```

## 使用场景

### 场景一：月底批量核算

1. 财务收集各门店导出的订单、消费记录、退款申请Excel
2. 将文件放入 `data/input/` 目录
3. 运行 `python main.py run --auto`
4. 查看 `data/output/` 目录下的核算结果

### 场景二：人工逐笔复核

1. 运行 `python main.py run`
2. 工具自动导入数据、校验规则
3. 查看异常清单，交互式处理每条异常
4. 查看试算结果，人工确认
5. 确认后生成凭证、导出报表

## 技术栈

- Python 3.8+
- click - 命令行框架
- pandas - 数据处理
- openpyxl - Excel读写
- PyYAML - 配置管理
- colorama - 终端彩色输出
- tabulate - 表格输出

## 许可证

内部工具，仅限授权使用。
