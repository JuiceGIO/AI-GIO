"""差旅标准规则表（Day10：配置化——改规则不动代码）"""

# 城市分级：一线 / 新一线（其余归「其他」）
CITY_LEVELS = {
    "一线": ["北京", "上海", "广州", "深圳"],
    "新一线": [
        "成都", "杭州", "重庆", "武汉", "西安", "苏州", "天津",
        "南京", "郑州", "长沙", "沈阳", "青岛", "宁波", "东莞", "无锡",
    ],
}

# 差标规则（单位：元；示例配置，按公司政策修改这里即可）
STANDARDS = {
    "hotel_daily": {"一线": 500, "新一线": 400, "其他": 300},  # 住宿每日上限
    "meal_daily": 100,                                        # 每日餐补上限
    "traffic_single": 2000,                                   # 单程交通上限（高铁二等座/机票经济舱，示例值）
}


def city_level(city: str) -> str:
    """城市 -> 档位（一线/新一线/其他）"""
    for level, cities in CITY_LEVELS.items():
        if city in cities:
            return level
    return "其他"


def check_expense(form: dict) -> dict:
    """校验报销单，返回 {"ok": bool, "messages": [提示...]}"""
    messages = []
    ftype = form["type"]
    amount = form["amount"]

    if ftype == "住宿":
        level = city_level(form["city"])
        limit = STANDARDS["hotel_daily"][level]
        if amount > limit:
            messages.append(
                f"住宿费 {amount:.2f} 元超出{form['city']}（{level}）标准 {limit:.2f} 元，"
                f"超 {amount - limit:.2f} 元"
            )
    elif ftype == "交通":
        limit = STANDARDS["traffic_single"]
        if amount > limit:
            messages.append(
                f"交通费 {amount:.2f} 元超出单程上限 {limit:.2f} 元，超 {amount - limit:.2f} 元"
            )
    elif ftype == "餐饮":
        limit = STANDARDS["meal_daily"]
        if amount > limit:
            messages.append(
                f"餐费 {amount:.2f} 元超出每日上限 {limit:.2f} 元，超 {amount - limit:.2f} 元"
            )

    return {"ok": not messages, "messages": messages}