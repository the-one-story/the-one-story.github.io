/**
 * One Story - signup endpoint.
 *
 * Resend has no hosted signup form (Brevo did), and its contacts API needs the
 * API key - which can never sit in a public page. So the page posts here, and
 * this Worker calls Resend server-side with the key held as a Worker secret.
 *
 * Deliberately tiny and dependency-free. It accepts a normal form POST and
 * replies with a minimal HTML page, because the page submits into a hidden
 * iframe - that keeps the subscriber on the page and works with no JS.
 *
 * Secrets (set with `wrangler secret put`, never committed):
 *   RESEND_API_KEY   - a Resend key with contacts write access
 * Vars (wrangler.toml):
 *   SEGMENT_ID       - the Resend segment/audience uuid to add contacts to
 *   ALLOWED_ORIGIN   - the site origin permitted to post here
 */

const HTML = (msg) =>
  new Response(`<!doctype html><meta charset="utf-8"><p>${msg}</p>`, {
    headers: { "content-type": "text/html; charset=utf-8" },
  });

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      // Pre-flight, in case the form is ever switched to fetch().
      return new Response(null, {
        headers: {
          "access-control-allow-origin": env.ALLOWED_ORIGIN || "*",
          "access-control-allow-methods": "POST, OPTIONS",
          "access-control-allow-headers": "content-type",
        },
      });
    }
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    let email = "";
    let honeypot = "";
    try {
      const ct = request.headers.get("content-type") || "";
      if (ct.includes("application/json")) {
        const body = await request.json();
        email = (body.email || "").trim();
        honeypot = (body.email_address_check || "").trim();
      } else {
        const form = await request.formData();
        email = (form.get("email") || "").toString().trim();
        honeypot = (form.get("email_address_check") || "").toString().trim();
      }
    } catch {
      return HTML("Could not read that submission.");
    }

    // Honeypot: humans never see the field, bots fill it. Answer 200 so the bot
    // cannot tell it was rejected, but do not touch the list.
    if (honeypot) return HTML("Thanks.");

    // Deliberately loose - the real validation is Resend's, and an over-strict
    // regex rejects valid addresses.
    if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      return HTML("That does not look like an email address.");
    }

    const res = await fetch("https://api.resend.com/contacts", {
      method: "POST",
      headers: {
        authorization: `Bearer ${env.RESEND_API_KEY}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        email,
        unsubscribed: false,
        segments: [{ id: env.SEGMENT_ID }],
      }),
    });

    if (!res.ok) {
      // Log for `wrangler tail`, but never leak the provider's response to the
      // page - it can echo account detail.
      console.log("resend contacts failed", res.status, await res.text());
      return HTML("Sorry - something went wrong. Please try again later.");
    }
    return HTML("Thanks - you're on the list.");
  },
};
