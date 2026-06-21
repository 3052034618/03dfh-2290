"""生成示例数据文件"""

import os
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
        ("I004", "光子嫩肤", "疗程", 5800, 0.75),
        ("I005", "双眼皮手术", "手术", 8800, 0.85),
        ("I006", "瘦脸针", "单次", 2800, 0.9),
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
    base_date = today - timedelta(days=90)

    orders_data = []
    order_id = 1
    for store_id, store_name in stores:
        for i in range(8):
            item_id, item_name, item_type, original_price, discount = random.choice(items)
            customer_id, customer_name = random.choice(customers)
            doc_id, doc_name = random.choice(doctors)
            cons_id, cons_name = random.choice(consultants)
            quantity = random.choice([1, 1, 2, 3, 5])
            purchase_date = base_date + timedelta(days=random.randint(0, 60))

            actual_price = round(original_price * discount, 2)

            orders_data.append({
                "订单号": f"ORD{order_id:06d}",
                "门店ID": store_id,
                "门店名称": store_name,
                "客户ID": customer_id,
                "客户姓名": customer_name,
                "项目ID": item_id,
                "项目名称": item_name,
                "项目类型": item_type,
                "原价": original_price,
                "折扣率": discount,
                "实付单价": actual_price,
                "购买数量": quantity,
                "购买日期": purchase_date.strftime("%Y-%m-%d"),
                "咨询师ID": cons_id,
                "咨询师姓名": cons_name,
                "是否套餐": 0,
                "备注": "",
            })
            order_id += 1

    df_orders = pd.DataFrame(orders_data)
    orders_file = os.path.join(output_dir, "订单汇总.xlsx")
    df_orders.to_excel(orders_file, index=False)

    consumption_data = []
    record_id = 1
    for order in orders_data:
        qty_purchased = order["购买数量"]
        qty_consumed = min(random.randint(0, qty_purchased + 1), qty_purchased + 1)
        if qty_consumed <= 0:
            continue

        doc_id, doc_name = random.choice(doctors)
        cons_id, cons_name = random.choice(consultants)
        consume_date = datetime.strptime(order["购买日期"], "%Y-%m-%d") + timedelta(days=random.randint(1, 30))

        for _ in range(qty_consumed):
            consume_date_single = consume_date + timedelta(days=random.randint(0, 10))
            consume_amount = order["实付单价"]

            doctor_commission = round(consume_amount * 0.15, 2)
            consultant_commission = round(consume_amount * 0.1, 2)

            consumption_data.append({
                "记录ID": f"REC{record_id:06d}",
                "订单号": order["订单号"],
                "门店ID": order["门店ID"],
                "门店名称": order["门店名称"],
                "客户ID": order["客户ID"],
                "客户姓名": order["客户姓名"],
                "项目ID": order["项目ID"],
                "项目名称": order["项目名称"],
                "消费数量": 1,
                "消费金额": consume_amount,
                "消费日期": consume_date_single.strftime("%Y-%m-%d"),
                "医生ID": doc_id,
                "医生姓名": doc_name,
                "咨询师ID": cons_id,
                "咨询师姓名": cons_name,
                "医生提成": doctor_commission,
                "咨询师提成": consultant_commission,
                "备注": "",
            })
            record_id += 1

    df_consumptions = pd.DataFrame(consumption_data)
    consumptions_file = os.path.join(output_dir, "消费记录.xlsx")
    df_consumptions.to_excel(consumptions_file, index=False)

    refund_data = []
    refund_id = 1
    refundable_orders = random.sample(orders_data, min(8, len(orders_data)))
    for order in refundable_orders:
        order_id = order["订单号"]
        qty_purchased = order["购买数量"]

        order_consumptions = [r for r in consumption_data if r["订单号"] == order_id]
        total_consumed = sum(r["消费数量"] for r in order_consumptions)
        remaining = max(qty_purchased - total_consumed, 0)

        if remaining <= 0:
            continue

        refund_qty = min(random.randint(1, max(remaining + 1, 1)), remaining + 1)
        refund_amount = round(refund_qty * order["实付单价"], 2)

        apply_date = consume_date + timedelta(days=random.randint(5, 20))

        reasons = ["客户个人原因", "效果不满意", "时间安排冲突", "皮肤过敏", "更换项目"]

        refund_data.append({
            "退款单号": f"RF{refund_id:06d}",
            "订单号": order_id,
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

    print(f"生成示例数据文件:")
    print(f"  订单文件: {orders_file} ({len(orders_data)}条)")
    print(f"  消费记录: {consumptions_file} ({len(consumption_data)}条)")
    print(f"  退款申请: {refunds_file} ({len(refund_data)}条)")

    return orders_file, consumptions_file, refunds_file


if __name__ == "__main__":
    generate_sample_data()
