from __future__ import annotations

import logging
import os

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
	BaseMessage,
	HumanMessage,
	SystemMessage
)
from langchain_core.messages.utils import convert_to_openai_messages

from browser_use.agent.memory.views import MemoryConfig
from browser_use.agent.message_manager.service import MessageManager
from browser_use.agent.message_manager.views import ManagedMessage, MessageMetadata
from browser_use.utils import time_execution_sync

logger = logging.getLogger(__name__)


PROCEDURAL_MEMORY_SYSTEM_PROMPT = """
You are a memory summarization system that records and preserves the complete interaction history between a human and an AI agent. You are provided with the agent’s execution history over the past N steps. Your task is to produce a comprehensive summary of the agent's output history that contains every detail necessary for the agent to continue the task without ambiguity. **Every output produced by the agent must be recorded verbatim as part of the summary.**

### Overall Structure:
- **Overview (Global Metadata):**
  - **Task Objective**: The overall goal the agent is working to accomplish.
  - **Progress Status**: The current completion percentage and summary of specific milestones or steps completed.

- **Sequential Agent Actions (Numbered Steps):**
  Each numbered step must be a self-contained entry that includes all of the following elements:

  1. **Agent Action**:
     - Precisely describe what the agent did (e.g., "Clicked on the 'Blog' link", "Called API to fetch content", "Scraped page data").
     - Include all parameters, target elements, or methods involved.

  2. **Action Result (Mandatory, Unmodified)**:
     - Immediately follow the agent action with its exact, unaltered output.
     - Record all returned data, responses, HTML snippets, JSON content, or error messages exactly as received. This is critical for constructing the final output later.

  3. **Embedded Metadata**:
     For the same numbered step, include additional context such as:
     - **Key Findings**: Any important information discovered (e.g., URLs, data points, search results).
     - **Navigation History**: For browser agents, detail which pages were visited, including their URLs and relevance.
     - **Errors & Challenges**: Document any error messages, exceptions, or challenges encountered along with any attempted recovery or troubleshooting.
     - **Current Context**: Describe the state after the action (e.g., "Agent is on the blog detail page" or "JSON data stored for further processing") and what the agent plans to do next.

### Guidelines:
1. **Preserve Every Output**: The exact output of each agent action is essential. Do not paraphrase or summarize the output. It must be stored as is for later use.
2. **Chronological Order**: Number the agent actions sequentially in the order they occurred. Each numbered step is a complete record of that action.
3. **Detail and Precision**:
   - Use exact data: Include URLs, element indexes, error messages, JSON responses, and any other concrete values.
   - Preserve numeric counts and metrics (e.g., "3 out of 5 items processed").
   - For any errors, include the full error message and, if applicable, the stack trace or cause.
4. **Output Only the Summary**: The final output must consist solely of the structured summary with no additional commentary or preamble.

### Example Template:

```
## Summary of the agent's execution history

**Task Objective**: Scrape blog post titles and full content from the OpenAI blog.
**Progress Status**: 10% complete — 5 out of 50 blog posts processed.

1. **Agent Action**: Opened URL "https://openai.com"  
   **Action Result**:  
      "HTML Content of the homepage including navigation bar with links: 'Blog', 'API', 'ChatGPT', etc."  
   **Key Findings**: Navigation bar loaded correctly.  
   **Navigation History**: Visited homepage: "https://openai.com"  
   **Current Context**: Homepage loaded; ready to click on the 'Blog' link.

2. **Agent Action**: Clicked on the "Blog" link in the navigation bar.  
   **Action Result**:  
      "Navigated to 'https://openai.com/blog/' with the blog listing fully rendered."  
   **Key Findings**: Blog listing shows 10 blog previews.  
   **Navigation History**: Transitioned from homepage to blog listing page.  
   **Current Context**: Blog listing page displayed.

3. **Agent Action**: Extracted the first 5 blog post links from the blog listing page.  
   **Action Result**:  
      "[ '/blog/chatgpt-updates', '/blog/ai-and-education', '/blog/openai-api-announcement', '/blog/gpt-4-release', '/blog/safety-and-alignment' ]"  
   **Key Findings**: Identified 5 valid blog post URLs.  
   **Current Context**: URLs stored in memory for further processing.

4. **Agent Action**: Visited URL "https://openai.com/blog/chatgpt-updates"  
   **Action Result**:  
      "HTML content loaded for the blog post including full article text."  
   **Key Findings**: Extracted blog title "ChatGPT Updates – March 2025" and article content excerpt.  
   **Current Context**: Blog post content extracted and stored.

5. **Agent Action**: Extracted blog title and full article content from "https://openai.com/blog/chatgpt-updates"  
   **Action Result**:  
      "{ 'title': 'ChatGPT Updates – March 2025', 'content': 'We\'re introducing new updates to ChatGPT, including improved browsing capabilities and memory recall... (full content)' }"  
   **Key Findings**: Full content captured for later summarization.  
   **Current Context**: Data stored; ready to proceed to next blog post.

... (Additional numbered steps for subsequent actions)
```
"""

class Memory:
	"""
	Manages procedural memory for agents.

	This class implements a procedural memory management system using Mem0 that transforms agent interaction history
	into concise, structured representations at specified intervals. It serves to optimize context window
	utilization during extended task execution by converting verbose historical information into compact,
	yet comprehensive memory constructs that preserve essential operational knowledge.
	"""

	def __init__(
		self,
		message_manager: MessageManager,
		llm: BaseChatModel,
		config: MemoryConfig | None = None,
	):
		self.message_manager = message_manager
		self.llm = llm

		# Initialize configuration with defaults based on the LLM if not provided
		if config is None:
			self.config = MemoryConfig(llm_instance=llm, agent_id=f'agent_{id(self)}')

			# Set appropriate embedder based on LLM type
			llm_class = llm.__class__.__name__
			if llm_class == 'ChatOpenAI':
				self.config.embedder_provider = 'openai'
				self.config.embedder_model = 'text-embedding-3-small'
				self.config.embedder_dims = 1536
			elif llm_class == 'ChatGoogleGenerativeAI':
				self.config.embedder_provider = 'gemini'
				self.config.embedder_model = 'models/text-embedding-004'
				self.config.embedder_dims = 768
			elif llm_class == 'ChatOllama':
				self.config.embedder_provider = 'ollama'
				self.config.embedder_model = 'nomic-embed-text'
				self.config.embedder_dims = 512
		else:
			# Ensure LLM instance is set in the config
			self.config = config # re-validate user-provided config
			if self.config.llm_instance is None:
				self.config.llm_instance = llm

		# Check for required packages
		# try:
		# 	# also disable mem0's telemetry when ANONYMIZED_TELEMETRY=False
		# 	if os.getenv('ANONYMIZED_TELEMETRY', 'true').lower()[0] in 'fn0':
		# 		os.environ['MEM0_TELEMETRY'] = 'False'
		# 	from mem0 import Memory as Mem0Memory
		# except ImportError:
		# 	raise ImportError('mem0 is required when enable_memory=True. Please install it with `pip install mem0`.')

		# if self.config.embedder_provider == 'huggingface':
		# 	try:
		# 		# check that required package is installed if huggingface is used
		# 		from sentence_transformers import SentenceTransformer  # noqa: F401
		# 	except ImportError:
		# 		raise ImportError(
		# 			'sentence_transformers is required when enable_memory=True and embedder_provider="huggingface". Please install it with `pip install sentence-transformers`.'
		# 		)

		# Initialize Mem0 with the configuration
		# self.mem0 = Mem0Memory.from_config(config_dict=self.config.full_config_dict)

	@time_execution_sync('--create_procedural_memory')
	def create_procedural_memory(self, current_step: int) -> None:
		"""
		Create a procedural memory if needed based on the current step.

		Args:
		    current_step: The current step number of the agent
		"""
		logger.info(f'Creating procedural memory at step {current_step}')

		# Get all messages
		all_messages = self.message_manager.state.history.messages

		# Separate messages into those to keep as-is and those to process for memory
		new_messages = []
		messages_to_process = []

		for msg in all_messages:
			if isinstance(msg, ManagedMessage) and msg.metadata.message_type in {'init', 'memory'}:
				# Keep system and memory messages as they are
				new_messages.append(msg)
			else:
				if len(msg.message.content) > 0:
					messages_to_process.append(msg)

		# Need at least 2 messages to create a meaningful summary
		if len(messages_to_process) <= 1:
			logger.info('Not enough non-memory messages to summarize')
			return
		# Create a procedural memory
		memory_content = self._create([m.message for m in messages_to_process], current_step)

		if not memory_content:
			logger.warning('Failed to create procedural memory')
			return

		# Replace the processed messages with the consolidated memory
		memory_message = HumanMessage(content=memory_content)
		memory_tokens = self.message_manager._count_tokens(memory_message)
		memory_metadata = MessageMetadata(tokens=memory_tokens, message_type='memory')

		# Calculate the total tokens being removed
		removed_tokens = sum(m.metadata.tokens for m in messages_to_process)

		# Add the memory message
		new_messages.append(ManagedMessage(message=memory_message, metadata=memory_metadata))

		# Update the history
		self.message_manager.state.history.messages = new_messages
		self.message_manager.state.history.current_tokens -= removed_tokens
		self.message_manager.state.history.current_tokens += memory_tokens
		logger.info(f'Messages consolidated: {len(messages_to_process)} messages converted to procedural memory')

	def _create_old(self, messages: list[BaseMessage], current_step: int) -> str | None:
		parsed_messages = convert_to_openai_messages(messages)
		try:
			results = self.mem0.add(
				messages=parsed_messages,
				agent_id=self.config.agent_id,
				memory_type='procedural_memory',
				metadata={'step': current_step},
			)
			if len(results.get('results', [])):
				return results.get('results', [])[0].get('memory')
			return None
		except Exception as e:
			logger.error(f'Error creating procedural memory: {e}')
			return None
		

	def _create(self, messages: list[BaseMessage], current_step: int) -> str | None:
		# parsed_messages = convert_to_openai_messages(messages)
		parsed_messages = [
			SystemMessage(content=PROCEDURAL_MEMORY_SYSTEM_PROMPT)
		]+messages+[
			HumanMessage(content="Create procedural memory of the above conversation.")
        ]
		try:
			response=self.config.llm_instance.invoke(parsed_messages)
			
			return response.content
		except Exception as e:
			logger.error(f'Error creating procedural memory: {e}')
			return None
