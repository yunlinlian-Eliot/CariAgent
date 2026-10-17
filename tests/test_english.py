import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r'[\u4e00-\u9fff]')


class EnglishEditionTests(unittest.TestCase):
    def test_english_workflow_strings_and_prompts_in_isolated_process(self):
        script = '''
import sys, re
sys.path.insert(0, 'core')
import simple_mvp as m
import retrieval
for path in m.PROMPT_DIR.glob('*.txt'):
    text = m.load_prompt(path.name)
    assert not re.search('[\\u4e00-\\u9fff]', text), path
assert 'English edition language contract' in m.load_prompt('system_cariagent.txt')
assert 'skip' in m.SKIP_WORDS and 'not sure' in m.SKIP_WORDS
assert 'stop' in m.EXIT_WORDS
for names in [[], ['Example employer']]:
    plan = m.build_gap_followup_plan({'matches':[{'jd_requirement':'SQL analysis', 'importance':'high', 'match_level':'low', 'evidence_quality':'weak', 'matched_experience_names':names}]})
    assert plan['candidate_questions']
    assert not re.search('[\\u4e00-\\u9fff]', str(plan)), plan
assert not re.search('[\\u4e00-\\u9fff]', str(retrieval.chunk_text('Built SQL dashboards for an employer.')[0].to_dict()))
assert not re.search('[\\u4e00-\\u9fff]', m.default_fit_summary({'fit_level':'good_fit'}))
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env={**os.environ, 'CARIAGENT_LANGUAGE':'en'}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_all_english_pages_navigation_and_missing_key_error(self):
        # Keep process language changes out of the Chinese regression suite.
        script = '''
from streamlit.testing.v1 import AppTest
import re, os
os.environ.pop('OPENAI_API_KEY', None)
at = AppTest.from_file('ui/app_en.py').run(timeout=30)
assert not at.exception, list(at.exception)
assert 'Data Analyst Intern' in at.session_state['jd_text']
assert not re.search('[\\u4e00-\\u9fff]', at.session_state['experience_text'])
def check():
    assert not at.exception, list(at.exception)
    for node in at:
        for attr in ('label', 'value', 'placeholder'):
            value = getattr(node, attr, None)
            if isinstance(value,str):
                assert not re.search('[\\u4e00-\\u9fff]',value), (node.type,attr,value)
check()
for step in ['jd', 'match', 'followup', 'resume', 'experience']:
    at.session_state['current_step']=step
    at.run(timeout=30)
    check()
at.session_state['current_step']='jd'
at.run(timeout=30)
next(b for b in at.button if b.label == 'Analyze JD').click().run(timeout=30)
check()
assert any('OPENAI_API_KEY' in e.value for e in at.error), list(at.error)
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env={**os.environ, 'CARIAGENT_LANGUAGE':'en'}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
