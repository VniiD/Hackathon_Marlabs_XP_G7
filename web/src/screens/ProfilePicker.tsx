import { useState } from "react";

import { api, type LoginProfile } from "../api";
import { Avatar, Icon, Load } from "../components/ui";
import { APP_NAME, errorText, useAsync } from "../lib";

function ProfileButton({ profile, onEnter }: { profile: LoginProfile; onEnter: () => void }) {
  return (
    <button type="button" className="profile" onClick={onEnter}>
      <Avatar name={profile.name} size="xl" />
      <span className="profile-name">{profile.name}</span>
      {profile.needs_onboarding && <span className="tag tag-accent">Primeiro acesso</span>}
    </button>
  );
}

function SignUp({ onEnter, onCancel }: { onEnter: (p: LoginProfile) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onEnter(await api.signUp(name.trim(), email.trim()));
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <form className="signup" onSubmit={submit}>
      <h2>Criar conta de cliente</h2>
      <label>
        Nome completo
        <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
      </label>
      <label>
        E-mail
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="voce@exemplo.com"
          required
        />
      </label>
      {error && (
        <p className="state-error" role="alert">
          Não foi possível criar a conta: {error}.
        </p>
      )}
      <div className="row-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Voltar
        </button>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Criando conta…" : "Criar conta e continuar"}
        </button>
      </div>
    </form>
  );
}

export function ProfilePicker({ onEnter }: { onEnter: (profile: LoginProfile) => void }) {
  const [creating, setCreating] = useState(false);
  const profiles = useAsync(() => api.listProfiles(), []);

  return (
    <div className="gate">
      <p className="brand brand-lg">{APP_NAME}</p>

      {creating ? (
        <SignUp onEnter={onEnter} onCancel={() => setCreating(false)} />
      ) : (
        <>
          <h1>Quem está acessando?</h1>
          <Load state={profiles} label="os perfis">
            {(list) => (
              <div className="gate-groups">
                <section>
                  <h2>Assessoria</h2>
                  <div className="profiles">
                    {list
                      .filter((p) => p.role === "ADVISOR")
                      .map((p) => (
                        <ProfileButton key={p.id} profile={p} onEnter={() => onEnter(p)} />
                      ))}
                  </div>
                </section>
                <section>
                  <h2>Clientes</h2>
                  <div className="profiles">
                    {list
                      .filter((p) => p.role === "CLIENT")
                      .map((p) => (
                        <ProfileButton key={p.id} profile={p} onEnter={() => onEnter(p)} />
                      ))}
                    <button type="button" className="profile" onClick={() => setCreating(true)}>
                      <span className="avatar avatar-xl avatar-add" aria-hidden="true">
                        <Icon name="plus" size={28} />
                      </span>
                      <span className="profile-name">Criar conta</span>
                    </button>
                  </div>
                </section>
              </div>
            )}
          </Load>
        </>
      )}
    </div>
  );
}
