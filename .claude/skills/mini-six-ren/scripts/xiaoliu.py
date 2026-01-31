# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "lunardate>=0.2.0",
# ]
# ///
"""小六壬占卜核心算法 - Mini Six Ren Divination Engine

Usage:
    uv run scripts/xiaoliu.py --numbers 1,2,3
    uv run scripts/xiaoliu.py --datetime "2025-01-31 14:30"
    uv run scripts/xiaoliu.py --chars "天地人"
    uv run scripts/xiaoliu.py --now
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ===== 九宫格符号数据（内置） =====
SYMBOLS_DATA = [
    {
        "name": "大安",
        "element": "木",
        "description": "长期、缓慢、稳定",
        "interpretation": "求安稳，大安最吉；求变化，大安不吉",
        "direction": "正东",
        "deity": "三清",
        "order": 1,
    },
    {
        "name": "留连",
        "element": "木",
        "description": "停止、反复、复杂",
        "interpretation": "想挽留，留连是吉；否则不吉",
        "direction": "东南",
        "deity": "文昌",
        "order": 2,
    },
    {
        "name": "速喜",
        "element": "火",
        "description": "惊喜、快速、突然",
        "interpretation": "意想不到的好事！如需稳定，则可能是惊吓",
        "direction": "正南",
        "deity": "雷祖",
        "order": 3,
    },
    {
        "name": "赤口",
        "element": "金",
        "description": "争斗、凶恶、伤害",
        "interpretation": "最凶最恶，吵架、打架、斗争、官司、肉体受伤",
        "direction": "正西",
        "deity": "将帅",
        "order": 4,
    },
    {
        "name": "小吉",
        "element": "水",
        "description": "起步、不多、尚可",
        "interpretation": "不完美，成中有缺，适合起步，碰上小吉都有阻碍",
        "direction": "正北",
        "deity": "真武",
        "order": 5,
    },
    {
        "name": "空亡",
        "element": "土",
        "description": "失去、虚伪、空想",
        "interpretation": "先得再失，尤忌金钱事。现实之事遇空亡很差，虚幻之事遇空亡很好",
        "direction": "中间",
        "deity": "玉皇",
        "order": 6,
    },
    {
        "name": "病符",
        "element": "土",
        "description": "病态、异常、治疗",
        "interpretation": "病态+治疗=病符，先有病才需治疗，过程不好受",
        "direction": "西南",
        "deity": "后土",
        "order": 7,
    },
    {
        "name": "桃花",
        "element": "土",
        "description": "欲望、牵绊、异性",
        "interpretation": "人际关系，往往和欲望、异性有关。除谈恋爱外，桃花都是不好的",
        "direction": "东北",
        "deity": "城隍",
        "order": 8,
    },
    {
        "name": "天德",
        "element": "金",
        "description": "贵人、长辈、上司老板、高远",
        "interpretation": "求人办事，靠人成事！让贵人来帮你",
        "direction": "西北",
        "deity": "紫薇",
        "order": 9,
    },
]

# ===== 五行生克关系 =====
WUXING_GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
WUXING_OVERCOMES = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def get_relation(e1: str, e2: str) -> str:
    """判断两个五行元素之间的关系"""
    if WUXING_GENERATES.get(e1) == e2:
        return "生"
    elif WUXING_OVERCOMES.get(e1) == e2:
        return "克"
    elif WUXING_GENERATES.get(e2) == e1:
        return "被生"
    elif WUXING_OVERCOMES.get(e2) == e1:
        return "被克"
    elif e1 == e2:
        return "同"
    else:
        return "无"


def calculate_symbol(start_position: int, steps: int) -> dict:
    """计算符号位置：从start_position开始，走steps步"""
    normalized = steps % 9
    if normalized == 0:
        normalized = 9
    end_position = (start_position + normalized - 1) % 9
    return SYMBOLS_DATA[end_position]


def generate_prediction(num1: int, num2: int, num3: int) -> dict:
    """核心算法：根据三个数字生成三传占卜结果"""
    first = calculate_symbol(0, num1)
    second = calculate_symbol((num1 - 1) % 9, num2)
    third = calculate_symbol((num1 + num2 - 2) % 9, num3)

    r1 = get_relation(first["element"], second["element"])
    r2 = get_relation(second["element"], third["element"])

    return {
        "input_numbers": [num1, num2, num3],
        "passes": [
            {"position": "初传（前期）", "symbol": first, "index": 0},
            {"position": "中传（中期）", "symbol": second, "index": 1},
            {"position": "末传（后期）", "symbol": third, "index": 2},
        ],
        "relations": [
            {
                "from": first["name"],
                "to": second["name"],
                "from_element": first["element"],
                "to_element": second["element"],
                "relation": r1,
            },
            {
                "from": second["name"],
                "to": third["name"],
                "from_element": second["element"],
                "to_element": third["element"],
                "relation": r2,
            },
        ],
    }


# ===== 常用汉字笔画表（常用字） =====
COMMON_STROKES = {
    "一": 1, "二": 2, "三": 3, "四": 5, "五": 4, "六": 4, "七": 2, "八": 2, "九": 2, "十": 2,
    "天": 4, "地": 6, "人": 2, "大": 3, "小": 3, "中": 4, "上": 3, "下": 3, "左": 5, "右": 5,
    "日": 4, "月": 4, "水": 4, "火": 4, "木": 4, "金": 8, "土": 3, "山": 3, "石": 5, "田": 5,
    "风": 4, "云": 4, "雨": 8, "雪": 11, "花": 8, "草": 9, "树": 9, "竹": 6, "鸟": 5, "鱼": 8,
    "马": 3, "牛": 4, "羊": 6, "猪": 11, "狗": 8, "猫": 11, "龙": 5, "虎": 8, "兔": 8, "蛇": 11,
    "猴": 12, "鸡": 7, "心": 4, "手": 4, "口": 3, "目": 5, "耳": 6, "足": 7, "头": 5, "身": 7,
    "男": 7, "女": 3, "父": 4, "母": 5, "子": 3, "孙": 6, "王": 4, "李": 7, "张": 7, "刘": 6,
    "陈": 7, "杨": 7, "黄": 11, "赵": 9, "吴": 7, "周": 8, "徐": 10, "孙": 6, "朱": 6, "林": 8,
    "东": 5, "南": 9, "西": 6, "北": 5, "春": 9, "夏": 10, "秋": 9, "冬": 5,
    "爱": 10, "福": 13, "财": 7, "喜": 12, "乐": 5, "安": 6, "平": 5, "和": 8, "美": 9, "好": 6,
    "家": 10, "国": 8, "学": 8, "生": 5, "工": 3, "业": 5, "事": 8, "情": 11, "道": 12, "理": 11,
    "明": 8, "白": 5, "红": 6, "蓝": 13, "绿": 11, "黑": 12, "青": 8, "紫": 12,
    "前": 9, "后": 6, "来": 7, "去": 5, "出": 5, "入": 2, "开": 4, "关": 6, "有": 6, "无": 4,
    "长": 4, "短": 12, "高": 10, "低": 7, "新": 13, "旧": 5, "老": 6, "少": 4, "多": 6, "吉": 6,
    "凶": 4, "运": 7, "命": 8, "星": 9, "辰": 7, "阳": 6, "阴": 6, "乾": 11, "坤": 8,
}


def get_stroke_count(char: str) -> int:
    """获取单个汉字笔画数"""
    if char in COMMON_STROKES:
        return COMMON_STROKES[char]
    # 对于不在表中的字，使用Unicode编码取模作为近似值
    return (ord(char) % 20) + 1


def chars_to_numbers(chars: str) -> list[int]:
    """将汉字转换为笔画数列表（取前三个字）"""
    chars = chars[:3]
    return [get_stroke_count(c) for c in chars if "\u4e00" <= c <= "\u9fff"]


def datetime_to_numbers(dt: datetime) -> list[int]:
    """将日期时间转换为三个数字（月、日、时辰）"""
    try:
        from lunardate import LunarDate

        lunar = LunarDate.fromSolarDate(dt.year, dt.month, dt.day)
        lunar_month = lunar.month
        lunar_day = lunar.day
    except Exception:
        lunar_month = dt.month
        lunar_day = dt.day

    # 时辰：0-1点=子时(1), 1-3点=丑时(2), ... 23-0点=子时(1)
    hour_branch = ((dt.hour + 1) // 2) % 12 + 1

    return [lunar_month, lunar_day, hour_branch]


def format_text_output(result: dict, question: Optional[str] = None) -> str:
    """格式化为文本输出"""
    lines = []
    lines.append("=" * 50)
    lines.append("        小六壬三传占卜结果")
    lines.append("=" * 50)
    lines.append(f"输入数字: {result['input_numbers']}")
    if question:
        lines.append(f"求问事项: {question}")
    lines.append("-" * 50)

    for p in result["passes"]:
        s = p["symbol"]
        lines.append(f"\n  {p['position']}:")
        lines.append(f"    符号: 【{s['name']}】")
        lines.append(f"    五行: {s['element']}")
        lines.append(f"    含义: {s['description']}")
        lines.append(f"    解释: {s['interpretation']}")
        lines.append(f"    方位: {s['direction']}")
        lines.append(f"    神灵: {s['deity']}")

    lines.append("\n" + "-" * 50)
    lines.append("五行生克关系:")
    for r in result["relations"]:
        arrow = f"{r['from']}({r['from_element']}) —{r['relation']}→ {r['to']}({r['to_element']})"
        lines.append(f"  {arrow}")

    lines.append("=" * 50)
    return "\n".join(lines)


def format_json_output(result: dict, question: Optional[str] = None) -> str:
    """格式化为JSON输出"""
    output = {**result}
    if question:
        output["question"] = question
    return json.dumps(output, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="小六壬占卜 - Mini Six Ren Divination")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--numbers", "-n", help="三个数字，逗号分隔 (例: 1,2,3)")
    group.add_argument("--datetime", "-d", help="日期时间 (例: 2025-01-31 14:30)")
    group.add_argument("--chars", "-c", help="三个汉字 (例: 天地人)")
    group.add_argument("--now", action="store_true", help="使用当前时间占卜")
    parser.add_argument("--question", "-q", help="求问事项")
    parser.add_argument("--format", "-f", choices=["text", "json"], default="text", help="输出格式")

    args = parser.parse_args()

    # 解析输入为三个数字
    if args.numbers:
        parts = args.numbers.split(",")
        if len(parts) != 3:
            print("错误: 请输入恰好3个数字，逗号分隔", file=sys.stderr)
            sys.exit(1)
        nums = [int(p.strip()) for p in parts]
    elif args.datetime:
        dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M")
        nums = datetime_to_numbers(dt)
    elif args.chars:
        nums = chars_to_numbers(args.chars)
        if len(nums) < 3:
            print("错误: 请输入至少3个汉字", file=sys.stderr)
            sys.exit(1)
        nums = nums[:3]
    elif args.now:
        dt = datetime.now()
        nums = datetime_to_numbers(dt)
    else:
        parser.print_help()
        sys.exit(1)

    result = generate_prediction(nums[0], nums[1], nums[2])

    if args.format == "json":
        print(format_json_output(result, args.question))
    else:
        print(format_text_output(result, args.question))


if __name__ == "__main__":
    main()
