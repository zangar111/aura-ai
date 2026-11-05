import sys
from pathlib import Path

# Тесты импортируют модули проекта из корня.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_row(subject="Блокчейн технологии_", stream="BT 1-2-L", **marks):
    return {"subject": subject, "stream": stream, "marks": marks}
