"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/app/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setError(null);
    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    setLoading(false);

    if (error) {
      setError("Email or password is incorrect.");
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  return (
    <main className="auth-wrap">
      <div className="auth-card">
        <p className="auth-brand">LindaAI</p>
        <h1 className="auth-title">Welcome back</h1>
        <p className="auth-sub">Log in to your dashboard.</p>

        <div className="field">
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="input" type="email" value={email}
            onChange={(e) => setEmail(e.target.value)} placeholder="you@business.co.ke" />
        </div>
        <div className="field">
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="input" type="password" value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            placeholder="Your password" />
        </div>

        {error && <p className="msg msg--error">{error}</p>}

        <button className="btn btn--primary" onClick={handleLogin} disabled={loading}>
          {loading ? "Logging in…" : "Log in"}
        </button>

        <p className="auth-foot">
          New here? <Link href="/signup">Create an account</Link>
        </p>
      </div>
    </main>
  );
}
