"""Small, auditable intent and input extraction for the conversation entry.

Only the user's words supply proposed facts. Inferred inputs are editable UI
defaults; physical casting results and GPS coordinates are never fabricated.
"""
import re

MODES = ('auto', 'liuyao', 'knowledge', 'feedback')
HOUSING = r'卜宅|风水|选房|择地|买房|租房|房子|房屋|[这那]套房|[A-Za-z0-9一二三四五六七八九十]+号?房|阳宅|阴宅|墓地|坟地|祖坟'
NEW_CAST = r'(?:起|摇|占|卜)(?:一|个|一支|一次|一個|的|过的)?卦|算一卦|六爻占问|卜宅'
NEGATED_CAST = r'不(?:要|用|想|是|必)(?:再|重新)?(?:起|摇|占|卜)卦|不(?:要|是)卜宅'


def casting_defaults(text, previous=None):
    previous = previous or {}
    result = {'question': previous.get('question') or text[:2000],
              'time_policy': previous.get('time_policy', 'current'),
              'person': dict(previous.get('person', {})),
              'buzhai': dict(previous['buzhai']) if previous.get('buzhai') else None,
              'inferred': dict(previous.get('inferred', {}))}
    if re.search(r'不知道.{0,8}(?:起卦)?时间|起卦时间不(?:知道|详|清楚)', text):
        result['time_policy'] = 'unknown'
    elif re.search(r'补录|(?:昨天|前天|昨晚|上周|之前|过去|当时).{0,12}(?:起|摇|占).{0,3}卦', text):
        result['time_policy'] = 'historical'
    if re.search(r'现在(?:重新)?起卦|此刻起卦', text):
        result['time_policy'] = 'current'
    if re.search(r'不是卜宅|不要卜宅|不问房子', text):
        result['buzhai'] = None
        result['inferred'] = {k: v for k, v in result['inferred'].items() if not k.startswith('buzhai.')}
        return result
    def put(field, value, evidence):
        result['buzhai'][field] = value
        result['inferred']['buzhai.' + field] = evidence[:160]
    # Later explicit corrections take precedence over earlier statements.
    positive = re.split(r'不是[^，。；,;]{0,30}[，,](?:而是|是)', text)[-1]
    if re.search(HOUSING, text) or result['buzhai'] is not None:
        if result['buzhai'] is None:
            result['buzhai'] = {'stage': 'site_choice', 'site_kind': 'yang', 'role': 'other',
                                 'residence': 'unknown', 'beneficiary': '', 'site': '', 'proposal': ''}
        if re.search(r'验证整改|整改方案|验证方案|评估整改|调整后.{0,8}(?:效果|有利|合适)', positive):
            put('stage', 'remedy_check', positive)
        elif re.search(r'已经(?:确认|核对|确定).{0,15}(?:范围|布局|房屋)|分析具体问题|具体查哪|诊断具体', positive):
            put('stage', 'diagnosis', positive)
        elif re.search(r'是否.{0,12}(?:房屋|布局|宅地).{0,8}(?:有关|导致)|先(?:核对|确认|排查).{0,8}范围|核对问题范围|是不是.{0,12}风水', positive):
            put('stage', 'scope_check', positive)
        elif re.search(r'选房|择地|买房|租房|是否适合|适不适合|合适吗|适合.{0,10}(?:居住|自住)', positive):
            put('stage', 'site_choice', positive)
        if re.search(r'阴宅|墓地|坟地|祖坟|安葬|迁坟', positive):
            put('site_kind', 'yin', positive)
        elif re.search(r'阳宅|自住|入住|住房|租房|买房|选房|居住|民宿', positive):
            put('site_kind', 'yang', positive)
        if re.search(r'尚未入住|还没(?:有)?(?:入住|搬入|搬进去)|未入住|没有入住|准备入住', positive):
            put('residence', 'not_occupied', positive)
        elif re.search(r'已经(?:入住|搬入|住进)|已入住|住进(?:去|来)|已经在.{0,12}住了', positive):
            put('residence', 'occupied', positive)
        if re.search(r'不是本人.{0,6}(?:起|摇)|我没(?:有)?亲自(?:起|摇)|不(?:是)?我.{0,4}(?:起|摇)|(?:朋友|别人|他人|她|他)替我(?:起|摇)|代(?:起|摇)卦', positive):
            put('role', 'other', positive)
        elif re.search(r'卦师.{0,8}(?:独立|勘察)|我以卦师身份', positive):
            put('role', 'consultant', positive)
        elif re.search(r'(?:我|本人|主家).{0,8}(?:亲自|自己)(?:起|摇)|(?:我|本人)(?:来|亲自)?(?:起|摇)(?:的|这一|这次|一)?卦|本人起卦', positive):
            put('role', 'host', positive)
        sites = list(dict.fromkeys(re.findall(r'[A-Za-zＡ-Ｚａ-ｚ0-9一二三四五六七八九十]+(?:号)?房|[这那](?:套|间|处)(?:房|住宅|地)|[这那]块地', positive)))
        if len(sites)==1:
            put('site', sites[0], sites[0])
        elif len(sites)>1:
            put('site', '', '出现多个备选地点，请选择本次要问的一处。')
        beneficiary = re.search(r'我和(?:家人|父母|孩子)|我们一家(?:三口|四口|五口)?|一家[三四五六]口|全家|为(?:父母|孩子|朋友)|给(?:父母|孩子|朋友)', positive)
        if beneficiary:
            put('beneficiary', beneficiary.group(), beneficiary.group())
        elif re.search(r'我.{0,12}(?:自住|居住)|自己住|本人自住', positive):
            put('beneficiary', '我', positive)
        proposal = re.search(r'长期自住|自住|出租|经营民宿|开民宿|办公|安葬|迁坟|(?:拟|准备|打算)(?:将|把).{1,80}', positive)
        if proposal:
            put('proposal', proposal.group()[:800], proposal.group())
    if re.search(r'问自己|我(?:自己|本人)|我想|我打算|我准备', text):
        result['person']['subject'] = 'self'
    if re.search(r'帮(?:朋友|父母|同事|孩子)|问(?:朋友|父母|同事|孩子)', text):
        result['person']['subject'] = 'other'
    age = re.search(r'我(?:今年|现在)?\s*(\d{1,3})\s*岁', text)
    if age and 0 <= int(age[1]) <= 150:
        result['person']['querent_age'] = int(age[1])
    return result


def route(text, context, mode='auto'):
    if mode not in MODES:
        raise ValueError('对话方式无效。')
    if mode=='auto' and re.search(r'(?:为什么|怎么|为何).{0,15}(?:重新|又|自动).{0,5}(?:起|摇|跑)',text):
        return {'action':'feedback','skill_id':'liuyao','answer':'这像是对软件行为的反馈。我先保留问题，不会因此另起一卦。'}
    if mode=='auto' and re.search(r'(?:起卦|卜宅|六爻)(?:方式)?(?:是什么意思|是什么|怎么用|如何操作)|什么(?:叫|是)(?:起卦|卜宅|六爻)',text):
        if context.get('active_case'):return {'action':'followup'}
        return {'action':'chat','answer':'可以先描述想问的事。明确想起一卦时，我会展开结果录入卡片；按实际器具记录，程序再排盘。具体方法可在“更多 → 规则与使用原理”中查看。'}
    if mode == 'feedback' or re.search(r'提交(?:一个)?反馈|提(?:一个)?\s*issue|软件.{0,8}(?:报错|有问题)|按钮.{0,8}(?:失效|点不了)|排盘.{0,5}(?:错了|不对)|回答太长|回答太短', text, re.I):
        return {'action': 'feedback', 'skill_id': 'knowledge' if context.get('last_skill') == 'knowledge' else 'liuyao',
                'answer': '我把问题整理成了反馈卡片，你可以修改后交给 AI 处理。'}
    if re.search(r'打开.{0,4}(?:人物|个人)(?:信息|档案)|管理人物', text):
        return {'action': 'profiles', 'answer': '人物档案可以单独保存，并在之后的占问中反复选用。'}
    if re.search(r'导入(?:资料|文档|文件)|管理(?:资料|知识库)|添加(?:资料|文档)', text):
        return {'action': 'documents', 'answer': '可以在这里导入文件或粘贴原文，之后直接在对话里提问。'}
    explicit_knowledge = mode == 'knowledge' or bool(re.search(r'知识库|资料(?:里|中)|查(?:看|一下|询)?.{0,8}(?:资料|原文)|根据(?:原文|资料)|原文出处', text))
    explicit_cast = mode == 'liuyao' or (bool(re.search(NEW_CAST, text)) and not re.search(NEGATED_CAST, text))
    if explicit_knowledge:
        return {'action': 'knowledge'}
    if explicit_cast:
        clear_new=mode=='liuyao' or bool(re.search(r'补录|再起|另起|重新(?:起|摇)|新起|我想(?:起|摇|卜宅)|我(?:要|准备|打算)(?:起|摇)|帮我(?:起|摇|卜宅)|^(?:起|摇|占|卜)(?:一|个)?卦',text))
        if context.get('active_case') and context.get('last_skill')=='liuyao' and not clear_new:
            return {'action':'followup'}
        # Repeated references to the current chart do not create a new one.
        if context.get('active_case') and re.search(r'继续(?:刚才|这个|这次|原来).{0,5}卦|回到.{0,6}卦', text) and not re.search(r'再起|重新起|新起', text):
            return {'action': 'followup'}
        previous = context.get('pending_cast', {}).get('prefill') if context.get('pending_cast') and not re.search(r'重新起|再起|新起', text) else None
        prefill = casting_defaults(text, previous)
        return {'action': 'cast', 'prefill': prefill, 'update_target': context.get('pending_cast', {}).get('turn_id') if previous else None,
                'answer': '已为这次占问展开起卦卡片。时间和起卦地点默认使用当前时刻与手机定位，排盘采用当地真太阳时。'
                if prefill['time_policy'] == 'current' else '这是补录或时间未知的卦，请核对当时的实际时间与地点；不会用现在的定位代替旧记录。'}
    if context.get('pending_cast') and context.get('last_skill') == 'liuyao':
        return {'action': 'cast', 'prefill': casting_defaults(text, context['pending_cast']['prefill']),
                'update_target': context['pending_cast']['turn_id'], 'answer': '已把这条补充带入起卦卡片；会话预填的选项仍可更改。'}
    if context.get('active_case') and (context.get('last_skill') == 'liuyao' or re.search(r'回到.{0,8}卦|继续.{0,6}卦', text)):
        return {'action': 'followup'}
    if context.get('last_skill') == 'knowledge' or re.search(r'解释|概念|定义|什么意思|什么是|是什么|如何理解|五行|意魂神魄精', text) or re.search(NEGATED_CAST, text):
        return {'action': 'knowledge'}
    if re.fullmatch(r'(?:你好|您好|谢谢|好的|明白了|收到)[！!。,.，\s]*', text):
        return {'action': 'chat', 'answer': '可以直接告诉我想做什么：起一卦、讨论资料，或反馈使用中遇到的问题。'}
    return {'action': 'clarify', 'answer': '这件事想通过起一卦来问，还是根据知识库资料一起分析？',
            'choices': [{'label': '起一卦', 'mode': 'liuyao'}, {'label': '根据资料讨论', 'mode': 'knowledge'}]}
