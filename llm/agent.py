"""手写 ReAct 循环：思考 -> 行动 -> 观察 -> 继续，直到回答"""
import ast
import json
import re

from llm.client import chat_messages
from llm.tools import execute_tool, get_time, tool_list_text

SYSTEM_PROMPT = f"""你是一个会使用工具的 AI 助手，可以回答用户问题。

可用工具：
{tool_list_text()}

处理问题时按下面的格式逐步输出：

思考: <你打算怎么做>
行动: <工具名>
行动输入: <JSON 格式的参数，没有参数就写 {{}}>

工具执行后，你会看到「观察: <结果>」，然后继续 思考 -> 行动。

当你已经得到答案、或这个问题不需要调用工具时，直接输出：

回答: <最终答案>

规则：
1. 行动只能从工具列表中选择。
2. 行动输入必须是合法 JSON。
3. 一次只输出一个「思考 / 行动 / 行动输入」，或直接输出「回答」。
4. 当前日期时间是动态信息，你的训练数据里没有真实时间；只要问题涉及时间/日期/年份，
   必须先调用 get_time 获取，禁止根据训练知识猜测或编造年份。
5. 如果「观察」里出现「工具执行出错」，先修正参数重试一次；仍失败就如实告诉用户。

示例（「观察」由程序返回，你不需要输出观察）：

用户: 现在几点了？
思考: 我不知道当前时间，必须调用工具。
行动: get_time
行动输入: {{}}

用户: 12345 + 67890 等于多少？
思考: 大数加法必须用工具确保准确。
行动: add
行动输入: {{"a": 12345, "b": 67890}}
"""

ANSWER_RE = re.compile(r"回答[:：]\s*(.+)$", re.S)
ACTION_RE = re.compile(r"行动[:：]\s*([A-Za-z_][A-Za-z0-9_]*)")
ARGS_RE = re.compile(r"行动输入[:：]\s*(.*?)(?=\n\s*(?:思考|行动|回答)[:：]|\Z)", re.S)

TIME_KEYWORDS = (
    "几点", "时间", "日期", "几号", "年份", "现在几", "几点几分",
    "now", "time", "date", "current time", "what time",
)


def _mentions_time(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in TIME_KEYWORDS)


def parse_args(text: str):
    """把「行动输入」后面的内容解析成参数 dict / list / 原始值"""
    match = ARGS_RE.search(text)
    if not match:
        return {}

    raw = match.group(1).strip().strip("`")
    if not raw:
        return {}

    # 如果 JSON 跨行（模型偶尔会换行写），把括号补齐
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        if raw.count(open_ch) > raw.count(close_ch):
            raw += close_ch * (raw.count(open_ch) - raw.count(close_ch))

    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(raw)
        except Exception:
            continue

    # 兜底：去掉引号后当普通字符串
    return raw.strip("\"'")


def parse_action(reply: str):
    """解析模型回复。返回 (工具名, 参数, 最终答案)。
    有「回答」或没有「行动」时，视为已得到最终答案。"""
    answer = ANSWER_RE.search(reply)
    if answer:
        return None, None, answer.group(1).strip()

    action = ACTION_RE.search(reply)
    if action:
        return action.group(1), parse_args(reply), None

    # 模型没按格式输出：整个回复当作最终答案
    return None, None, reply.strip()


def run_agent(user_message: str, max_steps: int = 5, verbose: bool = True):
    """跑 ReAct 循环，返回 (最终答案, 用了几步)"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    time_attempted = False 

    for step in range(1, max_steps + 1):
        if verbose:
            print(f"\n[step {step}] 调用模型...")
        reply = chat_messages(messages, stream=False)
        messages.append({"role": "assistant", "content": reply})

        tool_name, args, final = parse_action(reply)
        if final is not None:
            # 兜底：问题涉及时间，但模型全程没调 get_time（防止它凭记忆编年份）
            if _mentions_time(user_message) and not time_attempted:
                observation = (
                    f"观察: 问题涉及时间，程序已自动调用 get_time：{get_time()}。"
                    "若用户要求的是其他时区，请如实告知暂不支持。"
                )
                time_attempted = True
                if verbose:
                    print(f"[step {step}] 程序兜底 {observation}")
                messages.append({"role": "user", "content": observation})
                continue
            if verbose:
                print(f"[step {step}] 得到最终回答")
            return final, step

        if tool_name == "get_time":
            time_attempted = True

        result, error = execute_tool(tool_name, args)
        if error:
            observation = f"观察: 工具执行出错——{error}，请修正后重试或直接给出回答。"
        else:
            observation = f"观察: {result}"
        if verbose:
            print(f"[step {step}] 行动: {tool_name} 参数: {args}")
            print(f"[step {step}] {observation}")

        messages.append({"role": "user", "content": observation})

    return "已达最大步数，未能得出最终答案。", max_steps


if __name__ == "__main__":
    print("ReAct Agent（输入 exit / 退出 结束）")
    while True:
        user_input = input("\n你: ").strip()
        if user_input.lower() in ("exit", "quit", "退出"):
            break
        if not user_input:
            continue
        answer, steps = run_agent(user_input)
        print(f"\n[Agent] {answer}（共 {steps} 步）")
