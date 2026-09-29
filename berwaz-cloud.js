/*
 * Berwaz cloud layer — accounts, cloud boards, public profiles, analytics.
 * Thin wrapper over supabase-js so the React app never touches Supabase directly.
 *
 * Exposes window.BerwazCloud:
 *   enabled                      → true when cloud-config.js is filled in
 *   init()                       → resolves { user, profile } (or nulls)
 *   onAuth(cb)                   → cb({ user, profile }) on every auth change; returns unsubscribe
 *   signIn(email)                → sends a magic link
 *   signOut()
 *   getUser() / getProfile()
 *   updateProfile(patch)
 *   getPublicProfile(handle)     → { profile, boards }
 *   boards: list(), create(), update(), remove(), mergeLocal(localBoards)
 *   getPublicBoard(id)           → { board, owner }
 *   track(name, props)           → fire-and-forget analytics
 */
(function () {
  'use strict';
  const cfg = (window.BERWAZ_CLOUD || {});
  const enabled = !!(cfg.url && cfg.anonKey && window.supabase && window.supabase.createClient);

  // Stable anonymous session id for analytics (not identity)
  const sessionId = (() => {
    try {
      let s = sessionStorage.getItem('berwaz_sid');
      if (!s) { s = Math.random().toString(36).slice(2) + Date.now().toString(36); sessionStorage.setItem('berwaz_sid', s); }
      return s;
    } catch { return 'na'; }
  })();

  const Cloud = { enabled, sessionId, _user: null, _profile: null, _listeners: new Set(), _client: null };

  if (!enabled) {
    // Local mode: everything is a no-op that resolves sensibly
    Object.assign(Cloud, {
      init: async () => ({ user: null, profile: null }),
      onAuth: () => () => {},
      signIn: async () => { throw new Error('Accounts are not configured on this site yet.'); },
      signOut: async () => {},
      getUser: () => null, getProfile: () => null,
      updateProfile: async () => null,
      getPublicProfile: async () => null,
      getPublicBoard: async () => null,
      boards: { list: async () => [], create: async () => null, update: async () => null, remove: async () => null, mergeLocal: async () => [] },
      track: () => {},
    });
    window.BerwazCloud = Cloud;
    return;
  }

  const sb = window.supabase.createClient(cfg.url, cfg.anonKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'pkce' },
  });
  Cloud._client = sb;

  const emit = () => { for (const cb of Cloud._listeners) { try { cb({ user: Cloud._user, profile: Cloud._profile }); } catch (e) { console.warn(e); } } };

  async function loadProfile(uid) {
    if (!uid) return null;
    const { data, error } = await sb.from('profiles').select('*').eq('id', uid).maybeSingle();
    if (error) { console.warn('profile load failed', error); return null; }
    return data;
  }

  async function setSession(session) {
    Cloud._user = session ? session.user : null;
    Cloud._profile = Cloud._user ? await loadProfile(Cloud._user.id) : null;
    // The signup trigger may lag the first session by a moment — retry once
    if (Cloud._user && !Cloud._profile) { await new Promise(r => setTimeout(r, 800)); Cloud._profile = await loadProfile(Cloud._user.id); }
    emit();
  }

  Cloud.init = async () => {
    const { data } = await sb.auth.getSession();
    await setSession(data.session);
    sb.auth.onAuthStateChange((_evt, session) => { setSession(session); });
    // Clean the magic-link hash/params out of the URL after the SDK has consumed them
    try {
      const u = new URL(window.location.href);
      if (u.hash.includes('access_token') || u.searchParams.has('code')) {
        u.hash = ''; u.searchParams.delete('code'); u.searchParams.delete('type');
        window.history.replaceState(null, '', u.toString());
      }
    } catch {}
    return { user: Cloud._user, profile: Cloud._profile };
  };

  Cloud.onAuth = (cb) => { Cloud._listeners.add(cb); return () => Cloud._listeners.delete(cb); };
  Cloud.getUser = () => Cloud._user;
  Cloud.getProfile = () => Cloud._profile;

  Cloud.signIn = async (email) => {
    const redirect = window.location.origin + window.location.pathname;
    const { error } = await sb.auth.signInWithOtp({ email, options: { emailRedirectTo: redirect, shouldCreateUser: true } });
    if (error) throw error;
    Cloud.track('auth_magic_link_sent');
    return true;
  };

  Cloud.signOut = async () => { await sb.auth.signOut(); Cloud._user = null; Cloud._profile = null; emit(); };

  Cloud.updateProfile = async (patch) => {
    if (!Cloud._user) throw new Error('Not signed in');
    const allowed = ['handle', 'display_name', 'role', 'bio', 'website', 'avatar_url', 'is_public'];
    const clean = {};
    for (const k of allowed) if (k in patch) clean[k] = patch[k];
    if (clean.handle != null) clean.handle = String(clean.handle).toLowerCase().trim();
    const { data, error } = await sb.from('profiles').update(clean).eq('id', Cloud._user.id).select().single();
    if (error) throw error;
    Cloud._profile = data; emit();
    return data;
  };

  Cloud.getPublicProfile = async (handle) => {
    const { data: profile, error } = await sb.from('profiles').select('id, handle, display_name, role, bio, website, avatar_url, created_at').eq('handle', String(handle).toLowerCase()).eq('is_public', true).maybeSingle();
    if (error || !profile) return null;
    const { data: boards } = await sb.from('boards').select('id, name, frames, updated_at').eq('owner', profile.id).eq('is_public', true).order('updated_at', { ascending: false });
    return { profile, boards: boards || [] };
  };

  Cloud.getPublicBoard = async (id) => {
    const { data: board, error } = await sb.from('boards').select('id, name, frames, updated_at, owner').eq('id', id).eq('is_public', true).maybeSingle();
    if (error || !board) return null;
    const { data: owner } = await sb.from('profiles').select('handle, display_name').eq('id', board.owner).maybeSingle();
    return { board, owner };
  };

  // ── Boards ──
  const rowToBoard = (r) => ({ id: r.id, name: r.name, frames: Array.isArray(r.frames) ? r.frames.map(String) : [], isPublic: !!r.is_public, createdAt: Date.parse(r.created_at), updatedAt: Date.parse(r.updated_at), cloud: true });
  Cloud.boards = {
    list: async () => {
      if (!Cloud._user) return [];
      const { data, error } = await sb.from('boards').select('*').eq('owner', Cloud._user.id).order('updated_at', { ascending: false });
      if (error) { console.warn('boards list failed', error); return []; }
      return data.map(rowToBoard);
    },
    create: async ({ name, frames = [], isPublic = false, localId = null }) => {
      const { data, error } = await sb.from('boards').insert({ owner: Cloud._user.id, name, frames, is_public: isPublic, local_id: localId }).select().single();
      if (error) throw error;
      Cloud.track('board_create', { n: frames.length });
      return rowToBoard(data);
    },
    update: async (id, patch) => {
      const row = {};
      if ('name' in patch) row.name = patch.name;
      if ('frames' in patch) row.frames = patch.frames;
      if ('isPublic' in patch) row.is_public = !!patch.isPublic;
      const { data, error } = await sb.from('boards').update(row).eq('id', id).select().single();
      if (error) throw error;
      return rowToBoard(data);
    },
    remove: async (id) => { const { error } = await sb.from('boards').delete().eq('id', id); if (error) throw error; },
    // First sign-in: push this browser's local boards into the account (skip ones already merged)
    mergeLocal: async (localBoards) => {
      if (!Cloud._user || !localBoards.length) return [];
      const existing = await Cloud.boards.list();
      const have = new Set(existing.map(b => b.localId).filter(Boolean));
      const { data: rows } = await sb.from('boards').select('local_id').eq('owner', Cloud._user.id);
      (rows || []).forEach(r => r.local_id && have.add(r.local_id));
      const created = [];
      for (const b of localBoards) {
        if (have.has(b.id) || !b.frames.length) continue;
        try { created.push(await Cloud.boards.create({ name: b.name, frames: b.frames, localId: b.id })); } catch (e) { console.warn('merge failed for', b.name, e); }
      }
      if (created.length) Cloud.track('boards_merged', { n: created.length });
      return created;
    },
  };

  // ── Analytics (fire and forget; never blocks the UI) ──
  Cloud.track = (name, props) => {
    try {
      sb.from('events').insert({ name, props: props || {}, user_id: Cloud._user ? Cloud._user.id : null, session_id: sessionId }).then(() => {}, () => {});
    } catch {}
  };

  window.BerwazCloud = Cloud;
})();
