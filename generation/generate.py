from __future__ import annotations

from openai import OpenAI

from generation.prompts import GENERATION_SYSTEM_PROMPT, build_user_prompt


def generate_answer(client: OpenAI, model: str, question: str, ranked_chunks: list[dict]) -> str:
    user_prompt = build_user_prompt(question, ranked_chunks)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content.strip()
