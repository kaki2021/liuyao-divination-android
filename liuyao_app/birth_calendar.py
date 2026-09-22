"""Birth pillars using the application's explicit Beijing standard-time policy."""
from datetime import date, datetime
import re
from .calendar_context import calculate_calendar, CALCULATION_POLICY, CONVENTION_LABEL


def calculate_birth_chart(birth_date='', birth_time=''):
    if not birth_date and not birth_time:
        return {'status':'missing','pillars':{},'text':'','message':'填写公历出生日期后自动排出年、月、日柱；补充时间后排出时柱。'}
    try:
        if not isinstance(birth_date,str) or not isinstance(birth_time,str):
            raise ValueError('出生日期和时间格式不正确。')
        if birth_time and 'T' not in birth_time and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',birth_time):
            raise ValueError('出生时间格式不正确。')
        moment = datetime.fromisoformat(birth_time.replace('Z','+00:00')) if birth_time and 'T' in birth_time else None
        day_text = birth_date or (moment.date().isoformat() if moment else birth_time)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day_text):
            raise ValueError('出生日期须使用公历年、月、日。')
        day = date.fromisoformat(day_text)
        if moment and birth_date and moment.date()!=day:
            raise ValueError('出生日期与出生时间中的日期不一致。')
        if not 1900<=day.year<=2100:
            raise ValueError('出生排盘支持 1900 至 2100 年。')
        def calculate(value):
            result=calculate_calendar({'actual_cast_time':value})
            if result['status']!='computed':raise ValueError(result['message'])
            return result['pillars']
        if moment:
            instant=moment.isoformat(timespec='seconds')
            if moment.utcoffset() is None:instant+='+08:00'
            pillars=calculate(instant)
            status='computed';message='已按公历出生时间自动排出四柱。'
            alternatives={}
        else:
            start=calculate(day_text+'T00:00:00+08:00')
            end=calculate(day_text+'T23:59:59+08:00')
            pillars={key:start[key] if start[key]==end[key] else None for key in ('year','month','day')}
            pillars['hour']=None
            alternatives={key:[start[key],end[key]] for key in ('year','month','day') if start[key]!=end[key]}
            status='partial'
            message='出生时刻未填写，时柱暂缺。'
            if alternatives:message+='当天有交节，年柱或月柱需补充出生时刻后确定。'
        labels={'year':'年','month':'月','day':'日','hour':'时'}
        text=' '.join(pillars[key] or ('时柱待补' if key=='hour' else labels[key]+'柱待定') for key in labels)
        return {'status':status,'birth_date':day_text,'birth_time':birth_time,'pillars':pillars,'text':text,
                'message':message,'alternatives':alternatives,'convention_label':CONVENTION_LABEL,
                'calculation_policy':dict(CALCULATION_POLICY)}
    except (ValueError,TypeError,OverflowError) as exc:
        return {'status':'error','pillars':{},'text':'','message':str(exc)}
