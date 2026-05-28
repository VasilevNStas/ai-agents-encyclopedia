---
module: 8b
title: Fine-tuning Hands-On — LoRA на практике
tags: [course, fine-tuning, lora, practice, hands-on]
---

# Практикум: LoRA Fine-tuning своими руками

> [!quote] Ключевая идея
> Теория fine-tuning — в модуле выше. Здесь — **практика**: ты возьмёшь маленькую open-source модель (1.5B параметров), соберёшь датасет, натренируешь LoRA-адаптер и проверишь результат. Всё на локальной машине, без GPU в облаке.

---

## 1. Окружение

```bash
pip install torch transformers datasets peft accelerate bitsandbytes
pip install trl  # transformer reinforcement learning
```

**Требования к железу:** 8GB RAM + 4GB VRAM (или CPU-only режим — медленно, но работает).

---

## 2. Датасет: форматирование ответов агента

Соберём 200 примеров: как агент должен отвечать в формате JSON со строгой схемой.

```python
from datasets import Dataset
import json

# Пример данных: сырой запрос → отформатированный ответ агента
training_data = [
    {
        "instruction": "Как сбросить пароль?",
        "output": json.dumps({
            "action": "search",
            "query": "password reset guide",
            "parameters": {"user_id": "auto"},
            "response": "Перейдите в Settings → Security → Reset Password"
        }, ensure_ascii=False),
    },
    {
        "instruction": "Найди последний заказ пользователя",
        "output": json.dumps({
            "action": "query_database",
            "query": "SELECT * FROM orders ORDER BY created_at DESC LIMIT 1",
            "response": "Последний заказ: #12345 от 15 мая"
        }, ensure_ascii=False),
    },
    # ... ещё 198 примеров
]

# Формат для LoRA
def format_example(example):
    return {
        "text": f"### Instruction:\n{example['instruction']}\n\n### Response:\n{example['output']}",
    }

dataset = Dataset.from_list(training_data).map(format_example)
```

---

## 3. Загрузка модели и LoRA

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType
import torch

# Маленькая модель для экспериментов
model_name = "microsoft/Phi-3-mini-4k-instruct"  # 3.8B params

tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto" if torch.cuda.is_available() else "cpu",
)

# LoRA конфигурация
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=8,              # ранг адаптера (8 = маленький, 16 = средний)
    lora_alpha=32,    # scaling factor
    lora_dropout=0.05,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    bias="none",
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()  # Должно быть < 1% параметров
```

---

## 4. Тренировка

```python
from transformers import TrainingArguments, Trainer

training_args = TrainingArguments(
    output_dir="./lora-agent-output",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    num_train_epochs=3,
    learning_rate=2e-4,
    logging_steps=10,
    save_steps=50,
    evaluation_strategy="no",
    save_total_limit=2,
    remove_unused_columns=False,
    push_to_hub=False,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    tokenizer=tokenizer,
)

# Старт тренировки (~30-60 минут на CPU, ~5 минут на GPU)
trainer.train()

# Сохраняем адаптер
model.save_pretrained("./lora-agent-adapter")
tokenizer.save_pretrained("./lora-agent-adapter")
```

---

## 5. Инференс: сравниваем до и после

```python
from peft import PeftModel

# Базовая модель (без fine-tuning)
base_model = AutoModelForCausalLM.from_pretrained(model_name, device_map="auto")

# Модель с LoRA-адаптером
lora_model = PeftModel.from_pretrained(base_model, "./lora-agent-adapter")


def generate(model, instruction: str) -> str:
    prompt = f"### Instruction:\n{instruction}\n\n### Response:\n"
    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(
        **inputs,
        max_new_tokens=128,
        temperature=0.3,
        do_sample=True,
    )
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


# Сравнение
test = "Покажи историю платежей пользователя user_42"

print("=== BEFORE LoRA ===")
print(generate(base_model, test))

print("\n=== AFTER LoRA ===")
print(generate(lora_model, test))
```

**Ожидаемый результат:** до LoRA модель отвечает в свободной форме, после — строгим JSON.

---

## 6. Когда fine-tuning нужен агенту

- **Форматирование:** агент должен строго соблюдать JSON/XML схему
- **Tool use:** модель вызывает инструменты не в том формате
- **Style:** агент должен отвечать как бренд (тон, лексика)
- **Cost:** длинный few-shot заменяется одним промптом + адаптером

**Когда НЕ нужен:**
- Нужны новые фактические знания → RAG
- Нужно быстро протестировать гипотезу → prompting
- Мало данных (< 100 примеров) → prompting + few-shot

---

## Проверь себя

1. Запусти LoRA-тренировку на Phi-3-mini (или своём ноутбуке)
2. Сравни ответы до и после на 5 тестовых запросах
3. В чём разница? Какие улучшения?
4. Сколько VRAM занял процесс?
5. Сколько данных реально нужно, чтобы изменить поведение?

---

## Ссылки

- [[08-fine-tuning-pipeline]] — теория (LoRA, RLHF, DPO)
- [[../../ai-agents/08-decision-architecture/01-fine-tuning-rag-prompting]] — выбор подхода
