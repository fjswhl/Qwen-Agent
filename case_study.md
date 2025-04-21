# Agent 框架的基本组成单元

## 目录
- [Agent 类体系](#agent-类体系)
- [工具类体系](#工具类体系)
- [LLM 模型类体系](#llm-模型类体系)
- [类图](#类图)
  - [Agent](#agent)
  - [Tool](#tool)
  - [LLM](#llm)
- [FnCallAgent 的实现](#fncallagent-的实现)
  - [基本流程示例：画一只猫](#基本流程示例画一只猫)
    - [工具注册阶段](#工具注册阶段)
    - [Agent 初始化阶段](#agent-初始化阶段)
    - [用户输入处理阶段](#用户输入处理阶段)
    - [LLM 调用阶段](#llm-调用阶段)
    - [工具调用检测与执行阶段](#工具调用检测与执行阶段)
    - [工具结果处理阶段](#工具结果处理阶段)
    - [完整调用链路](#完整调用链路)
- [Mcp 的实现](#mcp-的实现)
  - [配置示例](#配置示例)
  - [MCP服务识别](#mcp服务识别)
  - [MCP服务管理机制](#mcp服务管理机制)
  - [工具动态注册和包装](#工具动态注册和包装)
  - [客户端连接和工具调用](#客户端连接和工具调用)
- [ReAct 的实现](#react-的实现)
  - [示例：MotiffAssistant](#示例motiffassistant)
    - [用户输入](#用户输入)
    - [Agent 实例化](#agent-实例化)
    - [提示词准备阶段](#提示词准备阶段)
    - [第一轮 LLM 调用与工具使用](#第一轮-llm-调用与工具使用)
    - [第二轮 LLM 调用与工具使用](#第二轮-llm-调用与工具使用)
    - [最终回答生成](#最终回答生成)
  - [数据流图](#数据流图)
  - [关键代码段执行顺序](#关键代码段执行顺序)
  - [ReAct 的提示词工程](#react-的提示词工程)


## Agent 类体系

- **Agent（抽象基类）**：所有 Agent 的基类，定义了 Agent 的基本接口和行为
- **BasicAgent**：最简单的 Agent 实现，只使用 LLM
- **FnCallAgent**：支持函数调用的 Agent
- **ReActChat**：使用 ReAct（推理和行动）格式的 Agent

## 工具类体系

- **BaseTool（抽象基类）**：所有工具的基类
- **BaseToolWithFileAccess**：具有文件访问能力的工具基类

## LLM 模型类体系

- **BaseChatModel（抽象基类）**：所有 LLM 模型的基类
- 各种具体的 LLM 模型实现

## 类图

### Agent

```text
+---------+------------------------+
|              Agent               |
+----------------------------------+
| + llm: BaseChatModel            |
| + function_map: dict            |
| + system_message: str           |
| + name: str                     |
| + description: str              |
| + run(messages): Iterator       |
| + run_nonstream(messages)       |
| + _run(messages): Iterator      |
| + _call_llm(messages)           |
| + _call_tool(tool_name, args)   |
| + _init_tool(tool)              |
| + _detect_tool(message)         |
+----------------------------------+
          ^
          |
+---------+------------------------+
|           BasicAgent             |
+----------------------------------+
| + _run(messages): Iterator      |
+----------------------------------+
          ^
          |
+---------+------------------------+     +------------------------+
|           FnCallAgent            |     |        Memory         |
+----------------------------------+     +------------------------+
| + files: list                    |<----| + cfg: dict           |
| + mem: Memory                    |     | + max_ref_token: int  |
| + _run(messages): Iterator       |     | + parser_page_size    |
| + _run_with_tool()               |     | + rag_searchers: list |
| + _prepend_file_prompt()         |     | + _run(): Iterator    |
+----------------------------------+     | + get_rag_files()     |
          ^                              +------------------------+
          |
     +----+----+----------------------+-------------------+
     |         |                      |                   |
+----+----+ +--+------+       +-------+------+      +----+----------+
|Assistant| |ReactChat|       |RouterAgent   |      |GroupChat      |
+----+----+ +----+----+       +--------------+      +---------------+
     |           |            |+ router_prompt|      |+ agents: list |
     |           |            |+ _run()       |      |+ _run()       |
     |           |            +--------------+      |+ summarize()   |
     |           |                                  +---------------+
+----+----+  +---+------+
|DialogueRA|  |TIRAgent  |
+---------+  +----------+
```

### Tool

```text
+-------------------------+
|       BaseTool          |
+-------------------------+
| + name: str             |
| + description: str      |
| + parameters: list/dict |
| + cfg: dict             |
|                         |
| + call()                |
| + _verify_json_format_  |
|   args()                |
| + function              |
| + name_for_human        |
| + args_format           |
| + file_access: bool     |
+-------------------------+
          ^
          |
          |
+---------+------------------+
|    BaseToolWithFileAccess  |
+----------------------------+
| + work_dir: str            |
| + file_access: bool = True |
| + call(params, files)      |
+----------------------------+
          ^
          |
     +----+----+-------------------+-------------------+-------------------+
     |         |                   |                   |                   |
+----+----+ +--+-----------+ +-----+-------+  +-------+-----+  +----------+-----+
|CodeInter| |DocParser     | |WebSearch    |  |Storage      |  |Retrieval       |
|preter   | |              | |             |  |             |  |                |
+---------+ +--------------+ +-------------+  +-------------+  +----------------+
|+ python_| |+ max_ref_token |+ search_api   |+ path: str    |+ max_ref_token  |
|  executor| |+ parser_page_ |+ api_key      |+ call()       |+ parser_page_size|
|+ call()  | |  size         |+ call()       |+ _upload()    |+ rag_searchers   |
|          | |+ call()       |               |+ _download()  |+ call()          |
|          | |+ _parse_docs()|               |+ _delete()    |+ _search_files() |
+---------+ +--------------+ +-------------+  +-------------+  +----------------+
```

### LLM

```text
+-----------------------------------------------+
|                  BaseChatModel                |
+-----------------------------------------------+
| # 属性                                         |
| + model: str                                  |
| + generate_cfg: dict                          |
| + max_retries: int                            |
| + cache                                       |
| + model_type: str                             |
|                                               |
| # 特性                                         |
| + support_multimodal_input: bool              |
| + support_multimodal_output: bool             |
| + support_audio_input: bool                   |
|                                               |
| # 方法                                         |
| + __init__(cfg: dict)                         |
| + quick_chat(prompt: str): str                |
| + chat(messages, functions, stream): Iterator |
| + _chat(): 抽象方法                            |
| + _chat_with_functions(): 抽象方法             |
| + _continue_assistant_response()              |
| + _chat_stream(): 抽象方法                     |
| + _chat_no_stream(): 抽象方法                  |
| + _preprocess_messages()                      |
| + _postprocess_messages()                     |
| + quick_chat_oai()                            |
+-----------------------------------------------+
                     ^
                     |
        +------------+-----------------------------+
        |            |             |              |
+-------+------+ +---+--------+ +--+---------+ +-+------------+
| OpenAIModel  | | DashScope  | | OpenVino   | | AzureModel   |
+-------+------+ +------------+ +------------+ +--------------+
| + api_key    | | + api_key  | | + model_path| | + api_version|
| + api_base   | | + model    | | + session   | | + api_key    |
| + _chat()    | | + _chat()  | | + _chat()   | | + deployment |
| + _chat_with_| | + _chat_with| | + _chat_with| | + _chat()    |
|   functions()| |   functions()| |   functions()| | + _chat_with_|
| + _chat_stream| | + _chat_stream| + _chat_stream| |   functions()|
| + _chat_no_  | | + _chat_no_  | | + _chat_no_  | +--------------+
|   stream()   | |   stream()   | |   stream()   |
+-------------+ +-------------+ +-------------+
```

# FnCallAgent 的实现

## 基本流程示例：画一只猫

### 工具注册阶段

#### 工具类定义与注册

```python
@register_tool('image_gen')
class ImageGen(BaseTool):
    description = 'AI绘画（图像生成）服务，输入文本描述和图像分辨率，返回根据文本信息绘制的图片URL。'
    parameters = [{
        'name': 'prompt',
        'type': 'string',
        'description': '详细描述了希望生成的图像具有什么内容，例如人物、环境、动作等细节描述，使用英文',
        'required': True
    }, {
        'name': 'resolution',
        'type': 'string',
        'description': '格式是 数字*数字，表示希望生成的图像的分辨率大小，选项有[1024*1024, 720*1280, 1280*720]'
    }]
```

#### 注册机制

`@register_tool('image_gen')` 装饰器将 ImageGen 类注册到全局的 TOOL_REGISTRY 字典中。

```python
def register_tool(name, allow_overwrite=False):
    def decorator(cls):
        if name in TOOL_REGISTRY:
            if allow_overwrite:
                logger.warning(f'Tool `{name}` already exists! Overwriting with class {cls}.')
            else:
                raise ValueError(f'Tool `{name}` already exists! Please ensure that the tool name is unique.')
        if cls.name and (cls.name != name):
            raise ValueError(f'{cls.__name__}.name="{cls.name}" conflicts with @register_tool(name="{name}").')
        cls.name = name
        TOOL_REGISTRY[name] = cls
        return cls
    return decorator
```

### Agent 初始化阶段

#### 创建 Agent 实例

创建 FnCallAgent 实例时，通过 function_list 参数传入工具列表（可以是工具名、配置或实例）。

#### 工具初始化

Agent 类的 __init__ 方法会遍历 function_list 并通过 _init_tool 方法初始化每个工具：

```python
def _init_tool(self, tool: Union[str, Dict, BaseTool]):
    if isinstance(tool, BaseTool):
        tool_name = tool.name
        self.function_map[tool_name] = tool
    elif isinstance(tool, dict) and 'mcpServers' in tool:
        tools = MCPManager().initConfig(tool)
        for tool in tools:
            self.function_map[tool.name] = tool
    else:
        if isinstance(tool, dict):
            tool_name = tool['name']
            tool_cfg = tool
        else:
            tool_name = tool
            tool_cfg = None
        if tool_name not in TOOL_REGISTRY:
            raise ValueError(f'Tool {tool_name} is not registered.')
        self.function_map[tool_name] = TOOL_REGISTRY[tool_name](tool_cfg)
```

这个过程会查找 TOOL_REGISTRY 中的工具类，实例化并存入 function_map。

### 用户输入处理阶段

#### 用户输入
用户输入"画一只猫"。

#### 构建消息
创建一个 Message 对象并添加到消息列表中：

```python
messages = [Message(role="user", content="画一只猫")]
```

#### Agent 运行
调用 agent.run(messages) 开始处理消息，内部会调用 _run 方法（在 FnCallAgent 中实现）。

### LLM 调用阶段

#### 调用 LLM
FnCallAgent 的 _run 方法会调用 _call_llm 并传入消息和函数列表：

```python
output_stream = self._call_llm(
    messages=messages,
    functions=[func.function for func in self.function_map.values()],
    extra_generate_cfg=extra_generate_cfg
)
```

#### 准备工具描述
将 function_map 中的所有工具转换为可以被 LLM 理解的函数描述格式，包括名称、描述和参数。

#### LLM 处理
LLM 会接收到消息和函数列表，理解用户的"画一只猫"意图需要生成图像，并决定调用 image_gen 工具。

#### 生成函数调用
LLM 返回的响应包含 function_call 字段，指定要调用的工具和参数：

```python
{
    "role": "assistant",
    "function_call": {
        "name": "image_gen",
        "arguments": "{\"prompt\": \"a cute cat\"}"
    }
}
```

### 工具调用检测与执行阶段

#### 工具调用检测
FnCallAgent 的 _run 方法通过 _detect_tool 检测 LLM 是否请求调用工具：

```python
use_tool, tool_name, tool_args, _ = self._detect_tool(out)
```

检测到 function_call 中有 image_gen 和相应参数：

```python
def _detect_tool(self, message: Message) -> Tuple[bool, str, str, str]:
    func_name = None
    func_args = None
    if message.function_call:
        func_call = message.function_call
        func_name = func_call.name
        func_args = func_call.arguments
    return (func_name is not None), func_name, func_args, message.content
```

#### 调用工具
如果检测到需要调用工具，会调用 _call_tool 方法：

```python
tool_result = self._call_tool(tool_name, tool_args, messages=messages, **kwargs)

def call(self, params: Union[str, dict], **kwargs) -> str:
    params = self._verify_json_format_args(params)
    prompt = params['prompt']  # 这里是 "a cute cat"
    prompt = urllib.parse.quote(prompt)
    return json.dumps({'image_url': f'https://image.pollinations.ai/prompt/{prompt}'}, ensure_ascii=False)
```

### 工具结果处理阶段

#### 创建函数返回消息
将工具返回的结果封装为 FUNCTION 角色的消息：

```python
fn_msg = Message(
    role=FUNCTION,
    name=tool_name,
    content=tool_result,
)
```

#### 添加到消息列表
将函数返回消息添加到消息列表和响应中：

```python
messages.append(fn_msg)
response.append(fn_msg)
```

#### 继续 LLM 对话
在下一轮循环中，LLM 会看到工具的执行结果，并可能基于结果生成后续回应。

### 完整调用链路

```text
+-------------------------+
| 用户输入请求             |
| (例如："画一只猫")        |
+------------+------------+
             |
             v
+-------------------------+
| Agent初始化              |
| 工具注册到TOOL_REGISTRY   |
+------------+------------+
             |
             v
+-------------------------+
| agent.run(messages)     |
| 处理用户输入              |
+------------+------------+
             |
             v
+-------------------------+
| FnCallAgent._run()      |
| 运行主对话循环            |
+------------+------------+
             |
             v
+-------------------------+
| 工具描述转换              |
| func.function提取描述     |
| name,description,parameters|
+------------+------------+
             |
             v
+-------------------------+
| _call_llm(messages,     |
| functions=[...])        |
| 向LLM发送消息和工具描述    |
+------------+------------+
             |
             v
+-------------------------+
| LLM处理输入和工具描述      |
| (分析用户意图)            |
+------------+------------+
             |
             v
+-------------------------+
| LLM返回带function_call   |
| 的响应                   |
| (决定调用image_gen工具)   |
+------------+------------+
             |
             v
+-------------------------+
| _detect_tool(message)   |
| 检测是否需要调用工具       |
+------------+------------+
             |
             v
+-------------------------+
| _call_tool(tool_name,   |
| tool_args)              |
| 调用特定工具              |
+------------+------------+
             |
             v
+-------------------------+
| 工具实例执行              |
| ImageGen.call(params)   |
| 执行工具逻辑              |
+------------+------------+
             |
             v
+-------------------------+
| 工具返回结果              |
| (图片生成URL)            |
+------------+------------+
             |
             v
+-------------------------+
| 创建function消息         |
| (role=FUNCTION)         |
| 添加到对话历史            |
+------------+------------+
             |
             v
+-------------------------+
| 继续对话或返回最终结果     |
+-------------------------+
```

# Mcp 的实现

## 配置示例

```python
tools = [{
    "mcpServers": {
        "sqlite": {  # 服务名称
            "command": "uvx",  # 启动命令
            "args": [  # 命令参数
                "mcp-server-sqlite",
                "--db-path",
                "test.db"
            ]
        }
    }
}]
```

## MCP服务识别

在初始化 tools 的过程中，会进行MCP服务识别：特别检查是否存在 mcpServers 键，如果有则进入MCP处理流程

```python
def _init_tool(self, tool: Union[str, Dict, BaseTool]):
    if isinstance(tool, BaseTool):
        # 处理直接传入的工具对象
        # ...
    elif isinstance(tool, dict) and 'mcpServers' in tool:
        # 处理MCP服务配置
        tools = MCPManager().initConfig(tool)
        for tool in tools:
            tool_name = tool.name
            if tool_name in self.function_map:
                logger.warning(f'Repeatedly adding tool {tool_name}, will use the newest tool in function list')
            self.function_map[tool_name] = tool
    else:
        # 处理其他工具类型
        # ...
```

## MCP服务管理机制

MCPManager 类（单例模式）负责管理所有MCP服务：

- **服务配置验证**：is_valid_mcp_servers() 方法验证配置格式是否正确
- **服务初始化**：initConfig() 方法启动服务并获取服务提供的工具
- **异步服务管理**：使用独立线程和事件循环管理MCP服务的异步通信

```python
def initConfig(self, config: Dict):
    logger.info(f'Initialize from config {config}. ')
    if not self.is_valid_mcp_servers(config):
        raise ValueError('Config format error')
    # 提交协程到事件循环并等待结果
    future = asyncio.run_coroutine_threadsafe(self.init_config_async(config), self.loop)
    try:
        result = future.result()
        return result
    except Exception as e:
        logger.info(f'Error executing function: {e}')
        return None
```

## 工具动态注册和包装

对于从MCP服务获取的每个工具：

- **工具标准化**：将工具的 inputSchema 转换为符合 function call 格式的 parameters
- **动态类创建**：为每个工具创建一个新的工具类，继承自 BaseTool
- **工具注册**：用 register_tool 装饰器注册工具，命名格式为 {server_name}-{tool_name}

```python
def create_tool_class(self, register_name, server_name, tool_name, tool_desc, tool_parameters):
    @register_tool(register_name)
    class ToolClass(BaseTool):
        description = tool_desc
        parameters = tool_parameters

        def call(self, params: Union[str, dict], **kwargs) -> str:
            tool_args = json.loads(params)
            # 获取MCP客户端并执行函数
            manager = MCPManager()
            client = manager.clients[server_name]
            future = asyncio.run_coroutine_threadsafe(
                client.execute_function(tool_name, tool_args), manager.loop)
            try:
                result = future.result()
                return result
            except Exception as e:
                logger.info(f'Error executing function: {e}')
                return None

    ToolClass.__name__ = f'{register_name}_Class'
    return ToolClass()
```

## 客户端连接和工具调用

MCPClient 类负责与MCP服务通信：

- **连接服务**：connection_server() 方法建立与MCP服务的连接
- **工具发现**：连接后自动获取服务提供的工具列表
- **工具执行**：execute_function() 方法调用MCP服务提供的工具功能

# ReAct 的实现

ReActChat 是 Qwen-Agent 中实现 ReAct（Reasoning and Acting）范式的核心类，它让大模型按照"思考-行动-观察-反思"的结构化思维方式解决问题。这是一种由提示词驱动的系统工程。

## 示例：MotiffAssistant

### 用户输入

用户请求：根据这个 Motiff 文档，在 /tmp 目录下依次创建多个 React 组件 https://beta.motiff.com/file/wG6EIu6Yoq6UwWYaBWTm32H?nodeId=2%3A5&type=design

### Agent 实例化

实例化一个 ReActChat 对象，并提供两个工具：

```python
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
```

### 提示词准备阶段

当 agent.run(messages) 被调用时，ReActChat 首先调用 _prepend_react_prompt 方法将用户消息转换为 ReAct 格式：

```text
Answer the following questions as best you can. You have access to the following tools:

motiff-get_motiff_node: Call this tool to interact with the motiff-get_motiff_node API. What is the motiff-get_motiff_node API useful for? Get a node from Motiff, the result is a complete and high-fidelity HTML page which implements the design of the node. Users may use the html to create a UI component.
Motiff is a vector design tool like Figma, where each node represents a part or whole of a UI design.
User might provide a URL like https://api.motiff.com/file/{docId}?nodeId={nodeId}&type=design. Parameters: {"type": "object", "properties": {"docId": {"type": "string"}, "nodeId": {"type": "string"}}, "required": ["docId", "nodeId"]}

motiff-create_react_project_template: Call this tool to interact with the motiff-create_react_project_template API. What is the motiff-create_react_project_template API useful for? Create a react project using predefined template when user request to create a project, And only call this tool once when previous get_motiff_node tool call succeed. Input directory should be an absolute path. After the project is created, you should run npm install directly in the input directory. Parameters: {"type": "object", "properties": {"projectName": {"type": "string"}, "directoryAsProjectRoot": {"type": "string"}}, "required": ["projectName", "directoryAsProjectRoot"]}

file_creator: Call this tool to interact with the file_creator API. What is the file_creator API useful for? 创建文件，接收参数：1. 文件路径 2. 文件内容 Parameters: {"type": "object", "properties": {"file_path": {"type": "string", "description": "文件的路径"}, "content": {"type": "string", "description": "文件的内容"}}, "required": ["file_path", "content"]}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [motiff-get_motiff_node,motiff-create_react_project_template,file_creator]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can be repeated zero or more times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: 根据这个 Motiff 文档，在 /tmp 目录下依次创建多个 React 组件 https://beta.motiff.com/file/wG6EIu6Yoq6UwWYaBWTm32H?nodeId=2%3A5&type=design
Thought:
```

这个提示词包含了可用工具的描述、响应格式和用户的原始问题。

### 第一轮 LLM 调用与工具使用

ReActChat 的 _run 方法开始第一轮 LLM 调用：

```python
# 初始化响应
response = "Thought: "

# 调用 LLM (流式输出)
for output in self._call_llm(messages=text_messages):
    if output:
        yield [Message(role="assistant", content=response + output[-1].content)]
```

#### LLM 第一次生成

```text
我需要首先调用 motiff-get_motiff_node API 来获取 Motiff 文档中的指定节点，并生成对应的 HTML 页面。然后，基于该 HTML 页面的内容，创建一个 React 项目模板，并在 /tmp 目录下生成相应的 React 组件。

Action: motiff-get_motiff_node
Action Input: {"docId": "wG6EIu6Yoq6UwWYaBWTm32H", "nodeId": "2:5"}
```

#### 工具调用检测与执行

```python
# 检测工具调用
has_action, action, action_input, thought = self._detect_tool(output[-1].content)
# 结果: has_action=True, action="motiff-get_motiff_node", action_input='{"docId": "wG6EIu6Yoq6UwWYaBWTm32H", "nodeId": "2:5"}'

# 执行工具调用
observation = self._call_tool(action, action_input, messages=messages)
# 实际调用 motiff-get_motiff_node 工具并获取结果
```

```text
// 工具请求
{
    tool_name: "motiff-get_motiff_node"
    tool_args: {
        docId: "wG6EIu6Yoq6UwWYaBWTm32H"
        nodeId: "2:5"
    }
}

// 工具返回
{
    "result": "...."
}
```

#### 添加观察结果到响应

```python
observation = f'\nObservation: {observation}\nThought: '
response += observation
yield [Message(role="assistant", content=response)]
```

现在响应变为：

```text
Thought: 我需要首先调用 motiff-get_motiff_node API 来获取 Motiff 文档中的指定节点，并生成了对应的 HTML 页面。然后，基于该 HTML 页面的内容，创建一个 React 项目模板，并在 /tmp 目录下生成相应的 React 组件。
Action: motiff-get_motiff_node
Action Input: {"docId": "wG6EIu6Yoq6UwWYaBWTm32H", "nodeId": "2:5"}
Observation:
{{html}}

Thought:
```

#### 更新提示内容

```python
text_messages[-1].content += thought + f'\nAction: {action}\nAction Input: {action_input}' + observation
```

这为下一轮 LLM 调用准备了上下文。

### 第二轮 LLM 调用与工具使用

继续循环，进行第二轮 LLM 调用：

#### LLM 第二次生成

```text
{{前面的消息}}
Thought: 我已成功获取了 Motiff 文档中的指定节点，并生成了对应的 HTML 页面。接下来，我将使用这个 HTML 页面的内容来创建一个 React 项目模板，并在 /tmp 目录下生成相应的 React 组件。

Action: motiff-create_react_project_template
Action Input: {"projectName": "CourtMasterReact", "directoryAsProjectRoot": "/tmp/CourtMasterReact"}
Observation:
```

继续调用工具、返回，然后拼接消息，现在的完整响应是:

```text
Thought: 我已成功获取了 Motiff 文档中的指定节点，并生成了对应的 HTML 页面。接下来，我将使用这个 HTML 页面的内容来创建一个 React 项目模板，并在 /tmp 目录下生成相应的 React 组件。

Action: motiff-create_react_project_template
Action Input: {"projectName": "CourtMasterReact", "directoryAsProjectRoot": "/tmp/CourtMasterReact"}
Observation:
{{ create project result }}
```

### 最终回答生成

第三轮 LLM 调用，由于所有信息都已获取，LLM 将提供最终答案：

#### LLM 第三次生成

```text
我已成功创建了一个名为 "CourtMasterReact" 的 React 项目，并将其放置在 /tmp/CourtMasterReact 目录下。现在，我需要根据从 Motiff 文档中获取的 HTML 页面内容来编写 React 组件。

...{{ 一切创建组件的计划 }}..

请确认是否同意这个计划，或者是否有特定的组件或功能您希望优先处理？
Thought: 确认了创建 React 组件的计划后，下一步是开始逐一创建这些组件，并将它们整合进项目中。
Final Answer: 我已经制定了一个详细的计划来基于 Motiff 设计文档创建 React 组件。该计划包括创建 Header、SearchBar、VenueCard、VenueList 和 Footer 组件。这些组件将被设计为可复用，并且可以接受必要的 props 来动态显示数据。此外，我还将使用 TypeScript 来提高代码的类型安全性。如果您同意这个计划，请告知我，以便我可以继续实施。如果有任何特定的需求或优先级，请随时告诉我。
```

#### 工具调用检测

```python
has_action, action, action_input, thought = self._detect_tool(output[-1].content)
# 结果: has_action=False，因为没有 Action: 标记
```

由于没有更多工具调用，循环结束，最终输出完整回答。

## 数据流图

```text
用户输入
  │
  ▼
[_prepend_react_prompt]─────┐
  │                         │
  ▼                         │
[_call_llm] ◄──────────┐    │
  │                    │    │
  ▼                    │    │
[_detect_tool]         │    │
  │                    │    │
  ├─无工具调用──►[结束]  │    │
  │                    │    │
  ├─有工具调用──►[_call_tool] │
  │                    │    │
  ▼                    │    │
[yield 观察结果]        │    │
  │                    │    │
  ▼                    │    │
[更新提示词]────────────┘    │
  │                         │
  └─────────────────────────┘
```

## 关键代码段执行顺序

1. 初始化响应变量：

```python
response: str = 'Thought: '
```

2. 进入主循环：

```python
while num_llm_calls_available > 0:
    num_llm_calls_available -= 1
```

3. LLM 调用与流式输出：

```python
output = []
for output in self._call_llm(messages=text_messages):
    if output:
        yield [Message(role=ASSISTANT, content=response + output[-1].content)]
```

4. 检测工具:

```python
has_action, action, action_input, thought = self._detect_tool(output[-1].content)
```

5. 工具执行：

```python
observation = self._call_tool(action, action_input, messages=messages, **kwargs)
observation = f'\nObservation: {observation}\nThought: '
```

6. 更新响应和上下文：

```python
response += observation
yield [Message(role=ASSISTANT, content=response)]
text_messages[-1].content += thought + f'\nAction: {action}\nAction Input: {action_input}' + observation
```

## ReAct 的提示词工程

### 结构化提示模板

使用预定义的 PROMPT_REACT 模板引导 LLM 遵循特定格式：

```python
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
```

### 工具描述格式化

使用标准化模板描述每个工具的功能和参数：

```python
TOOL_DESC = (
    '{name_for_model}: Call this tool to interact with the {name_for_human} API. '
    'What is the {name_for_human} API useful for? {description_for_model} Parameters: {parameters} {args_format}')
```

### 停止词设计

配置特定的停止词使 LLM 在关键点停止生成：

```python
self.extra_generate_cfg = merge_generate_cfgs(
    base_generate_cfg=self.extra_generate_cfg,
    new_generate_cfg={'stop': ['Observation:', 'Observation:\n']},
)
```
