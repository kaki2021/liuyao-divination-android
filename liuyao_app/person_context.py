"""Project optional, case-bound people information as user evidence.

Age is recorded at casting in completed years. It does not select a five-element
matrix, resolve the source's age boundary, or supply facts absent from the user.
"""


def person_evidence(input_data, known_at):
    info = input_data.get("person_info")
    if not info:
        return None
    lines = ["人物信息（用户填写；年龄为起卦时周岁，不随当前日期增长）"]
    subject = info.get("subject", "unspecified")
    lines.append("所问对象：" + {"self": "自己", "other": "他人", "unspecified": "其他、多人或尚未区分"}[subject])
    if "querent_age" in info:
        lines.append(f"提问者起卦时年龄：{info['querent_age']}周岁")
        if subject == "self":
            lines.append(f"所问对象起卦时年龄：{info['querent_age']}周岁（自占，与提问者相同）")
    if "subject_age" in info:
        lines.append(f"所问对象起卦时年龄：{info['subject_age']}周岁")
    if info.get("relationship"):
        lines.append("所问对象与提问者的关系：" + info["relationship"])
    if info.get("background"):
        lines.append("本次事情相关背景：" + info["background"])
    return {"evidence_id": "USER_PERSON_INFO", "text": "\n".join(lines),
            "origin": "user_background", "known_at": known_at}
