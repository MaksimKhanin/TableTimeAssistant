"""
Скрипт для генерации промтов для AI-генерации изображений карточек.

Использование:
1. Генерация промтов: python scripts/generate_image_prompts.py --export
2. Обновление БД после добавления изображений: python scripts/generate_image_prompts.py --update

Промты сохраняются в image_prompts.csv в формате:
id,card_type,name,prompt,filename
"""
import argparse
import csv
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from grokhanika.db.database import make_engine, make_session_factory
from grokhanika.db.models import Card
from grokhanika.enums import CardType


# Промт-шаблоны по типам карточек
PROMPT_TEMPLATES = {
    CardType.CHARACTER.value: (
        "dark fantasy portrait of {name}, {description}, "
        "detailed character art, professional game card illustration, "
        "square aspect ratio, high quality, dramatic lighting"
    ),
    CardType.CREATURE.value: (
        "dark fantasy monster {name}, {description}, "
        "creature design, menacing, detailed texture, "
        "professional game card illustration, square aspect ratio, high quality"
    ),
    CardType.WEAPON.value: (
        "dark fantasy weapon {name}, {description}, "
        "item illustration, detailed craftsmanship, magical aura, "
        "professional game card art, square aspect ratio, high quality"
    ),
    CardType.ARMOR.value: (
        "dark fantasy armor {name}, {description}, "
        "equipment illustration, detailed metalwork, protective design, "
        "professional game card art, square aspect ratio, high quality"
    ),
    CardType.ITEM.value: (
        "dark fantasy item {name}, {description}, "
        "magical object, glowing effects, detailed props, "
        "professional game card art, square aspect ratio, high quality"
    ),
    CardType.SPELLBOOK.value: (
        "dark fantasy magic tome {name}, {description}, "
        "ancient book, magical runes, glowing energy, "
        "professional game card art, square aspect ratio, high quality"
    ),
    CardType.SCROLL.value: (
        "dark fantasy scroll {name}, {description}, "
        "ancient parchment, magical symbols, mystical aura, "
        "professional game card art, square aspect ratio, high quality"
    ),
    CardType.INSTRUMENT.value: (
        "dark fantasy musical instrument {name}, {description}, "
        "detailed craftsmanship, magical properties, bardic theme, "
        "professional game card art, square aspect ratio, high quality"
    ),
    CardType.SKILL.value: (
        "dark fantasy skill icon {name}, {description}, "
        "abstract representation, magical energy, symbolic design, "
        "professional game card art, square aspect ratio, high quality"
    ),
}

# Соответствие типов карточек именам папок (множественное число)
TYPE_TO_FOLDER = {
    CardType.CHARACTER.value: "characters",
    CardType.CREATURE.value: "creatures",
    CardType.WEAPON.value: "weapons",
    CardType.ARMOR.value: "armor",
    CardType.ITEM.value: "items",
    CardType.SPELLBOOK.value: "spellbooks",
    CardType.SCROLL.value: "scrolls",
    CardType.INSTRUMENT.value: "instruments",
    CardType.SKILL.value: "skills",
}


def slugify(text: str) -> str:
    """Преобразует текст в безопасное имя файла."""
    # Заменяем пробелы и спецсимволы на подчеркивания
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '_', text)
    return text[:50]  # Ограничиваем длину


def generate_filename(card: Card) -> str:
    """Генерирует имя файла для карточки."""
    name_slug = slugify(card.name)
    return f"{card.card_type}_{card.id}_{name_slug}.png"


def generate_prompt(card: Card) -> str:
    """Генерирует промт для карточки на основе типа и описания."""
    template = PROMPT_TEMPLATES.get(card.card_type, PROMPT_TEMPLATES[CardType.ITEM.value])
    
    name = card.name
    description = card.description if card.description else "generic fantasy design"
    
    # Ограничиваем длину описания для промта
    if len(description) > 200:
        description = description[:200] + "..."
    
    return template.format(name=name, description=description)


def export_prompts(output_file: str = "image_prompts.csv") -> None:
    """Экспортирует промты для всех карточек в CSV файл."""
    engine = make_engine()
    session_factory = make_session_factory(engine)
    session = session_factory()
    
    try:
        cards = session.query(Card).all()
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'card_type', 'name', 'description', 'prompt', 'filename'])
            
            for card in cards:
                prompt = generate_prompt(card)
                filename = generate_filename(card)
                
                writer.writerow([
                    card.id,
                    card.card_type,
                    card.name,
                    card.description or '',
                    prompt,
                    filename
                ])
        
        print(f"✓ Экспортировано {len(cards)} промтов в {output_file}")
        print(f"  Используйте этот файл для генерации изображений в AI-инструментах")
        
    finally:
        session.close()


def update_database(images_dir: str = "grokhanika/web/static/images/cards") -> None:
    """Обновляет image_id в БД на основе существующих файлов."""
    engine = make_engine()
    session_factory = make_session_factory(engine)
    session = session_factory()
    
    try:
        cards = session.query(Card).all()
        updated = 0
        
        for card in cards:
            # Определяем подпапку по типу (используем множественное число)
            type_folder = TYPE_TO_FOLDER.get(card.card_type, card.card_type)
            filename = generate_filename(card)
            filepath = os.path.join(images_dir, type_folder, filename)
            
            # Проверяем существование файла
            if os.path.isfile(filepath):
                # Формируем относительный путь для хранения в БД
                image_id = f"{type_folder}/{filename}"
                
                if card.image_id != image_id:
                    card.image_id = image_id
                    updated += 1
                    print(f"  ✓ Обновлена карточка {card.id}: {card.name} -> {image_id}")
        
        session.commit()
        print(f"✓ Обновлено {updated} карточек в БД")
        
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Генерация промтов для изображений карточек"
    )
    parser.add_argument(
        '--export',
        action='store_true',
        help='Экспортировать промты в CSV файл'
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='Обновить image_id в БД на основе существующих файлов'
    )
    parser.add_argument(
        '--output',
        default='image_prompts.csv',
        help='Имя выходного CSV файла (по умолчанию: image_prompts.csv)'
    )
    parser.add_argument(
        '--images-dir',
        default='grokhanika/web/static/images/cards',
        help='Путь к папке с изображениями (по умолчанию: grokhanika/web/static/images/cards)'
    )
    
    args = parser.parse_args()
    
    if args.export:
        export_prompts(args.output)
    elif args.update:
        update_database(args.images_dir)
    else:
        parser.print_help()
        print("\nПримеры:")
        print("  python scripts/generate_image_prompts.py --export")
        print("  python scripts/generate_image_prompts.py --export --output my_prompts.csv")
        print("  python scripts/generate_image_prompts.py --update")


if __name__ == "__main__":
    main()
