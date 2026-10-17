import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
import simple_mvp
from streamlit.testing.v1 import AppTest


class ResumeOutputTests(unittest.TestCase):
    def test_generation_keeps_body_and_advice_in_separate_files(self):
        output = {
            'resume_markdown': '# 简历草稿\n\n## 技能\nPython',
            'improvement_suggestions_markdown': '请补充项目成果数据。',
        }
        state = simple_mvp.WorkflowState()
        with patch.object(simple_mvp, 'ask_ai_for_json_once', return_value=(None, output)) as generate, patch.object(simple_mvp, 'save_markdown') as save:
            result = simple_mvp.run_resume_generation_workflow(None, state)
        self.assertEqual(result.resume_markdown, output['resume_markdown'])
        self.assertEqual(result.improvement_suggestions_markdown, output['improvement_suggestions_markdown'])
        self.assertEqual(generate.call_args.args[3], 'resume_output')
        self.assertEqual(save.call_args_list[0].args, ('result.md', output['resume_markdown']))
        self.assertEqual(save.call_args_list[1].args, ('improvement_suggestions.md', output['improvement_suggestions_markdown']))

    def test_resume_page_displays_advice_separately_and_exports_only_body(self):
        # Execute the actual page and real DOCX converter, capturing both downloads.
        at = AppTest.from_string('''
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(UI_PATH)))
import app
import simple_mvp
import streamlit as st
state = simple_mvp.WorkflowState(resume_markdown='# Resume\\n\\n## Skills\\nPython', improvement_suggestions_markdown='ADVICE_ONLY_SENTINEL')
st.session_state.workflow_state = state
with patch.object(st, 'download_button') as download:
    app.render_resume_page()
    st.session_state.captured_downloads = [call.kwargs['data'] for call in download.call_args_list]
'''.replace('UI_PATH', repr(str(ROOT / 'ui')))).run(timeout=30)
        self.assertFalse(at.exception, list(at.exception))
        self.assertTrue(any('不包含在下载文件中' in e.label for e in at.expander))
        self.assertTrue(any(m.value == 'ADVICE_ONLY_SENTINEL' for m in at.markdown))
        markdown, docx = at.session_state['captured_downloads']
        self.assertNotIn('ADVICE_ONLY_SENTINEL', markdown)
        from zipfile import ZipFile
        from io import BytesIO
        with ZipFile(BytesIO(docx)) as z:
            xml = z.read('word/document.xml').decode()
        self.assertIn('Python', xml)
        self.assertNotIn('ADVICE_ONLY_SENTINEL', xml)

    def test_prompt_ends_resume_before_advice(self):
        prompt = (ROOT / "prompts/task_s8_generate_resume.txt").read_text()
        self.assertNotIn("## 建议后续简历完善方向", prompt)
        self.assertIn("以上为 resume_markdown 的全部内容，到技能部分结束。", prompt)

    def test_schema_requires_both_outputs(self):
        schema = simple_mvp.SCHEMAS['resume_output']
        self.assertEqual(set(schema['required']), {'resume_markdown', 'improvement_suggestions_markdown'})
        self.assertFalse(schema['additionalProperties'])


if __name__ == '__main__':
    unittest.main()
