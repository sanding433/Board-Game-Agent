def system_prompt(language: str = "zh") -> str:
    if language == "zh":
        return "你是桌游顾问系统中的一个专业 agent。请用中文思考；需要结构化输出时只返回合法 JSON。"
    return "You are an agent in a board-game advisor system. When asked for JSON, return valid JSON only."
