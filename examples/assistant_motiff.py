"""A sqlite database assistant implemented by assistant"""

import os
import asyncio

from qwen_agent.agents import Assistant, ReActChat
from qwen_agent.gui import WebUI
from typing import Optional, Union, Dict

from qwen_agent.tools.base import BaseTool, register_tool

ROOT_RESOURCE = os.path.join(os.path.dirname(__file__), 'resource')

@register_tool('file_creator')
class FileCreatorTool(BaseTool):
    name = 'file_creator'
    description = '创建文件，接收参数：1. 文件路径 2. 文件内容'
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "文件的路径"
            },
            "content": {
                "type": "string",
                "description": "文件的内容"
            }
        },
        "required": ["file_path", "content"]
    }

    def __init__(self, cfg: Optional[Dict] = None):
        super().__init__(cfg)

    def call(self, params: Union[str, dict], **kwargs) -> str:
        """创建文件并写入内容

        Args:
            params: 包含文件路径和内容的参数
            kwargs: 额外参数

        Returns:
            文件创建结果
        """
        return f"文件已成功创建"

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
    },
    'file_creator'
    ]
    bot = ReActChat(
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
            '根据这个 Motiff 文档，在 /tmp 目录下依次创建多个 React 组件: '
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
