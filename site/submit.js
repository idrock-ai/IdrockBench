// ============================================
// Model Submission Form -> Supabase Edge Function
// ============================================
//
// The form POSTs to a Supabase Edge Function (`submit-model`) which (1) stores
// the submission in the database and (2) sends a Telegram notification. The
// Telegram bot token lives only as a server-side secret in the function — it
// is never exposed to the browser. See supabase/functions/submit-model/.
//
// The anon (publishable) key below is SAFE to commit: it only authorizes the
// browser to invoke the function. See supabase-setup.sql for the DB + RLS.
//
// SETUP: create a Supabase project, run supabase-setup.sql, deploy the edge
// function, then paste your Project URL and anon key below.

const SUPABASE_CONFIG = {
    url: "https://vixpvhnyvcjzkjnkjkln.supabase.co",
    anonKey: "sb_publishable_h1Hzy-qEdS2gAJFD3QTK5w_jEvyZkz-",
    functionName: "submit-model"
};

// Localized status messages, mirrored from script.js TRANSLATIONS.
const SUBMIT_MESSAGES = {
    uz: {
        sending: "Yuborilmoqda...",
        success: "Rahmat! Arizangiz qabul qilindi. Modelni baholab, natijani reytingga qo'shamiz.",
        error: "Yuborishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring yoki idrock@newuu.uz ga yozing.",
        required: "Iltimos, barcha majburiy (*) maydonlarni to'ldiring."
    },
    en: {
        sending: "Sending...",
        success: "Thank you! Your submission was received. We'll evaluate the model and add it to the leaderboard.",
        error: "Something went wrong while submitting. Please try again or email idrock@newuu.uz.",
        required: "Please fill in all required (*) fields."
    }
};

function submitMsg(key) {
    const lang = document.documentElement.lang === "en" ? "en" : "uz";
    return (SUBMIT_MESSAGES[lang] || SUBMIT_MESSAGES.uz)[key];
}

(function initSubmitForm() {
    const form = document.getElementById("submitForm");
    if (!form) return;

    const statusEl = document.getElementById("formStatus");
    const btn = document.getElementById("submitBtn");
    const honeypot = document.getElementById("f_website");

    function setStatus(message, kind) {
        statusEl.textContent = message || "";
        statusEl.className = "form-status" + (kind ? ` form-status-${kind}` : "");
    }

    function configured() {
        return (
            SUPABASE_CONFIG.url &&
            !SUPABASE_CONFIG.url.includes("YOUR-PROJECT-REF") &&
            SUPABASE_CONFIG.anonKey &&
            !SUPABASE_CONFIG.anonKey.includes("YOUR-ANON")
        );
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        // Bot trap: a hidden field a human never fills. Pretend success, do nothing.
        if (honeypot && honeypot.value.trim() !== "") {
            setStatus(submitMsg("success"), "success");
            form.reset();
            return;
        }

        const consent = document.getElementById("f_consent");
        if (consent && !consent.checked) {
            setStatus(submitMsg("required"), "error");
            consent.focus();
            return;
        }

        if (!form.checkValidity()) {
            form.reportValidity();
            setStatus(submitMsg("required"), "error");
            return;
        }

        if (!configured()) {
            console.error("Supabase is not configured. Set SUPABASE_CONFIG in submit.js.");
            setStatus(submitMsg("error"), "error");
            return;
        }

        const fd = new FormData(form);
        const payload = {
            name: (fd.get("name") || "").trim(),
            email: (fd.get("email") || "").trim(),
            model_name: (fd.get("model_name") || "").trim(),
            company: (fd.get("company") || "").trim() || null,
            notes: (fd.get("notes") || "").trim() || null,
            consent: true,                    // recorded server-side with a timestamp
            website: fd.get("website") || "" // honeypot, validated server-side too
        };

        btn.disabled = true;
        setStatus(submitMsg("sending"), "");

        try {
            const res = await fetch(
                `${SUPABASE_CONFIG.url}/functions/v1/${SUPABASE_CONFIG.functionName}`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        apikey: SUPABASE_CONFIG.anonKey,
                        Authorization: `Bearer ${SUPABASE_CONFIG.anonKey}`
                    },
                    body: JSON.stringify(payload)
                }
            );

            if (!res.ok) {
                const detail = await res.text().catch(() => "");
                throw new Error(`HTTP ${res.status} ${detail}`);
            }

            setStatus(submitMsg("success"), "success");
            form.reset();
        } catch (err) {
            console.error("Submission failed:", err);
            setStatus(submitMsg("error"), "error");
        } finally {
            btn.disabled = false;
        }
    });
})();
