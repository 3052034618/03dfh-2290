"""生成示例数据文件 - 包含套餐和赠品"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import random


def generate_sample_data(output_dir: str = "./data/input"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    stores = [
        ("S001", "北京朝阳店"),
        ("S002", "上海浦东店"),
        ("S003", "广州天河店"),
    ]

    items = [
        ("I001", "水光针", "单次", 980, 0.85),
        ("I002", "热玛吉", "单次", 12800, 0.9),
        ("I003", "玻尿酸填充", "单次", 3800, 0.8),
        ("I004", "光子嫩肤疗程", "疗程", 5800, 0.75),
        ("I005", "双眼皮手术", "手术", 8800, 0.85),
        ("I006", "瘦脸针", "单次", 2800, 0.9),
    ]

    package_defs = [
        {
            "id": "P001",
            "name": "抗衰紧致套餐",
            "type": "套餐",
            "original_price": 25800,
            "discount": 0.78,
            "package_items": [
                {"name": "热玛吉", "price": 12800, "quantity": 1},
                {"name": "水光针", "price": 980, "quantity": 3},
                {"name": "光子嫩肤", "price": 1500, "quantity": 3},
            ],
            "gifts": [
                {"name": "修复面膜", "price": 380, "quantity": 1},
                {"name": "精华液", "price": 580, "quantity": 1},
            ],
        },
        {
            "id": "P002",
            "name": "面部焕新套餐",
            "type": "套餐",
            "original_price": 12800,
            "discount": 0.82,
            "package_items": [
                {"name": "玻尿酸填充", "price": 3800, "quantity": 2},
                {"name": "瘦脸针", "price": 2800, "quantity": 1},
            ],
            "gifts": [
                {"name": "导入护理", "price": 680, "quantity": 1},
            ],
        },
    ]

    doctors = [
        ("D001", "张医生"),
        ("D002", "李医生"),
        ("D003", "王医生"),
    ]

    consultants = [
        ("C001", "刘咨询师"),
        ("C002", "陈咨询师"),
        ("C003", "周咨询师"),
    ]

    customers = [
        ("CU001", "张小美"),
        ("CU002", "李婷婷"),
        ("CU003", "王芳芳"),
        ("CU004", "赵丽丽"),
        ("CU005", "孙倩倩"),
        ("CU006", "周晶晶"),
        ("CU007", "吴莹莹"),
        ("CU008", "郑思思"),
    ]

    today = datetime.now()
    current_month_start = datetime(today.year, today.month, 1)

    orders_data = []
    order_id = 1
    consumption_data = []
    record_id = 1

    for store_idx, (store_id, store_name) in enumerate(stores):
        for i in range(6):
            item = random.choice(items)
            customer = random.choice(customers)
            doc = random.choice(doctors)
            cons = random.choice(consultants)
            quantity = random.choice([1, 1, 2, 3, 5])

            purchase_date = current_month_start + timedelta(days=random.randint(0, min(today.day - 1, 20)))

            item_id, item_name, item_type, original_price, discount = item
            actual_price = round(original_price * discount, 2)

            order = {
                "订单号": f"ORD{order_id:06d}",
                "门店ID": store_id,
                "门店名称": store_name,
                "客户ID": customer[0],
                "客户姓名": customer[1],
                "项目ID": item_id,
                "项目名称": item_name,
                "项目类型": item_type,
                "原价": original_price,
                "折扣率": discount,
                "实付单价": actual_price,
                "购买数量": quantity,
                "购买日期": purchase_date.strftime("%Y-%m-%d"),
                "咨询师ID": cons[0],
                "咨询师姓名": cons[1],
                "是否套餐": 0,
                "套餐明细": "",
                "赠品信息": "",
                "备注": "",
            }
            orders_data.append(order)

            qty_consumed = random.randint(0, min(quantity + random.choice([0, 1, 1, 2]), quantity + 2))
            for _ in range(qty_consumed):
                consume_date = purchase_date + timedelta(days=random.randint(1, min(15, (today - purchase_date).days - 1) or 1))
                if consume_date > today:
                    consume_date = today - timedelta(days=1)
                doc = random.choice(doctors)
                consume_amount = actual_price
                doc_comm = round(consume_amount * 0.15, 2)
                cons_comm = round(consume_amount * 0.1, 2)
                consumption_data.append({
                    "记录ID": f"REC{record_id:06d}",
                    "订单号": order["订单号"],
                    "门店ID": store_id,
                    "门店名称": store_name,
                    "客户ID": customer[0],
                    "客户姓名": customer[1],
                    "项目ID": item_id,
                    "项目名称": item_name,
                    "消费数量": 1,
                    "消费金额": consume_amount,
                    "消费日期": consume_date.strftime("%Y-%m-%d"),
                    "医生ID": doc[0],
                    "医生姓名": doc[1],
                    "咨询师ID": cons[0],
                    "咨询师姓名": cons[1],
                    "医生提成": doc_comm,
                    "咨询师提成": cons_comm,
                    "备注": "",
                })
                record_id += 1

            order_id += 1

        if store_idx == 0:
            for pkg in package_defs:
                customer = random.choice(customers)
                cons = random.choice(consultants)
                quantity = random.choice([1, 1, 2])
                purchase_date = current_month_start + timedelta(days=random.randint(2, 15))

                pkg_actual_price = round(pkg["original_price"] * pkg["discount"], 2)

                order = {
                    "订单号": f"ORD{order_id:06d}",
                    "门店ID": store_id,
                    "门店名称": store_name,
                    "客户ID": customer[0],
                    "客户姓名": customer[1],
                    "项目ID": pkg["id"],
                    "项目名称": pkg["name"],
                    "项目类型": pkg["type"],
                    "原价": pkg["original_price"],
                    "折扣率": pkg["discount"],
                    "实付单价": pkg_actual_price,
                    "购买数量": quantity,
                    "购买日期": purchase_date.strftime("%Y-%m-%d"),
                    "咨询师ID": cons[0],
                    "咨询师姓名": cons[1],
                    "是否套餐": 1,
                    "套餐明细": json.dumps(pkg["package_items"], ensure_ascii=False),
                    "赠品信息": json.dumps(pkg["gifts"], ensure_ascii=False),
                    "备注": f"含{len(pkg['package_items'])}项内容+{len(pkg['gifts'])}个赠品",
                }
                orders_data.append(order)

                for pi in pkg["package_items"][:1]:
                    qty_pkg_consumed = random.randint(0, min(quantity, 2))
                    for _ in range(qty_pkg_consumed):
                        consume_date = purchase_date + timedelta(days=random.randint(3, 20))
                        if consume_date > today:
                            consume_date = today - timedelta(days=1)
                        doc = random.choice(doctors)
                        per_item_amt = round(pkg_actual_price / len(pkg["package_items"]), 2)
                        doc_comm = round(per_item_amt * 0.15, 2)
                        cons_comm = round(per_item_amt * 0.1, 2)
                        consumption_data.append({
                            "记录ID": f"REC{record_id:06d}",
                            "订单号": order["订单号"],
                            "门店ID": store_id,
                            "门店名称": store_name,
                            "客户ID": customer[0],
                            "客户姓名": customer[1],
                            "项目ID": pkg["id"],
                            "项目名称": pi["name"],
                            "消费数量": 1,
                            "消费金额": per_item_amt,
                            "消费日期": consume_date.strftime("%Y-%m-%d"),
                            "医生ID": doc[0],
                            "医生姓名": doc[1],
                            "咨询师ID": cons[0],
                            "咨询师姓名": cons[1],
                            "医生提成": doc_comm,
                            "咨询师提成": cons_comm,
                            "备注": "套餐项目消费",
                        })
                        record_id += 1

                order_id += 1

    prev_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    for i in range(3):
        store_id, store_name = random.choice(stores)
        item = random.choice(items)
        customer = random.choice(customers)
        doc = random.choice(doctors)
        cons = random.choice(consultants)
        quantity = 2
        purchase_date = prev_month_start + timedelta(days=random.randint(5, 25))

        item_id, item_name, item_type, original_price, discount = item
        actual_price = round(original_price * discount, 2)

        order = {
            "订单号": f"ORD{order_id:06d}",
            "门店ID": store_id,
            "门店名称": store_name,
            "客户ID": customer[0],
            "客户姓名": customer[1],
            "项目ID": item_id,
            "项目名称": item_name + "（上月订单）",
            "项目类型": item_type,
            "原价": original_price,
            "折扣率": discount,
            "实付单价": actual_price,
            "购买数量": quantity,
            "购买日期": purchase_date.strftime("%Y-%m-%d"),
            "咨询师ID": cons[0],
            "咨询师姓名": cons[1],
            "是否套餐": 0,
            "套餐明细": "",
            "赠品信息": "",
            "备注": "跨月测试数据",
        }
        orders_data.append(order)

        for _ in range(1):
            consume_date = purchase_date + timedelta(days=5)
            doc_comm = round(actual_price * 0.15, 2)
            cons_comm = round(actual_price * 0.1, 2)
            consumption_data.append({
                "记录ID": f"REC{record_id:06d}",
                "订单号": order["订单号"],
                "门店ID": store_id,
                "门店名称": store_name,
                "客户ID": customer[0],
                "客户姓名": customer[1],
                "项目ID": item_id,
                "项目名称": item_name,
                "消费数量": 1,
                "消费金额": actual_price,
                "消费日期": consume_date.strftime("%Y-%m-%d"),
                "医生ID": doc[0],
                "医生姓名": doc[1],
                "咨询师ID": cons[0],
                "咨询师姓名": cons[1],
                "医生提成": doc_comm,
                "咨询师提成": cons_comm,
                "备注": "上月数据",
            })
            record_id += 1

        order_id += 1

    df_orders = pd.DataFrame(orders_data)
    orders_file = os.path.join(output_dir, "订单汇总.xlsx")
    df_orders.to_excel(orders_file, index=False)

    df_consumptions = pd.DataFrame(consumption_data)
    consumptions_file = os.path.join(output_dir, "消费记录.xlsx")
    df_consumptions.to_excel(consumptions_file, index=False)

    refund_data = []
    refund_id = 1
    random.seed(42)

    current_orders = [o for o in orders_data if o["购买日期"].startswith(current_month_start.strftime("%Y-%m"))]
    refund_targets = random.sample(current_orders, min(6, len(current_orders)))

    for order in refund_targets:
        qty_purchased = order["购买数量"]
        order_consumptions = [r for r in consumption_data if r["订单号"] == order["订单号"]]
        total_consumed = sum(r["消费数量"] for r in order_consumptions)
        remaining = max(qty_purchased - total_consumed, 0)

        refund_qty = max(1, remaining + random.choice([0, 0, 1, 2]))
        refund_amount = round(refund_qty * order["实付单价"], 2)

        apply_date = datetime.strptime(order["购买日期"], "%Y-%m-%d") + timedelta(days=random.randint(5, 18))
        if apply_date > today:
            apply_date = today - timedelta(days=1)

        reasons = ["客户个人原因", "效果不满意", "时间安排冲突", "皮肤过敏", "更换项目", "与预期不符"]

        refund_data.append({
            "退款单号": f"RF{refund_id:06d}",
            "订单号": order["订单号"],
            "门店ID": order["门店ID"],
            "门店名称": order["门店名称"],
            "客户ID": order["客户ID"],
            "客户姓名": order["客户姓名"],
            "项目ID": order["项目ID"],
            "项目名称": order["项目名称"],
            "退款数量": refund_qty,
            "退款金额": refund_amount,
            "退款原因": random.choice(reasons),
            "申请日期": apply_date.strftime("%Y-%m-%d"),
            "申请人": "前台",
            "状态": "待处理",
            "处理意见": "",
        })
        refund_id += 1

    df_refunds = pd.DataFrame(refund_data)
    refunds_file = os.path.join(output_dir, "退款申请.xlsx")
    df_refunds.to_excel(refunds_file, index=False)

    current_month_str = current_month_start.strftime("%Y-%m")
    current_month_orders = len([o for o in orders_data if o["购买日期"].startswith(current_month_str)])
    current_month_cons = len([r for r in consumption_data if r["消费日期"].startswith(current_month_str)])
    current_month_refs = len([r for r in refund_data if r["申请日期"].startswith(current_month_str)])

    print(f"生成示例数据文件 (当前月份: {current_month_str}):")
    print(f"  订单文件: {orders_file}")
    print(f"    - 总订单数: {len(orders_data)} 条")
    print(f"    - 当月订单数: {current_month_orders} 条 (跨月过滤后)")
    print(f"    - 包含套餐: {len([o for o in orders_data if o['是否套餐']==1])} 个")
    print(f"    - 包含赠品: {len([o for o in orders_data if o['赠品信息']])} 个订单")
    print(f"  消费记录: {consumptions_file}")
    print(f"    - 总记录数: {len(consumption_data)} 条")
    print(f"    - 当月记录数: {current_month_cons} 条")
    print(f"  退款申请: {refunds_file}")
    print(f"    - 总申请数: {len(refund_data)} 条")
    print(f"    - 当月申请数: {current_month_refs} 条")
    print(f"\n提示: 使用 --month {current_month_str} 可仅处理当月数据")

    return orders_file, consumptions_file, refunds_file


if __name__ == "__main__":
    generate_sample_data()
