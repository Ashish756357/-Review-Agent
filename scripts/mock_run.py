import asyncio
from types import SimpleNamespace

from pr_review_agent.main import PRReviewAgent
import pr_review_agent.main as main_module
import pr_review_agent.ai_engine as ai_module


class FakeProvider:
    def __init__(self, *args, **kwargs):
        pass

    async def authenticate(self):
        return True

    async def get_pull_request(self, owner, repo, pr_number):
        # Return a fake PR object compatible with PullRequest dataclass
        return SimpleNamespace(
            id='1', number=int(pr_number), title='Fake PR',
            description='Fake description', author='tester',
            source_branch='feature', target_branch='main',
            url='http://example', created_at=None, updated_at=None,
            state='open', draft=False, labels=[], assignees=[], reviewers=[]
        )

    async def get_pull_request_files(self, owner, repo, pr_number):
        # Return a single modified file with a small patch
        return [SimpleNamespace(
            filename='example.py', status='modified', additions=2, deletions=0,
            patch='+print("hello")\n', blob_url=None, raw_url=None
        )]

    async def get_file_content(self, owner, repo, path, ref):
        return 'def hello():\n    print("hello")\n'

    async def create_review(self, owner, repo, pr_number, review):
        return 'mock-review-id'

    async def close(self):
        return None


def install_fake_provider():
    def fake_init(self):
        return {'github': FakeProvider()}

    main_module.PRReviewAgent._initialize_git_providers = fake_init


def install_fake_ai():
    async def fake_generate_feedback(self, code_content, file_path, context=None):
        # Return an empty feedback list for deterministic behavior
        return []

    ai_module.AIEngine.generate_feedback = fake_generate_feedback


async def run_mock():
    install_fake_provider()
    install_fake_ai()

    async with PRReviewAgent() as agent:
        result = await agent.review_pull_request('github', 'test', 'test', 1)
        print('=== MOCK REVIEW RESULT ===')
        print('Overall score:', result.get('overall_score'))
        review = result.get('review')
        if review:
            print('Grade:', review.grade)
            print('Body:\n', review.body[:1000])


if __name__ == '__main__':
    asyncio.run(run_mock())
