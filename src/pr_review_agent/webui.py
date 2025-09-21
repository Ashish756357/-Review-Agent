from flask import Flask, request, render_template, jsonify
import asyncio
from .main import review_pr
from .config import Config

app = Flask(__name__, template_folder="templates")


def run_sync(coro):
    """Run an async coroutine from synchronous Flask handler."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No running loop; create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/run', methods=['POST'])
def run_review():
    provider = request.form.get('provider')
    owner = request.form.get('owner')
    repo = request.form.get('repo')
    pr = request.form.get('pr')
    cfg_path = request.form.get('config')

    config = None
    if cfg_path:
        try:
            config = Config.from_file(cfg_path)
        except Exception:
            config = None

    try:
        result = run_sync(review_pr(provider, owner, repo, pr, config))

        score = result.get('overall_score')
        grade = result.get('review').grade if result.get('review') else 'N/A'
        issues = len(result.get('analysis_results', [])) + len(result.get('ai_feedback', []))
        body = result.get('review').body if result.get('review') else ''

        return render_template('result.html', score=score, grade=grade, issues=issues, body=body)
    except Exception as e:
        return f"Error running review: {e}", 500


@app.route('/api/review', methods=['POST'])
def api_review():
    """JSON API endpoint: POST JSON {provider, owner, repo, pr, config}

    Returns JSON with review summary. This endpoint is intended for programmatic usage
    and tests; it avoids side effects like posting reviews to remote providers.
    """
    data = request.get_json() or {}
    provider = data.get('provider')
    owner = data.get('owner')
    repo = data.get('repo')
    pr = data.get('pr')
    cfg_path = data.get('config')

    config = None
    if cfg_path:
        try:
            config = Config.from_file(cfg_path)
        except Exception:
            config = None

    # Basic validation
    if not all([provider, owner, repo, pr]):
        return jsonify({'error': 'provider, owner, repo and pr are required'}), 400

    try:
        result = run_sync(review_pr(provider, owner, repo, pr, config))

        review = result.get('review')
        response = {
            'overall_score': result.get('overall_score'),
            'grade': review.grade if review else None,
            'issues': len(result.get('analysis_results', [])) + len(result.get('ai_feedback', [])),
            'review_body': review.body if review else None
        }

        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
