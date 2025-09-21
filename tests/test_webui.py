import json
from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    # Import using top-level package name (src layout exposes `pr_review_agent`)
    from pr_review_agent.webui import app

    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def fake_review_result():
    class FakeReview:
        grade = 'GOOD'
        body = 'Summary body'

    return {
        'overall_score': 0.85,
        'review': FakeReview(),
        'analysis_results': [],
        'ai_feedback': []
    }


def test_index_page(client):
    rv = client.get('/')
    assert rv.status_code == 200
    assert b'Run PR Review' in rv.data


@patch('pr_review_agent.webui.review_pr')
def test_run_review_html(mock_review, client):
    mock_review.return_value = fake_review_result()

    rv = client.post('/run', data={
        'provider': 'github',
        'owner': 'octocat',
        'repo': 'hello-world',
        'pr': '1'
    })

    assert rv.status_code == 200
    assert b'PR Review Result' in rv.data
    assert b'Summary body' in rv.data


@patch('pr_review_agent.webui.review_pr')
def test_api_review_json(mock_review, client):
    mock_review.return_value = fake_review_result()

    rv = client.post('/api/review', data=json.dumps({
        'provider': 'github',
        'owner': 'octocat',
        'repo': 'hello-world',
        'pr': '1'
    }), content_type='application/json')

    assert rv.status_code == 200
    data = rv.get_json()
    assert data['overall_score'] == 0.85
    assert data['grade'] == 'GOOD'
