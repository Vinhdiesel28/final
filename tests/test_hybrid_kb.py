import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from services.llm_explanation import validate_generation,apply_generation
from services.hybrid_kb import literal, rank_graph
from services.knowledge_service import normalize

class HybridEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.knowledge={'evidence':[{'evidence_id':'ev1','text':'A1C reflects average blood glucose over the past 3 months.'}]}
    def test_fake_citation_is_rejected(self):
        generated={'claims':[{'text':'A1C phản ánh đường huyết.','evidence_id':'fake','quote':'A1C reflects average blood glucose'}]}
        self.assertFalse(validate_generation(generated,self.knowledge)['passed'])
    def test_fabricated_quote_and_number_are_rejected(self):
        generated={'claims':[{'text':'A1C phản ánh 9 tháng.','evidence_id':'ev1','quote':'A1C reflects average blood glucose over the past 3 months.'}]}
        self.assertIn('unsupported_number',validate_generation(generated,self.knowledge)['issues'])
        generated['claims'][0]['quote']='Invented supporting evidence text'
        self.assertIn('quote_or_citation_invalid',validate_generation(generated,self.knowledge)['issues'])
    def test_generation_preserves_prediction_section(self):
        base={'answer':'Score 4.4%. Old text.','sections':[{'id':'assessment','text':'Score 4.4%.'},{'id':'medical_evidence','text':'Old text.'}],'model_factors':[]}
        generated={'status':'generated','claims':[{'text':'A1C phản ánh glucose trong 3 tháng.','evidence_id':'ev1','quote':self.knowledge['evidence'][0]['text']}]}
        result=apply_generation(base,generated,self.knowledge)
        self.assertEqual(result['sections'][0],base['sections'][0]);self.assertIn('[ev1]',result['answer'])
    def test_english_number_words_can_be_translated_to_digits(self):
        knowledge={'evidence':[{'evidence_id':'ev1','text':'A1C measures average blood glucose over the past three months.'}]}
        generation={'claims':[{'text':'A1C phản ánh glucose trung bình trong 3 tháng.','evidence_id':'ev1','quote':knowledge['evidence'][0]['text']}]}
        self.assertTrue(validate_generation(generation,knowledge)['passed'])
    def test_bundle_provenance_and_stable_ids(self):
        path=ROOT/'knowledge/hybrid/kb_bundle.json'
        if not path.exists():self.skipTest('Build KB first')
        b=json.loads(path.read_text(encoding='utf-8'));docs={d['id'] for d in b['documents']};chunks={c['id'] for c in b['chunks']}
        self.assertEqual(len(chunks),len(b['chunks']))
        self.assertTrue(all(c['document_id'] in docs for c in b['chunks']))
        self.assertTrue(all(f['chunk_id'] in chunks for f in b['facts']))
        self.assertTrue(all(c['page_start'] for c in b['chunks'] if c['source_type']=='pdf'))
        self.assertTrue(any(c['source_type']=='web' for c in b['chunks']))
    def test_cypher_export_escapes_strings(self):
        self.assertEqual(literal("a'b\\c"),"'a\\'b\\\\c'")

class GraphUpgradeTests(unittest.TestCase):
    def test_graph_rank_applies_relevance_before_top_k(self):
        rows = [{"doc": {"id": f"a{i:02d}", "text": "HbA1c cohort table"},
                 "matched_entities": 1} for i in range(25)]
        best = {"doc": {"id": "zzz", "text": "HbA1c reflects average blood glucose"},
                "matched_entities": 1}
        self.assertEqual(rank_graph(rows + [best], {"hba1c", "average", "glucose"})[0], best)


if __name__=='__main__':unittest.main()
