# 의료광고법 금지 표현 검사 — HTML 주석과 스크립트를 제외한 '실제 노출 텍스트'만 본다
import re, sys, html

PATTERNS = [
    (r'없습니다|없어요|없는|무통|다운타임\s*(제로|0|없)', '부정형 단정 (제7·8·2호)'),
    (r'최고|최상|최고급|최초|최신|유일|제일|1위|No\.?\s*1|베스트|명품', '최상급 (제3·8호)'),
    (r'완벽|완치|100\s*%|절대|반드시|보장|평생|영구', '단정·보장 (제3·8호)'),
    (r'흉터\s*없|가장\s*안전|책임\s*진료|부작용\s*없', '안전성 단정 (제7·8호)'),
    (r'특가|한정|이벤트|할인|선착순|혜택|사은품|무료', '유인 (제13호·제27조)'),
    (r'즉시\s*효과|효과\s*보장|눈에\s*띄게', '효과 주장 (제2·8호)'),
    (r'전문\s*클리닉|명의|전문의\s*직접', '자격 표방 (제9호)'),
    (r'와\s*달리|타\s*병원|기존\s*장비|차별화|대비\s*우수', '비교 (제4호)'),
    (r'후기|리뷰|별점|만족도|체험담|경험담', '치료경험담 (제2호)'),
    (r'비포|애프터|before\s*&?\s*after|전후\s*사진', '전후 사진 (제2·6호)'),
    (r'콜라겐', '허가범위 외 효능 (의료기기법 제24조)'),
    (r'하나의\s*리프팅|오직|단\s*하나|유일한', '유일성 암시 (제8호)'),
    (r'\d+\s*곳(의)?\s*(의원|병원|클리닉)|돌아온\s*끝에|전전한', '편력 서사 = 치료경험담·비교 (제2·4호)'),
    (r'끝에\s*도달|마지막으로\s*찾은|결국\s*찾은', '치료효과 오인 서사 (제2호)'),
]

def visible_text(path):
    src = open(path, encoding='utf-8').read()
    src = re.sub(r'<!--.*?-->', ' ', src, flags=re.S)          # 주석 제거
    src = re.sub(r'<script.*?</script>', ' ', src, flags=re.S)  # JSON-LD·JS 제거
    src = re.sub(r'<style.*?</style>', ' ', src, flags=re.S)
    src = re.sub(r'<[^>]+>', ' ', src)                          # 태그 제거
    return html.unescape(src)

# 검토 완료 — 의료 효과·안전성 주장이 아니라 운영 안내·안내문이므로 허용
ALLOW = [
    r'예약\s*없이\s*방문하시면\s*진료를\s*받으실\s*수\s*없습니다',   # 완전예약제 운영 사실
    r'반드시\s*읽어\s*주십시오',                                       # 환자에 대한 안내 지시
    r'반드시\s*알려주셔야\s*하는',                                     # 환자에 대한 안내 지시
    r'복구할\s*수\s*없는\s*방법으로\s*삭제',                         # 개인정보 파기 절차 표준 문구
]

def allowed(text, start, end):
    for a in ALLOW:
        for am in re.finditer(a, text):
            if am.start() <= start and end <= am.end():
                return True
    return False

bad = 0
for path in sys.argv[1:]:
    text = visible_text(path)
    lines = [l.strip() for l in text.split('\n')]
    for pat, label in PATTERNS:
        for m in re.finditer(pat, text):
            if allowed(text, m.start(), m.end()):
                continue
            ctx = text[max(0, m.start()-45): m.end()+45].replace('\n', ' ')
            ctx = re.sub(r'\s+', ' ', ctx).strip()
            print(f'  [{label}] "{m.group()}"')
            print(f'      ...{ctx}...')
            print(f'      ← {path}')
            bad += 1

print()
print('=' * 70)
if bad:
    print(f'⚠️  {bad}건 검출 — 각각 확인 필요')
else:
    print('✅ 노출 텍스트에서 금지 표현 없음')
