"""RSA 加密解密 - 与龙猫服务器通信使用"""

import base64
import json
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from backend.config import PRIVATE_KEY_PEM, PUBLIC_KEY_PEM


def rsa_encrypt(plaintext: str | dict[str, Any]) -> str:
    """
    使用 RSA 公钥加密数据（PKCS#1）。

    支持自动将 dict 序列化为 JSON 字符串。
    对于长消息，使用分块加密（每块最大 117 字节，对应 1024 位密钥）。
    """
    if isinstance(plaintext, dict):
        data = json.dumps(plaintext, ensure_ascii=False).encode("utf-8")
    else:
        data = plaintext.encode("utf-8")

    pub_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode())
    key_size = pub_key.key_size // 8
    max_chunk = key_size - 11  # PKCS#1 v1.5 padding overhead

    chunks: list[bytes] = []
    for i in range(0, len(data), max_chunk):
        chunk = data[i : i + max_chunk]
        encrypted = pub_key.encrypt(chunk, padding.PKCS1v15())
        chunks.append(encrypted)

    return base64.b64encode(b"".join(chunks)).decode("utf-8")


def rsa_decrypt(ciphertext: str) -> dict[str, Any]:
    """
    使用 RSA 私钥解密数据（PKCS#1）。

    支持单块和多块密文，返回解析后的 JSON dict。
    """
    encrypted_data = base64.b64decode(ciphertext)

    priv_key = serialization.load_pem_private_key(
        PRIVATE_KEY_PEM.encode(), password=None
    )
    key_size = priv_key.key_size // 8

    chunks: list[bytes] = []
    for i in range(0, len(encrypted_data), key_size):
        chunk = encrypted_data[i : i + key_size]
        decrypted = priv_key.decrypt(chunk, padding.PKCS1v15())
        chunks.append(decrypted)

    plaintext = b"".join(chunks).decode("utf-8")
    return json.loads(plaintext)


def try_decrypt_response(resp_text: str) -> dict[str, Any] | str:
    """
    尝试解析服务器响应。

    服务器响应可能是：
    1. 明文 JSON
    2. Base64 编码的 RSA 加密字符串
    3. 其他格式

    依次尝试解析，返回最合适的格式。
    """
    # 尝试直接解析 JSON
    try:
        return json.loads(resp_text)
    except json.JSONDecodeError:
        pass

    # 尝试 RSA 解密
    try:
        return rsa_decrypt(resp_text)
    except Exception:
        pass

    # 返回原始文本（前 200 字符）
    return {"raw_response": resp_text[:200]}
