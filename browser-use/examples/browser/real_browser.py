import os
import sys
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio

import dotenv
from langchain_openai import ChatOpenAI

from browser_use import Agent, Browser, BrowserConfig, Controller

dotenv.load_dotenv("/Users/zhuige/Documents/llm/agent/projects/browser-use/.env")

from pydantic import BaseModel
# Define the output format as a Pydantic model
class Post(BaseModel):
	post_title: str
	post_url: str
	num_comments: int
	hours_since_post: int


class Posts(BaseModel):
	posts: List[Post]


controller = Controller(output_model=Posts)

browser = Browser(
	config=BrowserConfig(
		# NOTE: you need to close your chrome browser - so that this can open your browser in debug mode
		browser_binary_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
		headless=True,
	)
)

LLM_MODEL_NAME_QWEN="gpt-4o"
LLM_API_KEY_QWEN="dummy-key"
LLM_BASE_URL_QWEN="http://localhost:6300"
llm=ChatOpenAI(
    model=LLM_MODEL_NAME_QWEN,
    api_key=LLM_API_KEY_QWEN,
    base_url=LLM_BASE_URL_QWEN,
)


async def main():
	agent = Agent(
		task='search for aworld and scroll down 1000px',
		# task='In docs.google.com write my Papa a quick letter',
		llm=llm,
		browser=browser,
		controller=controller,
	)

	history = await agent.run()
	result = history.final_result()
	if result:
		parsed: Posts = Posts.model_validate_json(result)

		for post in parsed.posts:
			print('\n--------------------------------')
			print(f'Title:            {post.post_title}')
			print(f'URL:              {post.post_url}')
			print(f'Comments:         {post.num_comments}')
			print(f'Hours since post: {post.hours_since_post}')
	else:
		print('No result')
	await browser.close()

	input('Press Enter to close...')


if __name__ == '__main__':
	asyncio.run(main())
