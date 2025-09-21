#!/usr/bin/env python3
"""
Test script for enhanced AI analysis capabilities.

This script demonstrates the improved AI feedback and detailed analysis
features of the PR Review Agent.
"""

import asyncio
import os
from src.pr_review_agent.ai_engine import AIEngine, AIConfig
from src.pr_review_agent.config import load_config

def test_enhanced_ai_analysis():
    """Test the enhanced AI analysis with sample code."""

    # Sample Python code for analysis
    sample_code = '''
def process_user_data(user_input):
    # Get user data from database
    query = "SELECT * FROM users WHERE id = " + user_input
    result = db.execute(query)

    # Process the data
    for x in result:
        if x['status'] == 'active':
            print("User is active")

    return result
'''

    # Sample JavaScript code for analysis
    sample_js_code = '''
function fetchUserData(userId) {
    // Insecure API call
    const apiUrl = `https://api.example.com/users/${userId}`;
    fetch(apiUrl)
        .then(response => response.json())
        .then(data => {
            // No error handling
            console.log(data);
        });
}
'''

    # Create AI configuration
    ai_config = AIConfig(
        enabled=True,
        provider="openai",
        api_key="your_openai_api_key_here",  # Replace with actual key
        model="gpt-3.5-turbo",
        max_tokens=2000,
        temperature=0.3
    )

    async def run_analysis():
        """Run the AI analysis on sample code."""
        engine = AIEngine(ai_config)

        print("🚀 Testing Enhanced AI Analysis")
        print("=" * 50)

        # Test Python code analysis
        print("\n📄 Analyzing Python Code:")
        print("-" * 30)

        try:
            feedback = await engine.generate_feedback(
                sample_code,
                "sample.py",
                context={
                    'change_type': 'modified',
                    'additions': 15,
                    'deletions': 2
                }
            )

            if feedback:
                print(f"✅ Generated {len(feedback)} feedback items:")
                for i, item in enumerate(feedback, 1):
                    print(f"\n{i}. [{item.severity.upper()}] {item.message}")
                    if item.suggestion:
                        print(f"   💡 {item.suggestion}")
            else:
                print("❌ No feedback generated (API key may be missing)")

        except Exception as e:
            print(f"❌ Error during analysis: {e}")

        # Test JavaScript code analysis
        print("\n📄 Analyzing JavaScript Code:")
        print("-" * 30)

        try:
            feedback = await engine.generate_feedback(
                sample_js_code,
                "sample.js",
                context={
                    'change_type': 'added',
                    'additions': 12,
                    'deletions': 0
                }
            )

            if feedback:
                print(f"✅ Generated {len(feedback)} feedback items:")
                for i, item in enumerate(feedback, 1):
                    print(f"\n{i}. [{item.severity.upper()}] {item.message}")
                    if item.suggestion:
                        print(f"   💡 {item.suggestion}")
            else:
                print("❌ No feedback generated (API key may be missing)")

        except Exception as e:
            print(f"❌ Error during analysis: {e}")

        await engine.close()

    # Run the async test
    asyncio.run(run_analysis())

def test_config_loading():
    """Test loading the enhanced configuration."""
    print("\n🔧 Testing Configuration Loading:")
    print("-" * 30)

    try:
        # Try to load the enhanced config
        config = load_config("enhanced_config.yaml")
        print("✅ Enhanced config loaded successfully")

        # Check AI settings
        if hasattr(config, 'ai') and config.ai.enabled:
            print("✅ AI analysis enabled")
            print(f"   - Provider: {config.ai.provider}")
            print(f"   - Model: {config.ai.model}")
        else:
            print("⚠️  AI analysis disabled in config")

    except FileNotFoundError:
        print("❌ Enhanced config file not found")
        print("   Run: cp enhanced_config.yaml config.yaml")
    except Exception as e:
        print(f"❌ Error loading config: {e}")

if __name__ == "__main__":
    print("🧪 PR Review Agent - Enhanced AI Analysis Test")
    print("=" * 50)

    # Test configuration loading
    test_config_loading()

    # Test AI analysis (requires API key)
    test_enhanced_ai_analysis()

    print("\n" + "=" * 50)
    print("📝 Next Steps:")
    print("1. Add your OpenAI API key to enhanced_config.yaml")
    print("2. Run: pr-review-agent --config enhanced_config.yaml")
    print("3. Check README_AI_ENHANCED.md for full documentation")
