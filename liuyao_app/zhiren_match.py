"""知人首版可解释的本地规则匹配：不调用模型、不发送消息。"""
from .zhiren_store import text

TOPICS = {
    "户外": ("户外", "露营", "徒步", "爬山", "登山", "烧烤", "旅行", "出游"),
    "摄影": ("摄影", "拍照", "照片", "摄像"),
    "美食": ("美食", "餐厅", "饭店", "聚餐", "火锅", "川菜"),
    "AI": ("ai", "人工智能", "agent", "智能体", "大模型", "rag"),
    "技术": ("编程", "程序员", "开发", "软件", "测试", "技术"),
    "设计": ("设计", "平面", "美术", "视觉", "ui"),
    "运营": ("运营", "市场", "营销", "短视频"),
}

def matches(query, people):
    request = text(query, "需求", 1000, True).casefold()
    requested_topics = [topic for topic, words in TOPICS.items()
                        if any(word in request for word in words)]
    ranked = []
    for person in people:
        reasons = []
        tags = " ".join(person.get(k, "") if isinstance(person.get(k), str)
                        else " ".join(person.get(k) or [])
                        for k in ("industry", "occupation", "city", "skills", "interests", "needs")).casefold()
        for topic in requested_topics:
            if any(word in tags for word in TOPICS[topic]):
                reasons.append("人物资料涉及" + topic)
        for field in ("city", "industry", "occupation"):
            value = (person.get(field) or "").strip()
            if len(value) >= 2 and value.casefold() in request:
                reasons.append({"city": "位于", "industry": "行业", "occupation": "职业"}[field] + "：" + value)
        for key in ("skills", "interests", "needs"):
            for value in person.get(key, []):
                if len(value) >= 2 and value.casefold() in request:
                    reasons.append({"skills": "技能", "interests": "兴趣", "needs": "需求"}[key] + "：" + value)
        reasons = list(dict.fromkeys(reasons))
        if reasons:
            ranked.append(dict(person_id=person["person_id"], name=person["name"],
                               reasons=reasons, evidence_count=len(reasons)))
    ranked.sort(key=lambda x: (-x["evidence_count"], x["name"]))
    return {"matches": ranked, "method": "offline_keyword_rules",
            "note": "仅根据已保存资料提供候选人，不推断对方意愿或当前是否有空。"}
