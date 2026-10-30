"""Conservative name correction against the registered parts, not manual text."""
import re
import question_scope as scope


def compact(text):
    return re.sub(r'\s+', '', text).lower()


def distance(left, right):
    """Levenshtein distance; bounded short name strings only."""
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        new = [i]
        for j, b in enumerate(right, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j-1] + (a != b)))
        row = new
    return row[-1]


def name_spans(question):
    # Keep exact source offsets: only the candidate name may be replaced.
    actions = r'작동|동작|고장|이상|점검|정비|교환|교체|탈거|장착|위치|구성|설명|방법|절차|가격|전압|수명|결로|습기|알려|보여'
    tokens = list(re.finditer(r'[가-힣a-zA-Z0-9]+', question))
    for i, token in enumerate(tokens):
        for last in tokens[i:i+4]:
            start, end = token.start(), last.end()
            raw = question[start:end]
            action = re.search(actions, raw)
            if action:
                end = start + action.start()
            while end > start and question[end-1].isspace():
                end -= 1
            raw = question[start:end]
            if not raw or len(compact(raw)) > 24:
                continue
            yield start, end, raw
            suffix = re.search(r'(에서|으로|에는|은|는|이|가|을|를|의|에|와|과|도)$', raw)
            if suffix:
                yield start, start + suffix.start(), raw[:suffix.start()]


def resolve(question, parts):
    """Return a unique correction or candidates; never modify the request intent."""
    best = {}
    for start, end, raw in set(name_spans(question)):
        typed = compact(raw)
        if len(typed) < 3 or typed.isdigit():
            continue
        for part in parts:
            for term in [part['name']] + part['aliases']:
                name = compact(term)
                if abs(len(typed) - len(name)) > 2:
                    continue
                edits = distance(typed, name)
                score = 1 - edits / max(len(typed), len(name))
                # Short names allow one typo, longer names require >=80% match.
                if edits > (1 if len(name) < 5 else 2) or score < (2/3 if len(name) == 3 else .75 if len(name) == 4 else .8):
                    continue
                item = {'part': part, 'inputName': raw, 'matchedName': part['name'],
                        'normalizedQuestion': question[:start] + part['name'] + question[end:],
                        'score': score, 'start': start, 'end': end}
                old = best.get(part['id'])
                if old is None or (score, end-start, -start) > (old['score'], old['end']-old['start'], -old['start']):
                    best[part['id']] = item
    ranked = sorted(best.values(), key=lambda r: (-r['score'], r['part']['id']))
    if ranked:
        top = ranked[0]
        close = [r for r in ranked if top['score'] - r['score'] < .12]
        if len(close) == 1:
            if scope.supported(top['part'],top['normalizedQuestion']) or re.search(r'가격|금액|단가|비용|얼마|전압|규정값|토크|수명|루멘',top['normalizedQuestion']):
                return {'match': top, 'candidates': []}
            return {'match':None,'candidates':[]}
        return {'match': None, 'candidates': [r['part'] for r in close]}
    # An incomplete shared noun is useful for clarification, never auto-substitute.
    candidates = {}
    for start, end, raw in name_spans(question):
        typed = compact(raw)
        if len(typed) < 2 or typed.isdigit():
            continue
        for part in parts:
            if (any(typed in compact(term) for term in [part['name']] + part['aliases'])
                    and scope.supported(part, question[:start] + part['name'] + question[end:])):
                candidates[part['id']] = part
    return {'match': None, 'candidates': list(candidates.values())}
