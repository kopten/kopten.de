/**
 * Cloudflare Worker — API für kopten.de
 *
 * Route: api.kopten.de/*
 *
 * Endpunkte:
 *   POST /contact   — empfängt Kontaktformular, sendet via Resend an CONTACT_TO_EMAIL
 *
 * Secrets (via `wrangler secret put` oder CF Dashboard → Settings → Variables):
 *   RESEND_API_KEY     — Resend API Key
 *   CONTACT_TO_EMAIL   — Empfänger (z.B. info@kopten.de)
 *   CONTACT_FROM_EMAIL — Absender mit verifizierter Domain (z.B. noreply@kopten.de)
 */

const ALLOWED_ORIGIN = 'https://kopten.de';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Max-Age': '86400',
};

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

function isValidEmail(str) {
  return typeof str === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(str) && str.length <= 254;
}

function clamp(str, max) {
  return typeof str === 'string' ? str.slice(0, max).trim() : '';
}

async function handleContact(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: 'invalid_json' }, 400);
  }

  // Honeypot: hidden field that must be empty
  if (body.website && String(body.website).length > 0) {
    // Pretend success to confuse bots
    return json({ ok: true });
  }

  const name = clamp(body.name, 200);
  const email = clamp(body.email, 254);
  const subject = clamp(body.subject, 200) || 'Anfrage über die Website';
  const message = clamp(body.message, 5000);
  const consent = body.consent === true;

  if (!name) return json({ ok: false, error: 'name_required' }, 400);
  if (!isValidEmail(email)) return json({ ok: false, error: 'email_invalid' }, 400);
  if (!message) return json({ ok: false, error: 'message_required' }, 400);
  if (!consent) return json({ ok: false, error: 'consent_required' }, 400);

  // Send via Resend
  const text = [
    `Name: ${name}`,
    `E-Mail: ${email}`,
    '',
    'Nachricht:',
    message,
  ].join('\n');

  const resp = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: `Kontakt kopten.de <${env.CONTACT_FROM_EMAIL}>`,
      to: [env.CONTACT_TO_EMAIL],
      reply_to: email,
      subject: `[Kontakt] ${subject}`,
      text,
    }),
  });

  if (!resp.ok) {
    const errText = await resp.text().catch(() => '');
    console.error('Resend error', { status: resp.status, body: errText });
    return json({ ok: false, error: 'send_failed' }, 502);
  }

  // Auto-Reply an Absender (best-effort, blockiert die User-Response nicht)
  const replyText = [
    `Hallo ${name},`,
    '',
    'vielen Dank für deine Nachricht. Wir haben sie erhalten und melden uns zeitnah.',
    '',
    'Zur Erinnerung — das war deine Nachricht:',
    '',
    message,
    '',
    '---',
    'Koptisch-Orthodoxe Kirche in Deutschland',
    'https://kopten.de',
  ].join('\n');

  const replyResp = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: `Kopten Deutschland <${env.CONTACT_FROM_EMAIL}>`,
      to: [email],
      reply_to: env.CONTACT_TO_EMAIL,
      subject: 'Wir haben deine Nachricht erhalten',
      text: replyText,
    }),
  });

  if (!replyResp.ok) {
    // Logging only — die Hauptnachricht ist bereits durch
    const errText = await replyResp.text().catch(() => '');
    console.warn('Auto-reply send failed', { status: replyResp.status, body: errText });
  }

  return json({ ok: true });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    if (url.pathname === '/contact' && request.method === 'POST') {
      return handleContact(request, env);
    }

    return json({ ok: false, error: 'not_found' }, 404);
  },
};
