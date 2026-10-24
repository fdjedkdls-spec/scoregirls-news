import copy
import json
import unittest
from datetime import date
from pathlib import Path
from validate_feed import validate


class FeedValidationTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parent
        self.pack = json.loads((base/'newsquiz.json').read_text(encoding='utf-8'))
        self.sources = json.loads((base/'sources.json').read_text(encoding='utf-8'))
        self.today = date.fromisoformat(self.pack['updatedAt'])
        self.week = max((w for w in self.pack['weeks'] if date.fromisoformat(w['start']) <= self.today), key=lambda w:w['start'])

    def run_check(self):
        return validate(self.pack, self.sources, self.today, True)

    def test_valid(self):
        self.assertGreaterEqual(self.run_check()['currentQuestions'], 10)

    def test_missing_current_week(self):
        self.pack['weeks'].remove(self.week)
        with self.assertRaises(ValueError): self.run_check()

    def test_duplicate_week(self):
        self.pack['weeks'].append(copy.deepcopy(self.week))
        with self.assertRaises(ValueError): self.run_check()

    def test_invalid_date(self):
        self.week['start']='2026-02-30'
        with self.assertRaises(ValueError): self.run_check()

    def test_mismatched_week_id(self):
        self.week['id']='2030-W01'
        with self.assertRaises(ValueError): self.run_check()

    def test_wrong_choice_count(self):
        self.week['questions'][0]['choices'].pop()
        with self.assertRaises(ValueError): self.run_check()

    def test_blank_choice(self):
        self.week['questions'][0]['choices'][1]=' '
        with self.assertRaises(ValueError): self.run_check()

    def test_duplicate_choice(self):
        q=self.week['questions'][0]; q['choices'][1]=q['choices'][0]
        with self.assertRaises(ValueError): self.run_check()

    def test_wrong_answer(self):
        self.week['questions'][0]['answer']=4
        with self.assertRaises(ValueError): self.run_check()

    def test_boolean_answer(self):
        self.week['questions'][0]['answer']=True
        with self.assertRaises(ValueError): self.run_check()

    def test_missing_sources(self):
        self.sources={}
        with self.assertRaises(ValueError): self.run_check()

    def test_future_update(self):
        self.pack['updatedAt']='2099-01-01'
        with self.assertRaises(ValueError): self.run_check()


if __name__ == '__main__':
    unittest.main()
