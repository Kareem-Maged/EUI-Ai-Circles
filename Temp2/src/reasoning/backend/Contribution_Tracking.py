from transformers import pipeline

# ---- paths ----
# Hardcoded absolute path, same style as Text_Generation.py for now.
CLASSIFIER_DIR = "D:\Programming\Sawa_Ed\Version 2\Sawa-Ed\EUI-Hackathon-Ai-Circles-main\EUI-Hackathon-Ai-Circles-main\src\Models\contribution_tier_classifier"

# ---- load classifier ----
classifier = pipeline(
    "text-classification",
    model=CLASSIFIER_DIR,
    tokenizer=CLASSIFIER_DIR,
)


def tracker(message: str) -> dict:
    """
    Classifies a single group-chat message into a contribution tier:
    Substantive / Procedural / Social.

    Note: "Passive" is never produced here -- it means no message was sent
    at all, which is an application-logic case (not something this
    classifier, which only ever sees actual text, can decide).
    """
    result = classifier(message.strip())[0]

    return {
        "message": message,
        "tier": result["label"],
        "confidence": result["score"],
    }


# if __name__ == "__main__":
#     print("Contribution tier tracker test loop. Type 'n' when asked to stop.\n")

#     while True:
#         message = input("Message: ").strip()
#         result = tracker(message)
#         print(result)

#         cont = input("\nContinue? (y/n): ").strip().lower()
#         print()
#         if cont != "y":
#             print("Stopped.")
#             break
