# Berwaz accounts — Supabase setup (≈10 minutes)

The site works without any of this (local boards, no sign-in). Once configured, sign-in,
cloud boards, public profiles, gating and analytics switch on automatically.

## 1. Create the project
1. Go to https://supabase.com → **New project**.
2. Name: `berwaz`. Region: **Frankfurt (eu-central-1)** — closest to Saudi Arabia with the lowest latency
   (there is no KSA region; Supabase is open-source and can be self-hosted in-Kingdom later).
3. Choose a strong database password and keep it somewhere safe (you won't need it for the site).

## 2. Create the tables
1. Left sidebar → **SQL Editor** → **New query**.
2. Paste the entire contents of `supabase/schema.sql` → **Run**. It should finish with "Success".

## 3. Turn on magic-link sign-in
1. **Authentication → Providers → Email**: keep **Enable Email provider** on.
2. **Authentication → Sign In / Providers → Email**: turn **Confirm email** *off*
   (magic links then sign the user straight in) and keep **Enable magic link** on.
3. **Authentication → URL Configuration**:
   - Site URL: `https://zraddia93.github.io/berwaz/`
   - Redirect URLs (add all): `https://zraddia93.github.io/berwaz/**`, `http://localhost:8765/**`
4. **Authentication → Email Templates → Magic Link**: optional, but worth making it say "Berwaz".
   Suggested subject: `Your Berwaz sign-in link`.

> **Important — email limits.** Supabase's built-in mailer allows only a few emails per hour on the
> free plan, which is fine for testing but not for real users. Before launch, set a custom SMTP
> under **Project Settings → Authentication → SMTP Settings**. Resend (resend.com) has a free tier
> and takes ten minutes: verify your domain, create an API key, and enter
> host `smtp.resend.com`, port `465`, user `resend`, password = the API key, sender `hello@yourdomain`.

## 4. Copy the keys into the site
1. **Project Settings → API**. Copy **Project URL** and the **anon public** key.
2. Open `cloud-config.js` in the site folder and fill them in:
   ```js
   window.BERWAZ_CLOUD = {
     url: 'https://xxxxxxxx.supabase.co',
     anonKey: 'eyJhbGciOi...'
   };
   ```
   The anon key is designed to be public — security comes from the row-level policies in the schema.
   **Never** put the `service_role` key anywhere in the site.
3. Commit and push. Sign-in appears in the header on the next deploy.

## 5. Test
1. Open the site, click **Sign in**, enter your email, open the link from the email.
2. You should land back on the site signed in; your existing local boards are uploaded to your account.
3. Open **Boards** → a board → toggle **Public** → visit `profile.html?u=<your handle>`.

## Where to look later
- **Authentication → Users**: everyone who signed up.
- **Table Editor → boards / profiles**: the data.
- **SQL Editor**: `select * from top_saved_frames(20);` — most-saved frames;
  `select name, count(*) from events group by 1 order by 2 desc;` — what people do on the site.

## Self-hosting in-Kingdom (later)
Supabase publishes a Docker Compose stack (github.com/supabase/supabase/tree/master/docker). Run it on a
Saudi cloud VM, run `schema.sql` there, export/import the tables, and change `cloud-config.js`. The site
code doesn't change.
