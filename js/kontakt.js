/* ============================================================
   Kontaktformular — POST an api.kopten.de/contact (Cloudflare Worker + Resend)
   ============================================================ */

const API_ENDPOINT = 'https://api.kopten.de/contact';

const MESSAGES = {
  invalid_json:      'Etwas ging schief beim Senden. Bitte später erneut versuchen.',
  name_required:     'Bitte gib deinen Namen an.',
  email_invalid:     'Bitte gib eine gültige E-Mail-Adresse ein.',
  message_required:  'Bitte schreib eine kurze Nachricht.',
  consent_required:  'Bitte stimme der Datenverarbeitung zu.',
  send_failed:       'Beim Senden ist ein Fehler aufgetreten. Bitte später erneut versuchen.',
  not_found:         'Endpunkt nicht gefunden. Bitte später erneut versuchen.',
  network:           'Verbindungsfehler. Bitte Internetverbindung prüfen.',
  success:           'Vielen Dank! Deine Nachricht ist angekommen — wir melden uns zeitnah.',
};

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('contact-form');
  const status = document.getElementById('form-status');
  if (!form) return;

  const submitBtn = form.querySelector('button[type="submit"]');

  function setStatus(type, text) {
    status.className = 'form-status';
    if (type) status.classList.add(`is-${type}`);
    status.textContent = text || '';
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    setStatus('', '');

    const payload = {
      name:    form.name.value.trim(),
      email:   form.email.value.trim(),
      subject: form.subject.value.trim(),
      message: form.message.value.trim(),
      consent: form.consent.checked,
      website: (form.website?.value || '').trim(),  // honeypot
    };

    // Clientseitige Vorprüfung — der Worker validiert nochmal
    if (!payload.name)    return setStatus('error', MESSAGES.name_required);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email))
                          return setStatus('error', MESSAGES.email_invalid);
    if (!payload.message) return setStatus('error', MESSAGES.message_required);
    if (!payload.consent) return setStatus('error', MESSAGES.consent_required);

    submitBtn.disabled = true;
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = 'Sende …';

    try {
      const res = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({ ok: false, error: 'invalid_json' }));

      if (data.ok) {
        setStatus('success', MESSAGES.success);
        form.reset();
      } else {
        setStatus('error', MESSAGES[data.error] || MESSAGES.send_failed);
      }
    } catch (err) {
      setStatus('error', MESSAGES.network);
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalText;
    }
  });
});
