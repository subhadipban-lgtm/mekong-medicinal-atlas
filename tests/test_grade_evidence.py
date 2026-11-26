import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from grade_evidence import grade_citation, grade_row
class Grades(unittest.TestCase):
 def test_unverified_journal_not_a(self):
  self.assertNotEqual(grade_citation('Smith 2020, Journal of Ethnopharmacology 20:30',{}, {},'Plant example')[0],'A')
 def test_author_year_does_not_inherit(self):
  self.assertNotEqual(grade_citation('Smith 2020',{}, {('smith','2020'):'10.1/example'},'Plant example')[0],'A')
 def test_resolved_metadata(self):
  cite='Smith 2020, doi:10.1/example'
  result=grade_citation(cite,{cite:{'status':'resolved_doi','type':'journal-article','doi':'10.1/example'}},{},'Plant example')
  self.assertEqual(result[0],'A')
 def test_volume_semicolon_preserved(self):
  cite='Smith 2020;20(3):12'
  self.assertEqual(grade_row(cite,{cite:{'status':'resolved_doi','type':'journal-article','doi':'10.1/example'}},{},'Plant example')[0],'A')
