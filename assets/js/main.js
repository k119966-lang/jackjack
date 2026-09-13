/* ═══════════════════════════════════════════════
   AURA CLINIC — 동작 스크립트
   가격을 바꾸면 아래 PRICE 값도 같이 바꿔주세요.
   ═══════════════════════════════════════════════ */

/* ▼ 여기 두 줄만 고치면 계산기 금액이 전부 바뀝니다 */
const PRICE = {
  normal: 1500,   // 슈링크 1샷 정가
  event : 1000,   // 슈링크 1샷 오픈 이벤트가
};

const won = n => n.toLocaleString('ko-KR') + '원';


/* ── 1. 스크롤하면 헤더 배경 생기기 ───────────── */
(() => {
  const hd = document.getElementById('hd');
  if (!hd) return;
  const onScroll = () => hd.classList.toggle('is-stuck', window.scrollY > 40);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
})();


/* ── 2. 모바일 햄버거 메뉴 ───────────────────── */
(() => {
  const burger = document.getElementById('burger');
  const nav    = document.getElementById('nav');
  if (!burger || !nav) return;

  const setOpen = open => {
    nav.classList.toggle('is-open', open);
    burger.setAttribute('aria-expanded', String(open));
    burger.setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
  };

  burger.addEventListener('click', () => {
    setOpen(burger.getAttribute('aria-expanded') !== 'true');
  });

  // 메뉴 항목을 누르면 자동으로 닫기
  nav.addEventListener('click', e => {
    if (e.target.closest('a')) setOpen(false);
  });

  // ESC 로 닫기
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') setOpen(false);
  });

  // PC 너비로 넓어지면 상태 초기화
  matchMedia('(min-width: 901px)').addEventListener('change', e => {
    if (e.matches) setOpen(false);
  });
})();


/* ── 3. 스크롤하면 하나씩 나타나기 ───────────── */
(() => {
  const items = document.querySelectorAll('.reveal');
  if (!items.length) return;

  // 모션을 줄이도록 설정한 사용자에게는 애니메이션 없이 바로 보여줌
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
    items.forEach(el => el.classList.add('is-in'));
    return;
  }

  const io = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-in');
      obs.unobserve(entry.target);
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

  items.forEach(el => io.observe(el));
})();


/* ── 4. 샷 수 계산기 ─────────────────────────── */
(() => {
  const range = document.getElementById('shots');
  if (!range) return;

  const shotOut = document.getElementById('shotOut');
  const calcWas = document.getElementById('calcWas');
  const calcNow = document.getElementById('calcNow');
  const calcSave = document.getElementById('calcSave');
  const quickBtns = document.querySelectorAll('.calc__quick button');

  const render = () => {
    const shots = Number(range.value);
    const was = shots * PRICE.normal;
    const now = shots * PRICE.event;

    shotOut.textContent  = shots.toLocaleString('ko-KR') + '샷';
    calcWas.textContent  = won(was);
    calcNow.textContent  = won(now);
    calcSave.textContent = won(was - now);

    // 슬라이더 채워진 부분 색칠
    const pct = (shots - range.min) / (range.max - range.min) * 100;
    range.style.setProperty('--pct', pct + '%');

    // 빠른 선택 버튼 활성화 표시
    quickBtns.forEach(b => b.classList.toggle('is-on', Number(b.dataset.shots) === shots));
  };

  range.addEventListener('input', render);
  quickBtns.forEach(b => b.addEventListener('click', () => {
    range.value = b.dataset.shots;
    render();
  }));

  render();
})();


/* ── 5. 아직 주소를 안 넣은 링크 눌렀을 때 안내 ── */
(() => {
  document.addEventListener('click', e => {
    const a = e.target.closest('a[data-todo]');
    if (!a) return;
    e.preventDefault();
    alert('아직 주소를 연결하지 않았습니다.\n\n해야 할 일: ' + a.dataset.todo);
  });
})();
