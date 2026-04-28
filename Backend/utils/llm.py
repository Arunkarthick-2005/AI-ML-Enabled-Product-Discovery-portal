from llama_cpp import Llama

LLM = Llama(
    model_path=r"C:\Users\arunkarthick.l\Documents\PoC\Backend\models\Quantized Mistral Model\mistral-7b-instruct-v0.3-q4_k_m.gguf",
    n_ctx=4096,
    n_threads=8,     # adjust to your CPU
    temperature=0.3, # low → factual
    verbose=False
)

def generate(prompt: str) -> str:
    output = LLM(
        prompt,
        max_tokens=1024,
        stop=["</s>"]
    )
    return output["choices"][0]["text"].strip()