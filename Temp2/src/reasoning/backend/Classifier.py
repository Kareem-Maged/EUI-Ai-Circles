OUTPUT_DIR ="src\Models\student_text_classifier"
from transformers import pipeline



classifier = pipeline(
    "text-classification",
    model=OUTPUT_DIR,
    tokenizer=OUTPUT_DIR
)

result = classifier("أنا جربت أعوض بـ x باربعة وطلع الطرفين متساويين.") #answer
print(result)