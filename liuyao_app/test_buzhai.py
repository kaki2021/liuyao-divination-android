"""Source mapping, strict scope and retained topic context; no live model calls."""
import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from . import buzhai
from .pipeline import calculate_chart, _catalog, _selection_rules, _interpretation_rules, run_analysis
from .rulebook import load_rules
from .test_v5 import NewReportProvider, INPUT
from . import test_app_flow
from casting_input import normalize_casting_input, CastingInputError
from validate_input import validate_input
from validate_ai_contract import check_schema, load_pack, ContractError, _source_roles
from case_store import CaseStore, Actor

TOPIC = {'stage':'site_choice', 'site_kind':'yang', 'role':'host', 'residence':'not_occupied',
         'beneficiary':'我与家人', 'site':'备选房 A', 'proposal':'按现有户型自住'}


class SourceAndScopeTests(unittest.TestCase):
    def test_input_rejects_partial_or_wrong_types_without_touching_original(self):
        for value in (None, True, [], {}, {**TOPIC,'site':''}, {**TOPIC,'stage':['diagnosis']},
                      {**TOPIC,'extra':'x'}, {**TOPIC,'beneficiary':'x'*81},
                      {**TOPIC,'previous_case_id':'../db'}, {**TOPIC,'proposal':2}):
            with self.subTest(value=value):
                self.assertFalse(validate_input({**INPUT,'buzhai':value})['valid'])
                with self.assertRaises(CastingInputError):normalize_casting_input({**INPUT,'buzhai':value})
        original={**INPUT,'buzhai':copy.deepcopy(TOPIC)}
        normalized=normalize_casting_input(original);normalized['buzhai']['site']='changed'
        self.assertEqual(original['buzhai'],TOPIC)

    def test_all_64_static_charts_preserve_engine_and_name_from_shi(self):
        expected={'兄弟':('亲丁地','子孙'),'子孙':('丁财地','妻财'),'妻财':('财官地','官鬼'),
                  '官鬼':('官印地','父母'),'父母':('名望地','兄弟')}
        seen=set();clashes=[];rules=load_rules()
        for bits in itertools.product((0,1),repeat=6):
            data={'lines':['young_yang' if b else 'young_yin' for b in bits],'actual_cast_time':INPUT['actual_cast_time']}
            ordinary=calculate_chart(data,rules);scoped=calculate_chart({**data,'buzhai':TOPIC},rules)
            topic=scoped.pop('buzhai_analysis');self.assertEqual(scoped,ordinary)
            shi=ordinary['main']['lines'][ordinary['shi_position']-1]
            f=topic['five_lands'];self.assertEqual((f['candidate_name'],f['required_relative']),expected[shi['relative']])
            self.assertEqual(f['status'],'candidate_only');seen.add(f['candidate_name'])
            self.assertIsNone(topic['residence_choice'].get('verdict'))
            if topic['residence_choice']['six_clash']:clashes.append(ordinary['main']['name'])
            for fact in buzhai.structural_facts({**ordinary,'buzhai_analysis':topic}):
                check_schema(fact, load_pack()['stages']['interpretation']['input_schema']['$defs']['fact'])
                self.assertNotIn('备选房 A',fact['value'])
        self.assertEqual(len(seen),5);self.assertEqual(len(clashes),10)

    def test_scope_matrix_keeps_choice_and_empty_exceptions_out_of_diagnosis(self):
        _,catalog=_catalog()
        for stage,kind,role,residence in itertools.product(buzhai.STAGES,buzhai.KINDS,buzhai.ROLES,buzhai.RESIDENCE):
            ctx={**TOPIC,'stage':stage,'site_kind':kind,'role':role,'residence':residence}
            chart=calculate_chart({**normalize_casting_input(INPUT),'buzhai':ctx})
            rules=_interpretation_rules(catalog,_selection_rules(catalog,[],ctx),chart)
            ids=[r['rule_id'] for r in rules]
            choice=(stage=='site_choice' and kind=='yang' and role=='host')
            self.assertEqual('buzhai.residence_choice' in ids,choice)
            self.assertEqual('buzhai.empty_scope' in ids,choice and residence=='not_occupied')
            self.assertEqual(len(ids),len(set(ids)))
            self.assertEqual(chart['buzhai_analysis']['residence_choice']['applicable'],choice)
            _source_roles({r['rule_id']:r for r in rules})

    def test_ordinary_keyword_does_not_implicitly_enable_topic(self):
        _,catalog=_catalog();question='我出生八字要看风水，房屋旬空是否不好'
        rules=_selection_rules(catalog,[{'text':question}])
        chart=calculate_chart({**normalize_casting_input(INPUT),'question':question})
        rules=_interpretation_rules(catalog,rules,chart)
        self.assertNotIn('buzhai_analysis',chart)
        self.assertFalse(any(r['rule_id'].startswith('buzhai.') for r in rules))

    def test_missing_date_is_unknown_not_no_clash_or_empty(self):
        chart=calculate_chart({'lines':['young_yang']*6,'buzhai':TOPIC})
        r=chart['buzhai_analysis']['residence_choice']
        for key in ('shi_day_clash','shi_empty','shi_month_class'):self.assertIsNone(r[key])
        self.assertEqual(r['empty_exception'],'conditional_only')

    def test_export_explains_non_numeric_rules_and_exact_sources(self):
        guide=buzhai.principle_guide()
        self.assertEqual(len(guide['rules']),10);self.assertEqual(len(guide['sources']),2)
        self.assertEqual(guide['numeric_weights_added'],0)
        self.assertTrue(all(r['parameter_value'] is None and r['source_locator'] and r['limitations'] for r in guide['rules']))
        s=next(x for x in guide['sources'] if x['source_id']=='SRC-TAIBU')
        self.assertEqual(s['pages'],173);self.assertIn('PDF-P',s['anchor_convention'])
        with self.assertRaises(ContractError):_source_roles({'fake':{'source_id':'made-up','source_role':'core_supplement'}})


class RetentionTests(unittest.TestCase):
    def test_all_four_ai_stages_receive_only_scoped_frozen_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'cases.sqlite3';db=CaseStore(path);actor=Actor('topic','session')
            try:
                data={**INPUT,'buzhai':copy.deepcopy(TOPIC)}
                cid=db.create_case(actor,data,idempotency_key='topic')['case_id']
                provider=NewReportProvider();result=run_analysis(path,actor,cid,'deepseek','synthetic',1,provider_call=provider)
                self.assertEqual(result['status'],'completed',result.get('error'))
                self.assertEqual(len(provider.calls),4)
                for call in provider.calls:self.assertIn('本次用户明确启用卜宅专题',call['prompt'])
                interpretation=next(c for c in provider.calls if c['stage']=='interpretation')['input']
                topic_facts=[f for f in interpretation['facts'] if f['fact_id'].startswith('BUZHAI_')]
                self.assertEqual(len(topic_facts),3)
                self.assertTrue(any(f['kind']=='context' and '备选房 A' in f['value'] for f in interpretation['facts']))
                exported=db.export_case(actor,cid);run=exported['analysis_runs'][0]
                self.assertEqual(run['input_snapshot']['input']['buzhai'],TOPIC)
                self.assertEqual(run['outcome']['result']['chart_snapshot']['buzhai_analysis']['context'],TOPIC)
                # Add a new revision, without modifying the prior analysis or input.
                prior=copy.deepcopy(run)
                db.revise_case(actor,cid,{**data,'buzhai':{**TOPIC,'stage':'diagnosis'}},reason='分阶段记录',expected_revision_seq=1,idempotency_key='revision')
                self.assertEqual(db.export_case(actor,cid)['analysis_runs'][0],prior)
            finally:db.close()


class TopicHttpTests(unittest.TestCase):
    # This class uses the real server fixture, without inheriting the suite's tests.
    setUp = test_app_flow.FullAppFlow.setUp
    tearDown = test_app_flow.FullAppFlow.tearDown
    request = test_app_flow.FullAppFlow.request
    api = test_app_flow.FullAppFlow.api
    analyze_demo = test_app_flow.FullAppFlow.analyze_demo
    def test_topic_case_export_and_principle_download(self):
        guide=self.api('GET','/api/principles')
        self.assertEqual(len(guide['rules']),10)
        status,raw,headers=self.request('GET','/api/principles/export')
        self.assertEqual(status,200);self.assertIn('attachment',headers['Content-Disposition'])
        self.assertEqual(json.loads(raw),guide)
        submitted={**INPUT,'buzhai':TOPIC}
        case=self.api('POST','/api/cases',{'input':submitted},201)
        detail=self.api('GET',f"/api/cases/{case['case_id']}")
        self.assertEqual(detail['chart']['buzhai_analysis']['context'],TOPIC)
        self.analyze_demo(case['case_id'])
        exported=self.api('GET',f"/api/cases/{case['case_id']}/export")
        self.assertEqual(exported['original_input']['buzhai'],TOPIC)
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            return
        schema=json.loads((Path(__file__).resolve().parents[1]/'software_prep/case_record_schema.json').read_text())
        Draft202012Validator(schema).validate(exported)
