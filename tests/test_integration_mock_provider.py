import pytest
from datetime import datetime
from types import SimpleNamespace


@pytest.mark.asyncio
async def test_integration_mock_provider(monkeypatch):
    # Create a fake provider instance with the methods used by PRReviewAgent
    class FakeProvider:
        def __init__(self, *args, **kwargs):
            pass

        async def authenticate(self):
            return True

        async def get_pull_request(self, owner, repo, pr_number):
            return SimpleNamespace(
                id='1', number=int(pr_number), title='Test PR',
                description='desc', author='tester',
                source_branch='feature', target_branch='main',
                url='http://example', created_at=datetime.now(),
                updated_at=datetime.now(), state='open', draft=False,
                labels=[], assignees=[], reviewers=[]
            )

        async def get_pull_request_files(self, owner, repo, pr_number):
            return [SimpleNamespace(
                filename='example.py', status='modified', additions=3, deletions=0,
                patch='+print(\"hello\")\n' , blob_url=None, raw_url=None
            )]

        async def get_file_content(self, owner, repo, path, ref):
            return 'def foo():\n    return 42\n'

        async def close(self):
            return None

    # Patch PRReviewAgent to use FakeProvider for 'github'
    from pr_review_agent import main

    orig_init = main.PRReviewAgent._initialize_git_providers

    def fake_init(self):
        return {'github': FakeProvider(None)}

    monkeypatch.setattr(main.PRReviewAgent, '_initialize_git_providers', fake_init)

    # Patch ai_engine.generate_feedback to return empty list (avoid external API)
    async def fake_generate_feedback(self, code_content, file_path, context=None):
        return []

    monkeypatch.setattr('pr_review_agent.ai_engine.AIEngine.generate_feedback', fake_generate_feedback)

    # Now call the FastAPI endpoint in-process
    from pr_review_agent.async_webui import app
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        resp = await ac.post('/api/review', json={
            'provider': 'github', 'owner': 'me', 'repo': 'repo', 'pr': '1'
        })

    assert resp.status_code == 200
    data = resp.json()
    assert 'overall_score' in data
    assert data['grade'] is not None
