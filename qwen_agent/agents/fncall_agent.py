import copy
import os
from typing import Dict, Iterator, List, Literal, Optional, Union

from qwen_agent import Agent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import DEFAULT_SYSTEM_MESSAGE, FUNCTION, Message
from qwen_agent.memory import Memory
from qwen_agent.settings import MAX_LLM_CALL_PER_RUN
from qwen_agent.tools import BaseTool
from qwen_agent.utils.utils import extract_files_from_messages

# Import Langfuse for tracing
try:
    import langfuse
    from langfuse.decorators import observe
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False


class FnCallAgent(Agent):
    """This is a widely applicable function call agent integrated with llm and tool use ability."""

    def __init__(self,
                 function_list: Optional[List[Union[str, Dict, BaseTool]]] = None,
                 llm: Optional[Union[Dict, BaseChatModel]] = None,
                 system_message: Optional[str] = DEFAULT_SYSTEM_MESSAGE,
                 name: Optional[str] = None,
                 description: Optional[str] = None,
                 files: Optional[List[str]] = None,
                 **kwargs):
        """Initialization the agent.

        Args:
            function_list: One list of tool name, tool configuration or Tool object,
              such as 'code_interpreter', {'name': 'code_interpreter', 'timeout': 10}, or CodeInterpreter().
            llm: The LLM model configuration or LLM model object.
              Set the configuration as {'model': '', 'api_key': '', 'model_server': ''}.
            system_message: The specified system message for LLM chat.
            name: The name of this agent.
            description: The description of this agent, which will be used for multi_agent.
            files: A file url list. The initialized files for the agent.
        """
        super().__init__(function_list=function_list,
                         llm=llm,
                         system_message=system_message,
                         name=name,
                         description=description)

        if not hasattr(self, 'mem'):
            # Default to use Memory to manage files
            if 'qwq' in self.llm.model.lower() or 'qvq' in self.llm.model.lower():
                if 'dashscope' in self.llm.model_type:
                    mem_llm = {
                        'model': 'qwen-turbo-latest',
                        'model_type': 'qwen_dashscope',
                        'generate_cfg': {
                            'max_input_tokens': 30000
                        }
                    }
                else:
                    mem_llm = None
            else:
                mem_llm = self.llm
            self.mem = Memory(llm=mem_llm, files=files, **kwargs)

        # Initialize Langfuse if available
        self.langfuse = None
        if LANGFUSE_AVAILABLE:
            # Try to initialize Langfuse from environment variables
            public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
            secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
            host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

            if public_key and secret_key:
                try:
                    self.langfuse = langfuse.Langfuse(
                        public_key=public_key,
                        secret_key=secret_key,
                        host=host,
                        debug=os.environ.get("LANGFUSE_DEBUG", "False").lower() == "true"
                    )
                except Exception as e:
                    print(f"Failed to initialize Langfuse: {e}")

    def _run(self, messages: List[Message], lang: Literal['en', 'zh'] = 'en', **kwargs) -> Iterator[List[Message]]:
        messages = copy.deepcopy(messages)
        num_llm_calls_available = MAX_LLM_CALL_PER_RUN
        response = []

        # Start tracing with Langfuse
        trace = None
        if self.langfuse:
            trace_id = kwargs.get("trace_id", None)
            trace_name = f"{self.name or 'FnCallAgent'}_run"

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
                "agent_name": self.name or "FnCallAgent",
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
                    input=trace_input,  # Only include actual input
                    metadata=trace_metadata  # Put full history in metadata
                )
            else:
                trace = self.langfuse.trace(
                    name=trace_name,
                    input=trace_input,  # Only include actual input
                    metadata=trace_metadata  # Put full history in metadata
                )

        try:
            while True and num_llm_calls_available > 0:
                num_llm_calls_available -= 1

                # Start LLM span in Langfuse
                llm_span = None
                if self.langfuse and trace:
                    # For LLM calls, the input is the complete conversation context
                    # because that's what's fed to the model
                    llm_input = {
                        "messages": [msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in messages],
                        "functions": [func.function for func in self.function_map.values()],
                        "extra_generate_cfg": {"lang": lang}
                    }

                    llm_span = trace.span(
                        name="llm_call",
                        input=llm_input,  # For LLM, input is the full context
                    )

                extra_generate_cfg = {'lang': lang}
                if kwargs.get('seed') is not None:
                    extra_generate_cfg['seed'] = kwargs['seed']
                output_stream = self._call_llm(messages=messages,
                                            functions=[func.function for func in self.function_map.values()],
                                            extra_generate_cfg=extra_generate_cfg)
                output: List[Message] = []
                for output in output_stream:
                    if output:
                        yield response + output

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

                if output:
                    response.extend(output)
                    messages.extend(output)
                    used_any_tool = False
                    for out in output:
                        use_tool, tool_name, tool_args, _ = self._detect_tool(out)
                        if use_tool:
                            # Start Tool span in Langfuse
                            tool_span = None
                            if self.langfuse and trace:
                                # For tool calls, the input is the specific tool arguments
                                tool_span = trace.span(
                                    name=f"tool_{tool_name}",
                                    input={
                                        "tool_name": tool_name,
                                        "tool_args": tool_args,
                                    },
                                )

                            tool_result = self._call_tool(tool_name, tool_args,
                                                        messages=messages,
                                                        trace=trace if self.langfuse else None,
                                                        **kwargs)

                            # End Tool span in Langfuse
                            if self.langfuse and trace and tool_span:
                                tool_span.end(output={"result": tool_result})

                            fn_msg = Message(
                                role=FUNCTION,
                                name=tool_name,
                                content=tool_result,
                            )
                            messages.append(fn_msg)
                            response.append(fn_msg)
                            yield response
                            used_any_tool = True
                    if not used_any_tool:
                        break

            # End the trace successfully - Update to use trace.update for Langfuse v2+
            if self.langfuse and trace:
                try:
                    serializable_responses = [msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in response]

                    # Don't include full conversation in input for final update
                    # Only include original input and any updates to it
                    trace.update(
                        # No need to update input in the final step
                        output={
                            "response": serializable_responses
                        },
                        metadata={
                            "final_conversation": [msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in messages]
                        },
                        status="success"
                    )
                except Exception as e:
                    print(f"Failed to update Langfuse trace: {e}")

        except Exception as e:
            # End the trace with error if there was an exception - Update to use trace.update for Langfuse v2+
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

        yield response

    def _call_tool(self, tool_name: str, tool_args: Union[str, dict] = '{}', **kwargs) -> str:
        # Extract trace from kwargs if provided
        trace = kwargs.pop("trace", None)

        # Start Tool execution span in Langfuse
        tool_execution_span = None
        if self.langfuse and trace:
            # For tool execution, input is just the specific arguments and tool info
            span_input = {
                "tool_name": tool_name,
                "tool_args": tool_args,
            }

            tool_execution_span = trace.span(
                name=f"tool_execution_{tool_name}",
                input=span_input,
                metadata={
                    "tool_definition": self.function_map[tool_name].function if tool_name in self.function_map else None
                }
            )

        try:
            if tool_name not in self.function_map:
                result = f'Tool {tool_name} does not exists.'
            else:
                # Temporary plan: Check if it is necessary to transfer files to the tool
                # Todo: This should be changed to parameter passing, and the file URL should be determined by the model
                if self.function_map[tool_name].file_access:
                    assert 'messages' in kwargs
                    files = extract_files_from_messages(kwargs['messages'], include_images=True) + self.mem.system_files
                    result = super()._call_tool(tool_name, tool_args, files=files, **kwargs)
                else:
                    result = super()._call_tool(tool_name, tool_args, **kwargs)

            # End tool execution span in Langfuse
            if self.langfuse and trace and tool_execution_span:
                tool_execution_span.end(output={"result": result})

            return result
        except Exception as e:
            # End tool execution span with error if there was an exception
            if self.langfuse and trace and tool_execution_span:
                tool_execution_span.end(
                    error={
                        "message": str(e),
                        "type": type(e).__name__
                    }
                )
            raise
