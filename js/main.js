/* ==========================================================================
   슈리링의원 — main.js
   프레임워크·빌드 도구 없이 동작합니다.
   ========================================================================== */
(function () {
  'use strict';

  /* ------------------------------------------------------------------
     예약 문의 전송
     지금은 콘솔 출력만 합니다.
     나중에 서버로 보낼 때는 이 함수 하나만 교체하면 됩니다. 예:

       async function submitReservation(payload) {
         const res = await fetch('/api/reservations', {
           method: 'POST',
           headers: { 'Content-Type': 'application/json' },
           body: JSON.stringify(payload)
         });
         if (!res.ok) throw new Error('전송 실패');
         return res.json();
       }

     ⚠️ 서버 전송으로 바꿀 때 확인할 것
        · HTTPS 필수 (개인정보 보호법상 안전성 확보조치)
        · 외부 폼·문자 발송 서비스를 쓰면 개인정보 보호법 제26조 처리위탁에 해당합니다.
          수탁자명과 위탁업무를 개인정보처리방침에 적어야 합니다.
        · 보유기간 1년 경과분 파기 절차를 함께 마련해야 합니다.
     ------------------------------------------------------------------ */
  function submitReservation(payload) {
    console.log('[예약 문의 접수]', payload);
    return Promise.resolve({ ok: true });
  }

  /* ------------------------------------------------------------------
     폼 검증 + 제출
     ------------------------------------------------------------------ */
  var form = document.getElementById('reserve-form');

  if (form) {
    var statusEl = document.getElementById('rf-status');

    var RULES = [
      {
        id: 'rf-name',
        errorId: 'rf-name-error',
        validate: function (v) {
          if (!v.trim()) return '이름을 입력해 주십시오.';
          return '';
        }
      },
      {
        id: 'rf-tel',
        errorId: 'rf-tel-error',
        validate: function (v) {
          var t = v.trim();
          if (!t) return '연락처를 입력해 주십시오.';
          // 숫자가 9자리 미만이면 연락 가능한 번호로 보기 어렵습니다.
          if (t.replace(/\D/g, '').length < 9) return '연락 가능한 번호를 정확히 입력해 주십시오.';
          return '';
        }
      },
      {
        id: 'rf-consent',
        errorId: 'rf-consent-error',
        isCheck: true,
        validate: function (checked) {
          if (!checked) return '개인정보 수집·이용에 동의해 주셔야 문의를 접수할 수 있습니다.';
          return '';
        }
      }
    ];

    function fieldValue(rule, el) {
      return rule.isCheck ? el.checked : el.value;
    }

    function showError(rule, message) {
      var el = document.getElementById(rule.id);
      var errEl = document.getElementById(rule.errorId);
      if (errEl) errEl.textContent = message;
      if (el && !rule.isCheck) {
        if (message) el.setAttribute('aria-invalid', 'true');
        else el.removeAttribute('aria-invalid');
      }
      return !message;
    }

    // 한 번 오류가 난 뒤에는 입력하는 동안 바로 오류를 지워 줍니다.
    RULES.forEach(function (rule) {
      var el = document.getElementById(rule.id);
      if (!el) return;
      var evt = rule.isCheck ? 'change' : 'input';
      el.addEventListener(evt, function () {
        var errEl = document.getElementById(rule.errorId);
        if (errEl && errEl.textContent) {
          showError(rule, rule.validate(fieldValue(rule, el)));
        }
      });
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();

      var firstInvalid = null;
      var allValid = true;

      RULES.forEach(function (rule) {
        var el = document.getElementById(rule.id);
        if (!el) return;
        var message = rule.validate(fieldValue(rule, el));
        var ok = showError(rule, message);
        if (!ok) {
          allValid = false;
          if (!firstInvalid) firstInvalid = el;
        }
      });

      if (!allValid) {
        statusEl.dataset.state = 'error';
        statusEl.textContent = '입력하지 않은 항목이 있습니다. 확인해 주십시오.';
        if (firstInvalid) firstInvalid.focus();
        return;
      }

      var payload = {
        name: document.getElementById('rf-name').value.trim(),
        tel: document.getElementById('rf-tel').value.trim(),
        consent: document.getElementById('rf-consent').checked,
        // 동의 시점을 함께 남깁니다. 보유기간(수집일로부터 1년) 기산점이 됩니다.
        consentedAt: new Date().toISOString()
      };

      var button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;

      statusEl.dataset.state = '';
      statusEl.textContent = '전송 중입니다.';

      submitReservation(payload)
        .then(function () {
          form.reset();
          RULES.forEach(function (rule) { showError(rule, ''); });
          statusEl.dataset.state = 'ok';
          statusEl.textContent =
            '문의가 접수되었습니다. 확인 후 연락드려 예약 시간을 확정합니다.';
        })
        .catch(function () {
          statusEl.dataset.state = 'error';
          statusEl.textContent =
            '전송에 실패했습니다. 잠시 후 다시 시도하시거나 전화로 문의해 주십시오.';
        })
        .finally(function () {
          if (button) button.disabled = false;
        });
    });
  }

  /* ------------------------------------------------------------------
     가로 스크롤이 생기는 표에만 키보드 포커스를 부여합니다.
     스크롤 영역이 키보드로 접근 불가능하면 접근성 문제가 됩니다.
     ------------------------------------------------------------------ */
  function updateScrollableTables() {
    document.querySelectorAll('.table-scroll').forEach(function (el) {
      var overflows = el.scrollWidth > el.clientWidth + 1;
      if (overflows) {
        el.setAttribute('tabindex', '0');
        el.setAttribute('role', 'region');
        var caption = el.querySelector('.table__caption');
        if (caption && !el.hasAttribute('aria-label')) {
          el.setAttribute('aria-label', caption.textContent.trim());
        }
      } else {
        el.removeAttribute('tabindex');
        el.removeAttribute('role');
        el.removeAttribute('aria-label');
      }
    });
  }

  updateScrollableTables();

  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(updateScrollableTables, 150);
  });
})();
