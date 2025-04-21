"""A sqlite database assistant implemented by assistant"""

import os
import asyncio
from typing import Optional

from qwen_agent.agents import Assistant
from qwen_agent.gui import WebUI

ROOT_RESOURCE = os.path.join(os.path.dirname(__file__), 'resource')


def init_agent_service():
    llm_cfg = {'model': 'qwen-max'}
    system = ('你扮演一个 Motiff 专家，拥有分析 Motiff 文档的能力，Motiff 是一个类似于 Figma 的矢量设计工具')
    tools = [{
        "mcpServers": {
            "motiff" : {
                "command": "npx",
                    "args": ["-y", "@motiffcom/motiff-mcp-server@latest"],
                "env": {
                    "MOTIFF_TOKEN": "HfdIPgQIXew2xZrJ8K9qK3QzuLhOBzP5",
                    "MOTIFF_HOST": "https://api.motiff.com"
                }
            }
        }
    }]
    bot = Assistant(
        llm=llm_cfg,
        name='Motiff 专家',
        description='Motiff 文档分析',
        system_message=system,
        function_list=tools,
    )

    return bot


def app_tui():
    # Define the agent
    bot = init_agent_service()

    # Chat
    messages = []
    while True:
        # Query example: 数据库里有几张表
        query = input('user question: ')
        # File example: resource/poem.pdf
        file = input('file url (press enter if no file): ').strip()
        if not query:
            print('user question cannot be empty！')
            continue
        if not file:
            messages.append({'role': 'user', 'content': query})
        else:
            messages.append({'role': 'user', 'content': [{'text': query}, {'file': file}]})

        response = []
        for response in bot.run(messages):
            print('bot response:', response)
        messages.extend(response)


def app_gui():
    # Define the agent
    bot = init_agent_service()
    chatbot_config = {
        'prompt.suggestions': [
            '分析这个 Motiff 文档',
        ]
    }
    WebUI(
        bot,
        chatbot_config=chatbot_config,
    ).run()


if __name__ == '__main__':
    # test()
    # app_tui()
    app_gui()
