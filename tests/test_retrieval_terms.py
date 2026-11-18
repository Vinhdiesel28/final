import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from knowledge.retrieval_terms import canonical_text,search_query

class TerminologyTests(unittest.TestCase):
 def test_equivalent_abbreviations_match_same_concept(self):
  self.assertEqual(canonical_text('HbA1c'),canonical_text('A1C'))
  self.assertEqual(canonical_text('body mass index'),canonical_text('BMI'))
 def test_aliases_expand_queries_without_inventing_answers(self):
  self.assertIn('A1C',search_query('What is HbA1c?'))
  self.assertIn('body mass index',search_query('BMI definition'))
  self.assertEqual(search_query('unknown trial ZXQ999'),'unknown trial ZXQ999')
 def test_alias_replacement_respects_word_boundaries(self):
  self.assertEqual(canonical_text('notHbA1cCode'),'nothba1ccode')
