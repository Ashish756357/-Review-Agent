from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import asyncio
from .main import review_pr
from .config import Config

app = FastAPI(title="PR Review Agent API")

# Optional API key enforcement: set environment variable API_KEY to require requests
import os
API_KEY = os.getenv('API_KEY')


class ReviewRequest(BaseModel):
    provider: str
    owner: str
    repo: str
    pr: str
    config: Optional[str] = None


@app.post('/api/review')
async def api_review(req: ReviewRequest, x_api_key: str | None = Header(default=None)):
    # Enforce API key if configured
    if API_KEY:
        if not x_api_key or x_api_key != API_KEY:
            raise HTTPException(status_code=401, detail='Invalid or missing API key')
    # Load config if provided
    config = None
    if req.config:
        try:
            config = Config.from_file(req.config)
        except Exception:
            config = None

    try:
        # Call the async review_pr directly
        result = await review_pr(req.provider, req.owner, req.repo, req.pr, config)

        review = result.get('review')
        return {
            'overall_score': result.get('overall_score'),
            'grade': review.grade if review else None,
            'issues': len(result.get('analysis_results', [])) + len(result.get('ai_feedback', [])),
            'review_body': review.body if review else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn

    uvicorn.run('src.pr_review_agent.async_webui:app', host='127.0.0.1', port=8000, reload=True)
