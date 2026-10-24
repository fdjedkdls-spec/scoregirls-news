"""Prepare one source-checked batch without overwriting the input feed.

Research is performed by the scheduled Codex task; this tool validates its result.
The output directory must be new. Publication is a separate, validated Git commit.
"""
import argparse
import copy
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from validate_feed import iso_date, validate


def japanese_today():
    return datetime.now(timezone(timedelta(hours=9))).date()


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold()
                   if not c.isspace() and not unicodedata.category(c).startswith('P'))


def prepare(pack, sources, batch, today=None, supplement=False):
    today = today or japanese_today()
    validate(pack, sources, today)
    digest = hashlib.sha256(json.dumps(batch, ensure_ascii=False, sort_keys=True,
                                      separators=(',', ':')).encode('utf-8')).hexdigest()
    batch_id = batch.get('batchId', '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', batch_id):
        raise ValueError('a stable batchId is required')
    ledger = pack.get('publishedBatches', {})
    if batch_id in ledger:
        if ledger[batch_id]['sha256'] != digest:
            raise ValueError('batchId was already used with different content')
        return copy.deepcopy(pack), copy.deepcopy(sources), False
    if iso_date(batch.get('checkedAt')) != today:
        raise ValueError('check the sources on the actual publication date')
    monday = today - timedelta(days=today.weekday())
    year, week_number, _ = monday.isocalendar()
    week_id = f'{year:04}-W{week_number:02}'
    old_week = next((w for w in pack['weeks'] if w['id'] == week_id), None)
    if old_week and not supplement:
        raise ValueError('this week already exists; do not create duplicate scheduled batches')
    questions = batch.get('questions', [])
    if len(questions) != 10:
        raise ValueError('each batch must contain exactly ten new questions')
    existing = {normalized(q['text']) for w in pack['weeks'] for q in w['questions']}
    for q in questions:
        if not isinstance(q.get('text'), str) or not 1 <= len(q['text']) <= 100:
            raise ValueError('new question text must fit within 100 characters')
        key = normalized(q['text'])
        if key in existing:
            raise ValueError('duplicate question in the existing feed or batch')
        existing.add(key)
        if not isinstance(q.get('choices'), list) or any(not isinstance(c, str) or len(c) > 36 for c in q['choices']):
            raise ValueError('new choices must fit within 36 characters')
    refs = batch.get('sources', [])
    if len({ref.get('url') for ref in refs}) < 3:
        raise ValueError('use at least three distinct primary source articles')
    for ref in refs:
        if not ref.get('title', '').strip() or not ref.get('supports', '').strip():
            raise ValueError('each source needs a title and factual support summary')
        if iso_date(ref.get('checkedAt')) != today:
            raise ValueError('every source must be checked today')
        published = iso_date(ref.get('referenceDate'))
        if not 0 <= (today - published).days <= 14:
            raise ValueError('source publication must be within the last fourteen days')
        if any(type(n) is not int or not 1 <= n <= 10 for n in ref.get('questions', [])):
            raise ValueError('batch source numbers must refer to its ten questions')
    new_pack, new_sources = copy.deepcopy(pack), copy.deepcopy(sources)
    new_week = {'id': week_id, 'start': monday.isoformat(), 'title': batch.get('title'),
                'questions': copy.deepcopy(questions)}
    new_sources[week_id] = copy.deepcopy(refs)
    if old_week:
        # The app uses the first ten questions for its weekly challenge.
        new_week['questions'].extend(copy.deepcopy(old_week['questions']))
        for ref in copy.deepcopy(sources.get(week_id, [])):
            ref['questions'] = [n + 10 for n in ref['questions']]
            new_sources[week_id].append(ref)
        new_pack['weeks'][new_pack['weeks'].index(old_week)] = new_week
    else:
        new_pack['weeks'].append(new_week)
    new_pack['version'] += 1
    new_pack['updatedAt'] = today.isoformat()
    new_pack.setdefault('publishedBatches', {})[batch_id] = {
        'sha256': digest, 'week': week_id, 'version': new_pack['version']}
    validate(new_pack, new_sources, today, require_current=True)
    return new_pack, new_sources, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch', type=Path)
    parser.add_argument('--base', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--supplement', action='store_true', help='explicitly add ten to an existing week')
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    pack, sources, changed = prepare(read(args.base/'newsquiz.json'), read(args.base/'sources.json'),
                                     read(args.batch), supplement=args.supplement)
    if not changed:
        print('ALREADY_APPLIED: no version increment or duplicated questions')
        return
    args.output.mkdir(parents=True, exist_ok=False)
    for name, data in [('newsquiz.json', pack), ('sources.json', sources)]:
        (args.output/name).write_bytes((json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print(json.dumps(validate(pack, sources, require_current=True), ensure_ascii=False))


if __name__ == '__main__':
    main()
