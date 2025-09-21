import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_api_review_async(monkeypatch):
    from pr_review_agent.async_webui import app
    from httpx import AsyncClient, ASGITransport
    async def fake_review(provider, owner, repo, pr, config=None):
        class FakeReview:
            grade = 'GOOD'
            body = 'Async summary'

        return {
            'overall_score': 0.9,
            'review': FakeReview(),
            'analysis_results': [],
            'ai_feedback': []
        }

    monkeypatch.setattr('pr_review_agent.async_webui.review_pr', fake_review)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        resp = await ac.post('/api/review', json={
            'provider': 'github',
            'owner': 'octocat',
            'repo': 'hello-world',
            'pr': '1'
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data['overall_score'] == 0.9
    assert data['grade'] == 'GOOD'
