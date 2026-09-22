"""Single canonical user report layout."""
SECTIONS = [('day_month','从日月来看'),('change','从动变来看'),('shi_ying','从世应来看'),
            ('relations','从其他关系来看'),('support','支持因素'),('obstacle','阻碍因素'),('advice','最终建议')]

def format_divination_report(conclusion, sections):
    return {'title':'综合解卦','summary':conclusion['answer'],'conclusion':conclusion,
            'sections':[{'key':key,'heading':heading,'content':sections.get(key,'')} for key,heading in SECTIONS]}
