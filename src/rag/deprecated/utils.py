import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from openai import OpenAI


def extract_url_root_domain(url):
    """
    从 URL 中提取根域名
    例如:
    - https://www.example.com/path -> example.com
    - sub.example.co.uk -> example.co.uk
    """
    # 确保 URL 包含协议，如果没有则添加
    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    # 使用 urlparse 解析 URL
    parsed = urlparse(url).netloc
    if not parsed:
        parsed = url

    # 移除端口号(如果存在)
    parsed = parsed.split(":")[0]

    # 分割域名部分
    parts = parsed.split(".")

    # 处理特殊的二级域名，如 .co.uk, .com.cn 等
    if len(parts) > 2:
        if parts[-2] in ["co", "com", "org", "gov", "edu", "net"]:
            if parts[-1] in ["uk", "cn", "jp", "br", "in"]:
                return ".".join(parts[-3:])

    # 返回主域名部分（最后两部分）
    return ".".join(parts[-2:])


def get_clean_content(line):
    clean_line = re.sub(r"^[\*\-•#\d\.]+\s*", "", line).strip()
    clean_line = re.sub(r'^[\'"]|[\'"]$', "", clean_line).strip()
    if (clean_line.startswith('"') and clean_line.endswith('"')) or (
        clean_line.startswith("'") and clean_line.endswith("'")
    ):
        clean_line = clean_line[1:-1]
    return clean_line


def get_content_from_tag(content, tag, default_value=None):
    # 说明：
    # 1) (.*?) 懒惰匹配，尽量少匹配字符
    # 2) (?=(</tag>|<\w+|$)) 使用前瞻，意味着当后面紧跟 </tag> 或 <任意单词字符开头的标签> 或文本结束时，都停止匹配
    # 3) re.DOTALL 使得点号 . 可以匹配换行符
    pattern = rf"<{tag}>(.*?)(?=(</{tag}>|<\w+|$))"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return default_value


def get_response_from_llm(
    messages: List[Dict[str, Any]],
    client: OpenAI,
    model: str,
    stream: Optional[bool] = False,
    temperature: Optional[float] = 0.6,
    depth: int = 0,
):
    try:
        response = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, stream=stream
        )
        if hasattr(response.choices[0].message, "content") and response.choices[0].message.content:
            content = response.choices[0].message.content
        return {"content": content.strip()}
    except Exception as e:
        print(f"LLM API error: {e}")
        if "Input data may contain inappropriate content" in str(e):
            return {"content": ""}
        if "Error code: 400" in str(e):
            return {"content": ""}
        if depth < 512:
            time.sleep(1)
            return get_response_from_llm(
                messages=messages, client=client, model=model, stream=stream, temperature=temperature, depth=depth + 1
            )
        raise e
