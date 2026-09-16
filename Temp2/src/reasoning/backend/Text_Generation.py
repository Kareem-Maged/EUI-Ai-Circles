import json
import torch

from transformers import (
    pipeline,
    AutoTokenizer,
    AutoModelForCausalLM,
)

from src.retrieval.main import retrieve_context


# ---- paths ----
CLASSIFIER_DIR = "D:\Programming\Sawa_Ed\Version 2\Sawa-Ed\EUI-Hackathon-Ai-Circles-main\EUI-Hackathon-Ai-Circles-main\src\Models\student_text_classifier"
GENERATOR_DIR = "D:\Programming\Sawa_Ed\Version 2\Sawa-Ed\EUI-Hackathon-Ai-Circles-main\EUI-Hackathon-Ai-Circles-main\src\Models\sawa_ed_qwen3_1.7b_merged_final"


# ---- load classifier ----
classifier = pipeline(
    "text-classification",
    model=CLASSIFIER_DIR,
    tokenizer=CLASSIFIER_DIR,
)


# ---- load generator ----
tokenizer = AutoTokenizer.from_pretrained(
    GENERATOR_DIR
)

model = AutoModelForCausalLM.from_pretrained(
    GENERATOR_DIR,
    torch_dtype=(
        torch.bfloat16
        if torch.cuda.is_available()
        else torch.float32
    ),
    device_map=(
        "auto"
        if torch.cuda.is_available()
        else None
    ),
)

model.eval()


# ---- load the exact training-time system prompt ----
with open(
    f"{GENERATOR_DIR}\\training_config.json",
    encoding="utf-8",
) as f:
    SYSTEM_TEMPLATE = json.load(f)["system_template"]


def generate_response(
    category: str,
    context: str,
    instruction: str,
    max_new_tokens: int = 180,
) -> str:

    messages = [
        {
            "role": "system",
            "content": SYSTEM_TEMPLATE.format(
                category=category,
                context=context.strip(),
            ),
        },
        {
            "role": "user",
            "content": instruction.strip(),
        },
    ]

    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    ).to(model.device)

    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=(
                tokenizer.pad_token_id
                or tokenizer.eos_token_id
            ),
        )

    response = tokenizer.decode(
        out[0][inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True,
    )

    if "<think>" in response and "</think>" in response:
        response = response.split("</think>")[-1]

    return response.strip()


def tutor_reply(instruction: str) -> dict:
    """
    Full Sawa-Ed pipeline:
    1. Retrieve relevant curriculum context.
    2. Classify the student's message.
    3. Generate the tutor's response using the retrieved context.
    """

    # ---- retrieve context ----
    context = retrieve_context(
        instruction,
        n_results=8,
    )

    # ---- classify student's message ----
    cls_result = classifier(instruction)[0]

    category = cls_result["label"]
    confidence = cls_result["score"]

    # ---- generate tutor response ----
    reply = generate_response(
        category=category,
        context=context,
        instruction=instruction,
    )

    return {
        "instruction": instruction,
        "predicted_category": category,
        "classifier_confidence": confidence,
        "context": context,
        "response": reply,
    }


if __name__ == "__main__":

    print(
        "Sawa-Ed tutor test loop. "
        "Type 'n' when asked to stop.\n"
    )

    while True:

        instruction = input(
            "Student instruction: "
        ).strip()

        if not instruction:
            continue

        result = tutor_reply(instruction)

        # print(
        #     json.dumps(
        #         result,
        #         ensure_ascii=False,
        #         indent=2,
        #     )
        # )
        print("\nSawa-Ed:")
        print(result["response"])

        cont = input(
            "\nContinue? (y/n): "
        ).strip().lower()

        print()

        if cont != "y":
            print("Stopped.")
            break