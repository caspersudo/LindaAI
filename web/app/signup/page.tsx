"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/app/lib/supabase/client";

export default function SignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSignup() {
    setError(null);
    if (password.length < 8) {
      setError("Use a password with at least 8 characters.");
      return;
    }
    setLoading(true);
    const supabase = createClient();
    const { data, error } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      options: {
        data: { full_name: fullName.trim() },
        emailRedirectTo: `${location.origin}/auth/confirm`,
      },
    });
    setLoading(false);

    if (error) {
      setError(error.message);
      return;
    }
    // If email confirmation is OFF, Supabase logs them in immediately.
    if (data.session) {
      router.push("/dashboard");
      router.refresh();
    } else {
      // Email confirmation is ON — tell them to check their inbox.
      setSent(true);
    }
  }

  if (sent) {
    return (
      <main className="auth-wrap">
        <div className="auth-card">
          <p className="auth-brand">LindaAI</p>
          <h1 className="auth-title">Check your email</h1>
          <p className="auth-sub">
            We sent a confirmation link to <strong>{email}</strong>. Click it to
            finish creating your account.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="auth-wrap">
      <div className="auth-card">
        <p className="auth-brand">LindaAI</p>
        <h1 className="auth-title">Create your account</h1>
        <p className="auth-sub">Start protecting a website you own.</p>

        <div className="field">
          <label className="label" htmlFor="name">Full name</label>
          <input id="name" className="input" value={fullName}
            onChange={(e) => setFullName(e.target.value)} placeholder="Jane Wanjiku" />
        </div>
        <div className="field">
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="input" type="email" value={email}
            onChange={(e) => setEmail(e.target.value)} placeholder="you@business.co.ke" />
        </div>
        <div className="field">
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="input" type="password" value={password}
            onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
        </div>

        {error && <p className="msg msg--error">{error}</p>}

        <button className="btn btn--primary" onClick={handleSignup} disabled={loading}>
          {loading ? "Creating account…" : "Create account"}
        </button>

        <p className="auth-foot">
          Already have an account? <Link href="/login">Log in</Link>
        </p>
      </div>
    </main>
  );
}
