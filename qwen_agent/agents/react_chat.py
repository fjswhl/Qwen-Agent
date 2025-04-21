import json
import os
from typing import Dict, Iterator, List, Literal, Optional, Tuple, Union

from qwen_agent.agents.fncall_agent import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ASSISTANT, DEFAULT_SYSTEM_MESSAGE, Message
from qwen_agent.settings import MAX_LLM_CALL_PER_RUN
from qwen_agent.tools import BaseTool
from qwen_agent.utils.utils import format_as_text_message, merge_generate_cfgs

TOOL_DESC = (
    '{name_for_model}: Call this tool to interact with the {name_for_human} API. '
    'What is the {name_for_human} API useful for? {description_for_model} Parameters: {parameters} {args_format}')

PROMPT_REACT = """Answer the following questions as best you can. You have access to the following tools:

{tool_descs}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can be repeated zero or more times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {query}
Thought: """


class ReActChat(FnCallAgent):
    """This agent use ReAct format to call tools"""

    def __init__(self,
                 function_list: Optional[List[Union[str, Dict, BaseTool]]] = None,
                 llm: Optional[Union[Dict, BaseChatModel]] = None,
                 system_message: Optional[str] = DEFAULT_SYSTEM_MESSAGE,
                 name: Optional[str] = None,
                 description: Optional[str] = None,
                 files: Optional[List[str]] = None,
                 **kwargs):
        super().__init__(function_list=function_list,
                         llm=llm,
                         system_message=system_message,
                         name=name,
                         description=description,
                         files=files,
                         **kwargs)
        self.extra_generate_cfg = merge_generate_cfgs(
            base_generate_cfg=self.extra_generate_cfg,
            new_generate_cfg={'stop': ['Observation:', 'Observation:\n']},
        )

    def _run(self, messages: List[Message], lang: Literal['en', 'zh'] = 'en', **kwargs) -> Iterator[List[Message]]:
        text_messages = self._prepend_react_prompt(messages, lang=lang)

        num_llm_calls_available = MAX_LLM_CALL_PER_RUN
        response: str = 'Thought: '

        # Start tracing with Langfuse
        trace = None
        if self.langfuse:
            trace_id = kwargs.get("trace_id", None)
            trace_name = f"{self.name or 'ReActChat'}_run"

            # Convert messages to serializable format for tracing
            serializable_messages = []
            # Extract the latest user input if possible
            latest_user_input = None
            for msg in messages:
                try:
                    msg_data = msg.model_dump() if hasattr(msg, "model_dump") else msg
                    serializable_messages.append(msg_data)
                    # Find the latest user message as the primary input
                    if msg_data.get("role") == "user":
                        latest_user_input = msg_data
                except:
                    # Fallback for dict messages
                    serializable_messages.append(msg)
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        latest_user_input = msg

            # Prepare initial metadata with complete conversation history
            trace_metadata = {
                "agent_name": self.name or "ReActChat",
                "language": lang,
                "system_message": self.system_message,
                "conversation_history": serializable_messages
            }

            # Input should be focused on the user's query or instruction
            trace_input = {
                "user_input": latest_user_input["content"] if latest_user_input else None,
                "language": lang,
            }

            if trace_id:
                trace = self.langfuse.trace(
                    id=trace_id,
                    name=trace_name,
                    input=trace_input,
                    metadata=trace_metadata
                )
            else:
                trace = self.langfuse.trace(
                    name=trace_name,
                    input=trace_input,
                    metadata=trace_metadata
                )

        try:
            while num_llm_calls_available > 0:
                num_llm_calls_available -= 1

                # Start LLM span in Langfuse
                llm_span = None
                if self.langfuse and trace:
                    llm_input = {
                        "messages": [msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in text_messages],
                        "extra_generate_cfg": {"lang": lang}
                    }

                    llm_span = trace.span(
                        name="llm_call",
                        input=llm_input,
                    )

                # Display the streaming response
                output = []
                for output in self._call_llm(messages=text_messages):
                    if output:
                        yield [Message(role=ASSISTANT, content=response + output[-1].content)]

                # End LLM span in Langfuse
                if self.langfuse and trace and llm_span:
                    if output:
                        llm_span.end(
                            output={
                                "output": [msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in output]
                            }
                        )
                    else:
                        llm_span.end(output={"output": "No output"})

                # Accumulate the current response
                if output:
                    response += output[-1].content

                has_action, action, action_input, thought = self._detect_tool(output[-1].content)
                if not has_action:
                    break

                # Start Tool span in Langfuse
                tool_span = None
                if self.langfuse and trace:
                    tool_span = trace.span(
                        name=f"tool_{action}",
                        input={
                            "tool_name": action,
                            "tool_args": action_input,
                        },
                    )

                # Add the tool result
                observation = self._call_tool(action, action_input, messages=messages, trace=trace if self.langfuse else None, **kwargs)

                # End Tool span in Langfuse
                if self.langfuse and trace and tool_span:
                    tool_span.end(output={"result": observation})

                observation = f'\nObservation: {observation}\nThought: '
                response += observation
                yield [Message(role=ASSISTANT, content=response)]

                if (not text_messages[-1].content.endswith('\nThought: ')) and (not thought.startswith('\n')):
                    # Add the '\n' between '\nQuestion:' and the first 'Thought:'
                    text_messages[-1].content += '\n'
                if action_input.startswith('```'):
                    # Add a newline for proper markdown rendering of code
                    action_input = '\n' + action_input
                text_messages[-1].content += thought + f'\nAction: {action}\nAction Input: {action_input}' + observation

            # End the trace successfully
            if self.langfuse and trace:
                try:
                    trace.update(
                        output={
                            "response": response
                        },
                        status="success"
                    )
                except Exception as e:
                    print(f"Failed to update Langfuse trace: {e}")

        except Exception as e:
            # End the trace with error if there was an exception
            if self.langfuse and trace:
                try:
                    trace.update(
                        output={
                            "error": str(e),
                            "error_type": type(e).__name__
                        },
                        status="error"
                    )
                except Exception as trace_err:
                    print(f"Failed to update Langfuse trace with error: {trace_err}")
            raise

    def _prepend_react_prompt(self, messages: List[Message], lang: Literal['en', 'zh']) -> List[Message]:
        tool_descs = []
        for f in self.function_map.values():
            function = f.function
            name = function.get('name', None)
            name_for_human = function.get('name_for_human', name)
            name_for_model = function.get('name_for_model', name)
            assert name_for_human and name_for_model
            args_format = function.get('args_format', '')
            tool_descs.append(
                TOOL_DESC.format(name_for_human=name_for_human,
                                 name_for_model=name_for_model,
                                 description_for_model=function['description'],
                                 parameters=json.dumps(function['parameters'], ensure_ascii=False),
                                 args_format=args_format).rstrip())
        tool_descs = '\n\n'.join(tool_descs)
        tool_names = ','.join(tool.name for tool in self.function_map.values())
        text_messages = [format_as_text_message(m, add_upload_info=True, lang=lang) for m in messages]
        text_messages[-1].content = PROMPT_REACT.format(
            tool_descs=tool_descs,
            tool_names=tool_names,
            query=text_messages[-1].content,
        )
        return text_messages

    def _detect_tool(self, text: str) -> Tuple[bool, str, str, str]:
        special_func_token = '\nAction:'
        special_args_token = '\nAction Input:'
        special_obs_token = '\nObservation:'
        func_name, func_args = None, None
        i = text.rfind(special_func_token)
        j = text.rfind(special_args_token)
        k = text.rfind(special_obs_token)
        if 0 <= i < j:  # If the text has `Action` and `Action input`,
            if k < j:  # but does not contain `Observation`,
                # then it is likely that `Observation` is ommited by the LLM,
                # because the output text may have discarded the stop word.
                text = text.rstrip() + special_obs_token  # Add it back.
            k = text.rfind(special_obs_token)
            func_name = text[i + len(special_func_token):j].strip()
            func_args = text[j + len(special_args_token):k].strip()
            text = text[:i]  # Return the response before tool call, i.e., `Thought`
        return (func_name is not None), func_name, func_args, text
