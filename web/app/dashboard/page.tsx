import { redirect } from "next/navigation";
import { createClient } from "@/app/lib/supabase/server";
import AddDomainForm from "./add-domain-form";

export default async function DashboardPage() {
  const supabase = await createClient();

  // 1. Who is logged in? If nobody, send them to the login page.
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  // 2. Load this person's business profile.
  const { data: profile } = await supabase
    .from("users")
    .select("org_id, full_name, email")
    .eq("id", user.id)
    .single();

  // 3. Load the domains belonging to their business (RLS keeps it to theirs).
  const { data: domains } = await supabase
    .from("verified_domains")
    .select("id, hostname, status, verify_token, created_at")
    .order("created_at", { ascending: false });

  const firstName = profile?.full_name?.split(" ")[0] || "there";

  return (
    <>
      <nav className="nav">
        <div className="nav-inner">
          <span className="nav-brand">
            <svg width="20" height="23" viewBox="0 0 26 30" aria-hidden="true">
              <path d="M13 1.5 23.5 5v9c0 7.2-4.6 12-10.5 14.5C7.1 26 2.5 21.2 2.5 14V5L13 1.5Z"
                fill="#E6F4EE" stroke="#1B7F5C" strokeWidth="1.6" strokeLinejoin="round" />
              <path d="M8 14.5l3.4 3.4L18 11" fill="none" stroke="#1B7F5C"
                strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            LindaAI
          </span>
          <form action="/auth/signout" method="post">
            <button className="btn btn--ghost btn--sm" type="submit">Log out</button>
          </form>
        </div>
      </nav>

      <main className="dash">
        <h1 className="dash-title">Hi {firstName} 👋</h1>
        <p className="dash-sub">Add a website you own to check it for security risks.</p>

        {profile?.org_id && <AddDomainForm orgId={profile.org_id} />}

        <h2 className="dash-h2">Your domains</h2>

        {!domains || domains.length === 0 ? (
          <div className="empty">
            <p className="empty-title">No domains yet</p>
            <p className="empty-sub">Add your first domain above to get started.</p>
          </div>
        ) : (
          <div className="domain-list">
            {domains.map((d) => (
              <div className="domain-card" key={d.id}>
                <div className="domain-head">
                  <span className="domain-host">{d.hostname}</span>
                  <span className={`badge badge--${d.status}`}>{d.status}</span>
                </div>
                {d.status === "pending" && (
                  <p className="domain-note">
                    Next step (coming in Week 2): add this TXT record at your
                    domain registrar to prove you own it.
                    <code className="token">{d.verify_token}</code>
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
