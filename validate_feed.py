"""Validate the public feed without contacting accounts or modifying files."""
import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


def iso_date(value):
    if not isinstance(value, str):
        raise ValueError('date must be a YYYY-MM-DD string')
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError('date must use YYYY-MM-DD')
    return result


def validate(pack, sources, today=None, require_current=False):
    today = today or datetime.now(timezone(timedelta(hours=9))).date()
    if type(pack.get('version')) is not int or pack['version'] < 1:
        raise ValueError('version must be a positive integer')
    updated = iso_date(pack.get('updatedAt'))
    if updated > today:
        raise ValueError('updatedAt must not be in the future')
    weeks = pack.get('weeks')
    if not isinstance(weeks, list) or not weeks:
        raise ValueError('weeks must not be empty')
    ids = set()
    current = None
    monday = today - timedelta(days=today.weekday())
    for week in weeks:
        start = iso_date(week.get('start'))
        year, number, _ = start.isocalendar()
        wid = week.get('id')
        if start.weekday() or wid != f'{year:04}-W{number:02}' or wid in ids:
            raise ValueError('week must have a unique ISO week ID and Monday start')
        ids.add(wid)
        if not isinstance(week.get('title'), str) or not week['title'].strip():
            raise ValueError('week title is required')
        questions = week.get('questions')
        if not isinstance(questions, list) or not questions:
            raise ValueError('week questions must not be empty')
        seen = set()
        for q in questions:
            text = q.get('text')
            if not isinstance(text, str) or not text.strip() or text in seen:
                raise ValueError('question text must be nonempty and unique in the week')
            seen.add(text)
            choices = q.get('choices')
            if (not isinstance(choices, list) or len(choices) != 4
                    or any(not isinstance(c, str) or not c.strip() for c in choices)
                    or len(set(choices)) != 4):
                raise ValueError('exactly four distinct nonempty choices are required')
            if type(q.get('answer')) is not int or not 0 <= q['answer'] < 4:
                raise ValueError('answer must be an integer from 0 to 3')
            if not isinstance(q.get('cat'), str) or not q['cat'].strip():
                raise ValueError('question category is required')
        if start == monday:
            current = week
    if require_current:
        if not current or len(current['questions']) < 10 or updated < monday:
            raise ValueError('a current-week pack of at least ten questions is required')
        covered = set()
        for ref in sources.get(current['id'], []):
            url = urlparse(ref.get('url', ''))
            if url.scheme != 'https' or not url.hostname or url.username or url.password:
                raise ValueError('source URL must be public HTTPS without credentials')
            checked = iso_date(ref.get('checkedAt'))
            if iso_date(ref.get('referenceDate')) > checked or checked > updated:
                raise ValueError('source dates must precede checking and feed update')
            numbers = ref.get('questions')
            if not isinstance(numbers, list) or any(type(n) is not int or not 1 <= n <= len(current['questions']) for n in numbers):
                raise ValueError('source question numbers are out of range')
            covered.update(numbers)
        if covered != set(range(1, len(current['questions']) + 1)):
            raise ValueError('every current question requires a checked source')
    return {'version': pack['version'], 'weeks': len(weeks), 'currentWeek': current['id'] if current else None,
            'currentQuestions': len(current['questions']) if current else 0, 'updatedAt': pack['updatedAt']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-current', action='store_true')
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    try:
        result = validate(json.loads((base/'newsquiz.json').read_text(encoding='utf-8')),
                          json.loads((base/'sources.json').read_text(encoding='utf-8')),
                          require_current=args.require_current)
    except (ValueError, TypeError, AttributeError) as error:
        parser.exit(1, f'INVALID: {error}\n')
    print(json.dumps(result, ensure_ascii=False))
