from langchain_openai import ChatOpenAI
from utils.configs import OPENAI_API_KEY, DEEPSEEK_API_KEY

# gpt-4o-mini
model_gpt4omini = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.openai.com/v1",
    model="gpt-4o-mini",
    temperature=0.1,
)
# gpt-4.1
model_gpt41 = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.openai.com/v1",
    model="gpt-4.1",
    temperature=0.1,
)
# llama-3.3-70B
model_llama = ChatOpenAI(
    api_key="EMPTY",  # vLLM
    base_url="http://localhost:8000/v1",
    model="Meta-Llama-3.3-70B-Instruct", 
    temperature=0.1,
)
# deepseek-v3
model_deepseek = ChatOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
    model="deepseek-chat",
    temperature=0.1,
)
