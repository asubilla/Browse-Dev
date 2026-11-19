"""
Setup:
1. uv init --python 3.12 my-agent && cd my-agent && uv add 'browse-dev==1.0.6'
2. export BROWSE_DEV_API_KEY=bu_...   (get one at https://cloud.browser-use.com/new-api-key)

Runs on the default model (bu-4.0) in a Browse Dev Cloud browser. For a local browser and your own model:
    Agent(task, llm=ChatOpenAI('gpt-6-luna'), browser=Browser('chromium'))   # or Browser('chrome'): your open Chrome
"""

from browse_dev import Agent

agent = Agent('Find the number of stars of the following repos: browse-dev, playwright, stagehand, react, nextjs')
result = agent.run_sync()
print(result.final_result())
