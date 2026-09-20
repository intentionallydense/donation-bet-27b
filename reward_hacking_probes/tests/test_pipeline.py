import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare import synthetic, historical
from probe import direction, span_mask, encode
from evaluate import auc, threshold_at_fpr, validate_labels


class ProbeTests(unittest.TestCase):
    def test_token_weighted_direction(self):
        # Unequal lengths: averaging example means would give a different result.
        positive = np.array([[1.,2.],[3.,4.],[8.,9.]])
        negative = np.array([[2.,1.]])
        np.testing.assert_allclose(direction(positive.sum(0),3,negative.sum(0),1), [2.,4.])
        with self.assertRaises(ValueError):
            direction([0,0],1,[0,0],1)

    def test_mask_excludes_prompt_straddlers_and_specials(self):
        mask = span_mask([(0,0),(0,4),(4,7),(7,9),(9,12)],5,[[0,4]])
        self.assertEqual(mask.tolist(),[False,False,False,True,False])

    def test_tied_auc_and_threshold(self):
        self.assertEqual(auc(np.array([0,1]),np.array([2.,2.])),.5)
        negatives = np.array([1.,2.,2.,3.,4.])
        t = threshold_at_fpr(negatives,.2)
        self.assertLessEqual(float((negatives > t).mean()),.2)
        self.assertEqual(threshold_at_fpr(negatives,0),4.)

    def test_leakage_and_quotes(self):
        targets = {'a': {'continuation':'I choose the desired result.'}, 'b': {'continuation':'I use the evidence.'}}
        labels = [dict(id='a',start=0,end=27,label=1,quote='desired result',split='calibration',group='g'),
                  dict(id='b',start=0,end=19,label=0,split='test',group='g')]
        with self.assertRaisesRegex(ValueError,'leakage'):
            validate_labels(labels,targets)
        labels[1]['group'] = 'h'
        validate_labels(labels,targets)
        labels[0]['quote'] = 'invented quote'
        with self.assertRaisesRegex(ValueError,'verbatim'):
            validate_labels(labels,targets)

    def test_evaluation_selects_only_on_calibration(self):
        import tempfile
        import json
        import subprocess
        import hashlib
        from probe import file_hash
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            targets = root/'targets.jsonl'
            labels = root/'labels.jsonl'
            output = root/'result.json'
            targets.write_text(''.join(json.dumps({'id':str(i),'continuation':'valid'})+'\n' for i in range(4)))
            labels.write_text(''.join(json.dumps(dict(id=str(i),start=0,end=5,label=i%2,
                split='calibration' if i < 2 else 'test',group=str(i),quote='valid'))+'\n' for i in range(4)))
            (root/'run.json').write_text(json.dumps({'input_sha256':file_hash(targets)}))
            for i in range(4):
                name = hashlib.sha256(str(i).encode()).hexdigest()+'.npz'
                # A wins calibration, B wins test. Selection must still choose A.
                a = i%2 if i < 2 else 1-i%2
                b = 1-i%2 if i < 2 else i%2
                np.savez(root/name,offsets=np.array([[0,5]]),A__L0=np.array([a]),B__L0=np.array([b]))
            subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'evaluate.py'),
                '--labels',str(labels),'--targets',str(targets),'--scores',str(root),
                '--output',str(output)],check=True,capture_output=True)
            result = json.loads(output.read_text())
            self.assertEqual(result['selected_probe'],'A__L0')
            self.assertEqual(result['calibration']['auroc'],1.)
            self.assertEqual(result['test']['auroc'],0.)

    def test_matched_synthetic(self):
        rows = synthetic()
        pairs = {}
        for row in rows:
            pairs.setdefault(row['pair'],[]).append(row)
            self.assertEqual(row['spans'],[[0,len(row['continuation'])]])
        self.assertEqual(len(pairs),192)
        for pair in pairs.values():
            self.assertEqual({r['label'] for r in pair},{0,1})
            self.assertEqual(pair[0]['messages'],pair[1]['messages'])

    def test_historical_dedup(self):
        rows,total = historical()
        self.assertEqual(total,4200)
        self.assertEqual(len(rows),2800)
        self.assertEqual(sum(len(r['sources']) for r in rows),total)
        self.assertTrue(all(r['label'] is None for r in rows))
        for r in rows:
            key = r['metadata']['prompt_key']
            direction = r['metadata']['direction']
            if 'casual_good_cause_silent' in key or 'casual_unicef_silent' in key:
                self.assertNotEqual(direction,'below_good')
            if 'casual_silent_naked_run' in key:
                self.assertNotEqual(direction,'above_good')

    def test_encode_real_cached_tokenizer(self):
        from tokenizers import Tokenizer
        from jinja2 import Environment, StrictUndefined
        base = Path('/home/iodide/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9')
        if not base.exists():
            self.skipTest('Optional local tokenizer cache absent')
        class Adapter:
            tokenizer = Tokenizer.from_file(str(base/'tokenizer.json'))
            template = Environment(undefined=StrictUndefined).from_string((base/'chat_template.jinja').read_text())
            def apply_chat_template(self,messages,**kwargs):
                return self.template.render(messages=messages,tools=None,**kwargs)
            def __call__(self,text,**kwargs):
                encoding = self.tokenizer.encode(text,add_special_tokens=False)
                return {'input_ids':encoding.ids,'offset_mapping':encoding.offsets}
        row = historical()[0][0]
        ids, offsets, mask, start = encode(Adapter(),row,16384)
        self.assertTrue(all(a >= start for (a,b), keep in zip(offsets,mask) if keep))
        self.assertTrue(mask.any())
        with self.assertRaisesRegex(ValueError,'no truncation'):
            encode(Adapter(),row,10)


if __name__ == '__main__':
    unittest.main()
