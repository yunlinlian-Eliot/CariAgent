"""Opt-in live API test using synthetic fixtures. Incurs API usage costs."""
import argparse
import ast
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
os.environ['CARIAGENT_LANGUAGE'] = 'en'
import simple_mvp as workflow


def assert_english(value):
    assert not re.search(r'[\u4e00-\u9fff]', json.dumps(value, ensure_ascii=False)), 'Unexpected Chinese text'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    workflow.OUTPUT_DIR = args.output_dir
    workflow.SAVE_OUTPUTS = True
    fixtures = {}
    for node in ast.parse((ROOT / 'ui/app.py').read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {'DEMO_EXPERIENCE', 'DEMO_JD'}:
                    fixtures[target.id] = ast.literal_eval(node.value.args[1])
    client = workflow.initialize_workflow_runtime()
    state = workflow.create_workflow_state(fixtures['DEMO_EXPERIENCE'], fixtures['DEMO_JD'])
    for step in [workflow.run_jd_analysis_workflow, workflow.run_retrieval_workflow, workflow.run_matching_workflow]:
        state = step(client, state)
        print('PASS:', step.__name__, flush=True)
    state = workflow.run_followup_planning_workflow(state)
    for field in ['jd_analysis','experience_sections','retrieval_result','experience_atoms','input_quality_audit','fit_verdict','followup_plan']:
        assert_english(getattr(state, field))
    questions = state.followup_plan['candidate_questions']
    assert questions, 'Demo must exercise follow-up planning'
    question = questions[0]
    # A simulated answer; does not claim to replace human acceptance testing.
    state.reviewed_answers = workflow.review_user_answers(client, [{
        'question_id': question['id'], 'related_experience_id': question.get('related_experience_id', ''),
        'related_experience_name': question.get('related_experience_name', ''), 'question': question['question'],
        'answer': 'I have no additional evidence beyond the experience bank. Use only the existing facts and do not invent results.',
    }])
    assert_english(state.reviewed_answers)
    print('PASS: real follow-up answer review with simulated response', flush=True)
    state = workflow.run_resume_generation_workflow(client, state)
    assert_english(state.resume_markdown)
    assert_english(state.improvement_suggestions_markdown)
    assert state.resume_markdown.strip() and state.improvement_suggestions_markdown.strip()
    assert not re.search(r'^#{1,6}\s+.*(?:suggestions|recommendations|improvements)', state.resume_markdown, re.I | re.M)
    workflow.save_workflow_trace(state)
    (args.output_dir / 'state.json').write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2))
    summary = {'passed':True, 'api_calls':len(workflow.API_CALL_TRACE), 'resume_chars':len(state.resume_markdown), 'suggestion_chars':len(state.improvement_suggestions_markdown), 'followup_questions':len(questions), 'human_acceptance_test':False}
    (args.output_dir / 'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
