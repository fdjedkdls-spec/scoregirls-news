import copy
import unittest
from datetime import date
from update_week import prepare


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 10, 26)
        self.pack = {'version': 3, 'updatedAt': '2026-10-24', 'weeks': [
            {'id': '2026-W43', 'start': '2026-10-19', 'title': 'Previous', 'questions': [
                {'text': 'Old question', 'choices': ['A','B','C','D'], 'answer': 0, 'cat': '科学'}]}]}
        self.sources = {'2026-W43': [{'questions': [1], 'title': 'Old', 'url': 'https://example.org/old',
            'referenceDate': '2026-10-23', 'checkedAt': '2026-10-24', 'supports': 'Old fact'}]}
        self.batch = {'batchId': '2026-W44', 'checkedAt': '2026-10-26', 'title': 'New',
            'questions': [{'text': f'New question {i}', 'choices':['A','B','C','D'], 'answer': i%4, 'cat':'科学'} for i in range(10)],
            'sources': [{'questions': nums, 'url': f'https://example.org/{i}', 'title':'Primary article',
                'referenceDate':'2026-10-24', 'checkedAt':'2026-10-26', 'supports':'Verified facts'}
                for i,nums in enumerate([[1,2,3],[4,5,6],[7,8,9,10]])]}

    def run_prepare(self, supplement=False):
        return prepare(self.pack, self.sources, self.batch, self.today, supplement)

    def test_new_week_preserves_inputs_and_past(self):
        old = copy.deepcopy((self.pack, self.sources))
        p,s,c = self.run_prepare()
        self.assertTrue(c)
        self.assertEqual((self.pack,self.sources),old)
        self.assertEqual(p['weeks'][0],self.pack['weeks'][0])
        self.assertEqual(p['weeks'][-1]['id'],'2026-W44')
        self.assertEqual(p['version'],4)
        self.assertEqual(s['2026-W43'],self.sources['2026-W43'])

    def test_retry_does_not_append_or_increment(self):
        p,s,_ = self.run_prepare()
        p2,s2,c = prepare(p,s,self.batch,self.today)
        self.assertFalse(c); self.assertEqual((p,s),(p2,s2))

    def test_changed_content_cannot_reuse_batch_id(self):
        p,s,_ = self.run_prepare(); self.batch['questions'][0]['answer']=2
        with self.assertRaises(ValueError): prepare(p,s,self.batch,self.today)

    def test_existing_week_requires_explicit_supplement(self):
        self.pack,self.sources,_ = self.run_prepare(); self.batch['batchId']='another'
        with self.assertRaises(ValueError): self.run_prepare()

    def test_supplement_preserves_and_remaps_old_sources(self):
        self.today=date(2026,10,24); self.batch['checkedAt']='2026-10-24'
        for ref in self.batch['sources']: ref['checkedAt']='2026-10-24'
        p,s,_=self.run_prepare(True)
        self.assertEqual(p['weeks'][0]['questions'][10:],self.pack['weeks'][0]['questions'])
        self.assertEqual(s['2026-W43'][-1]['questions'],[11])

    def test_year_boundary_uses_iso_year(self):
        self.today=date(2027,1,1); self.batch['checkedAt']='2027-01-01'
        for ref in self.batch['sources']: ref.update(referenceDate='2026-12-30',checkedAt='2027-01-01')
        p,_,_=self.run_prepare(); self.assertEqual(p['weeks'][-1]['id'],'2026-W53')

    def test_duplicate_after_normalization_rejected(self):
        self.batch['questions'][0]['text']='Old  question!'
        with self.assertRaises(ValueError): self.run_prepare()

    def test_missing_source_rejected(self):
        self.batch['sources'][-1]['questions']=[7,8,9]
        with self.assertRaises(ValueError): self.run_prepare()

    def test_stale_source_rejected(self):
        self.batch['sources'][0]['referenceDate']='2026-09-01'
        with self.assertRaises(ValueError): self.run_prepare()

    def test_unchecked_today_rejected(self):
        self.batch['sources'][0]['checkedAt']='2026-10-25'
        with self.assertRaises(ValueError): self.run_prepare()

    def test_ten_questions_required(self):
        self.batch['questions'].pop()
        with self.assertRaises(ValueError): self.run_prepare()

    def test_invalid_answer_rejected(self):
        self.batch['questions'][0]['answer']=4
        with self.assertRaises(ValueError): self.run_prepare()


if __name__ == '__main__':
    unittest.main()
