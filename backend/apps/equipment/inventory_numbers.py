import re

from django.db import transaction


LOCATION_PREFIXES = {
    'алтай': 'ALT',
    'москва': 'MSK',
    'новосибирск': 'NSK',
    'сочи': 'SOCH',
    'шерегеш': 'GESH',
}

INVENTORY_NUMBER_RE = re.compile(r'^(?P<prefix>[A-Z]{2,4})-(?P<letter>[A-Z])(?P<number>\d{4})$')
LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
DEFAULT_PREFIX = 'GEN'


def get_inventory_prefix(equipment):
    if equipment.location_id and equipment.location:
        name = equipment.location.name.strip().lower()
        if name in LOCATION_PREFIXES:
            return LOCATION_PREFIXES[name]

        latin = ''.join(char for char in name.upper() if 'A' <= char <= 'Z')
        if latin:
            return latin[:4]

    return DEFAULT_PREFIX


def _sequence_value(letter, number):
    return LETTERS.index(letter) * 10000 + number


def _format_sequence(prefix, value):
    letter_index, number = divmod(value, 10000)
    if letter_index >= len(LETTERS):
        raise ValueError(f'Закончился диапазон инвентарных номеров для префикса {prefix}.')
    return f'{prefix}-{LETTERS[letter_index]}{number:04d}'


def generate_next_inventory_number(equipment):
    from apps.equipment.models import Equipment

    prefix = get_inventory_prefix(equipment)
    last_value = 0

    numbers = (
        Equipment.objects
        .filter(inventory_number__startswith=f'{prefix}-')
        .values_list('inventory_number', flat=True)
    )
    for inventory_number in numbers:
        match = INVENTORY_NUMBER_RE.match(inventory_number or '')
        if not match or match.group('prefix') != prefix:
            continue
        value = _sequence_value(match.group('letter'), int(match.group('number')))
        last_value = max(last_value, value)

    return _format_sequence(prefix, last_value + 1)


def ensure_inventory_number(equipment):
    if equipment.inventory_number:
        return equipment.inventory_number

    with transaction.atomic():
        equipment.inventory_number = generate_next_inventory_number(equipment)
        return equipment.inventory_number
