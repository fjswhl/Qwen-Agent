"""A simple example demonstrating basic usage of Qwen-Agent for building a chat bot.

This example shows:
1. How to initialize a basic agent
2. How to have a simple conversation
3. How to use the agent with custom system prompts

Usage:
    python simple_chat_bot.py
"""

from qwen_agent.agents import Assistant
from qwen_agent.llm import get_chat_model


def simple_chat_example():
    """Basic chat example with Qwen-Agent"""
    
    llm_cfg = {
        'model': 'qwen-max',
        'model_server': 'dashscope',
    }
    
    system_message = """You are a helpful AI assistant. You are friendly, 
    knowledgeable, and always try to provide accurate and useful information."""
    
    bot = Assistant(
        llm=llm_cfg,
        system_message=system_message,
    )
    
    messages = []
    
    print("Simple Chat Bot Example")
    print("=" * 50)
    print("This is a simple example of using Qwen-Agent.")
    print("Ask the bot a question!")
    print("=" * 50)
    
    user_input = "What is Qwen-Agent and what can it do?"
    print(f"\nUser: {user_input}")
    
    messages.append({'role': 'user', 'content': user_input})
    
    print("\nAssistant: ", end='', flush=True)
    response_text = ''
    for response in bot.run(messages):
        if response:
            content = response[-1].get('content', '')
            if content:
                print(content, end='', flush=True)
                response_text = content
    
    print("\n")
    
    messages.append({'role': 'assistant', 'content': response_text})
    
    user_input_2 = "Can you give me a simple use case?"
    print(f"\nUser: {user_input_2}")
    messages.append({'role': 'user', 'content': user_input_2})
    
    print("\nAssistant: ", end='', flush=True)
    for response in bot.run(messages):
        if response:
            content = response[-1].get('content', '')
            if content:
                print(content, end='', flush=True)
    
    print("\n")


def chat_with_llm_directly():
    """Example of using LLM directly without agent wrapper"""
    
    print("\n" + "=" * 50)
    print("Direct LLM Chat Example")
    print("=" * 50)
    
    llm_cfg = {'model': 'qwen-max', 'model_server': 'dashscope'}
    llm = get_chat_model(llm_cfg)
    
    messages = [
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'user', 'content': 'Explain what an AI agent is in one sentence.'}
    ]
    
    print("\nUser: Explain what an AI agent is in one sentence.")
    print("\nAssistant: ", end='', flush=True)
    
    for responses in llm.chat(messages):
        for response in responses:
            content = response.get('content', '')
            if content:
                print(content, end='', flush=True)
    
    print("\n")


if __name__ == '__main__':
    print("\n🤖 Qwen-Agent Simple Chat Bot Examples\n")
    
    print("Example 1: Using Agent with System Message")
    simple_chat_example()
    
    print("\n" + "=" * 50)
    print("Example 2: Direct LLM Usage")
    chat_with_llm_directly()
    
    print("\n" + "=" * 50)
    print("✅ Examples completed!")
    print("\nTip: Set your DASHSCOPE_API_KEY environment variable to run these examples.")
    print("Get your API key from: https://dashscope.console.aliyun.com/")
