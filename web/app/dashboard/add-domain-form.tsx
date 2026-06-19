"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/app/lib/supabase/client";

// Same shape the database expects: e.g. yourbusiness.co.ke
const DOMAIN_PATTERN = /^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/;

export default function AddDomainForm({ orgId }: { orgId: string }) {
  const router = useRouter();
  const [hostname, setHostname] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleAdd() {
    setError(null);

    // Clean common copy/paste mistakes: https://, www., trailing slash, caps.
    const clean = hostname
      .trim()
      .toLowerCase()
      .replace(/^https?:\/\//, "")
      .replace(/^www\./, "")
      .replace(/\/.*$/, "");

    if (!DOMAIN_PATTERN.test(clean)) {
      setError("That doesn't look like a domain. Try something like yourbusiness.co.ke");
      return;
    }

    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase
      .from("verified_domains")
      .insert({ hostname: clean, org_id: orgId });
    setLoading(false);

    if (error) {
      setError(
        error.message.toLowerCase().includes("duplicate")
          ? "That domain has already been added."
          : error.message
      );
      return;
    }

    setHostname("");
    router.refresh(); // reload the dashboard so the new domain appears
  }

  return (
    <div className="add-card">
      <label className="label" htmlFor="domain">Website domain</label>
      <div className="add-row">
        <input
          id="domain"
          className="input"
          value={hostname}
          onChange={(e) => setHostname(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder="yourbusiness.co.ke"
        />
        <button className="btn btn--primary" onClick={handleAdd} disabled={loading}>
          {loading ? "Adding…" : "Add domain"}
        </button>
      </div>
      {error && <p className="msg msg--error" role="alert">{error}</p>}
    </div>
  );
}
