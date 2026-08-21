// ============================================================
// submit-model — Supabase Edge Function
// ------------------------------------------------------------
// Receives a model submission from the public site, stores it in the
// `model_submissions` table (using the service_role key, bypassing RLS), and
// sends a Telegram notification. The Telegram bot token is a server-side
// secret and is never exposed to the browser.
//
// Required secrets (set with: supabase secrets set KEY=value):
//   TELEGRAM_BOT_TOKEN   — from @BotFather
//   TELEGRAM_CHAT_ID     — your chat/channel/group id (see README notes)
// Auto-provided by Supabase at runtime:
//   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
//
// Deploy with:
//   supabase functions deploy submit-model
// ============================================================

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

function clip(v: unknown, max: number): string {
  return (typeof v === "string" ? v : "").trim().slice(0, max);
}

/** Submissions accepted from one hashed IP per hour. */
const MAX_PER_HOUR = 5;

async function sha256(input: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

Deno.serve(async (req: Request) => {
  try {
    return await handle(req);
  } catch (err) {
    // Without this, an unhandled throw returns a bare 500 with no CORS
    // headers, and the browser reports a CORS failure instead of the real error.
    console.error("submit-model failed:", err);
    return json({ error: "Internal error" }, 500);
  }
});

async function handle(req: Request): Promise<Response> {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return json({ error: "Invalid JSON" }, 400);
  }

  // Honeypot: a hidden field real users never fill. Pretend success, drop it.
  if (clip(body.website, 200) !== "") return json({ ok: true });

  // Consent must be explicit. Storing personal data without it leaves no
  // record that the person agreed, which is the basis for holding it at all.
  if (body.consent !== true) {
    return json({ error: "Consent is required" }, 400);
  }

  const name = clip(body.name, 120);
  const email = clip(body.email, 160);
  const model_name = clip(body.model_name, 120);
  const company = clip(body.company, 120) || null;
  const notes = clip(body.notes, 1500) || null;

  if (!name || !email || !model_name) {
    return json({ error: "Missing required fields" }, 400);
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ error: "Invalid email" }, 400);
  }

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
  const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!SUPABASE_URL || !SERVICE_KEY) {
    console.error("Missing Supabase environment");
    return json({ error: "Server not configured" }, 500);
  }

  // Rate limit on a hashed IP. The endpoint is public and unauthenticated, and
  // each accepted request both writes a row and fires a Telegram message — so
  // without a limit a trivial loop exhausts the quota and floods the channel.
  const ipHash = await sha256(
    (req.headers.get("x-forwarded-for") ?? "").split(",")[0].trim() +
    (Deno.env.get("IP_HASH_SALT") ?? "idrock-eval"),
  );
  const since = new Date(Date.now() - 60 * 60 * 1000).toISOString();
  const recent = await fetch(
    `${SUPABASE_URL}/rest/v1/model_submissions?ip_hash=eq.${ipHash}` +
    `&created_at=gte.${since}&select=id`,
    { headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` } },
  );
  if (recent.ok) {
    const rows = await recent.json();
    if (Array.isArray(rows) && rows.length >= MAX_PER_HOUR) {
      return json({ error: "Too many submissions. Please try again later." }, 429);
    }
  }

  // 1) Store the submission (service_role bypasses RLS).
  const insertRes = await fetch(`${SUPABASE_URL}/rest/v1/model_submissions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      Prefer: "return=minimal",
    },
    body: JSON.stringify({
      name, email, model_name, company, notes,
      consent_at: new Date().toISOString(),
      ip_hash: ipHash,
    }),
  });

  if (!insertRes.ok) {
    console.error("Insert failed:", insertRes.status, await insertRes.text());
    return json({ error: "Could not store submission" }, 500);
  }

  // 2) Notify via Telegram (best-effort; never fail the request over this).
  const token = Deno.env.get("TELEGRAM_BOT_TOKEN");
  const chatId = Deno.env.get("TELEGRAM_CHAT_ID");
  if (token && chatId) {
    const text =
      "🆕 New model submission — eval.idrock.uz\n\n" +
      `👤 Name: ${name}\n` +
      `✉️ Email: ${email}\n` +
      `🤖 Model: ${model_name}\n` +
      (company ? `🏢 Company: ${company}\n` : "") +
      (notes ? `📝 Notes: ${notes}\n` : "");
    try {
      const tgRes = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // No parse_mode: send as plain text so user input needs no escaping.
        body: JSON.stringify({ chat_id: chatId, text, disable_web_page_preview: true }),
      });
      if (!tgRes.ok) console.error("Telegram notify failed:", await tgRes.text());
    } catch (e) {
      console.error("Telegram notify error:", e);
    }
  }

  return json({ ok: true });
}
