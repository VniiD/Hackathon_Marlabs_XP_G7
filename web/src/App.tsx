import { useEffect, useState, type ReactNode } from "react";

import { api, API_MODE, USING_MOCKS, type LoginProfile } from "./api";
import { CopilotChat } from "./components/CopilotChat";
import { Avatar } from "./components/ui";
import { APP_NAME } from "./lib";
import { AdvisorClient } from "./screens/AdvisorClient";
import { Agenda } from "./screens/Agenda";
import { AdvisorHome } from "./screens/AdvisorHome";
import { ClientHome } from "./screens/ClientHome";
import { Onboarding } from "./screens/Onboarding";
import { ProfilePicker } from "./screens/ProfilePicker";

type Route =
  | { page: "home" }
  | { page: "onboarding" }
  | { page: "chat" }
  | { page: "agenda" }
  | { page: "client"; id: number };

interface ShellProps {
  session: LoginProfile;
  tabs?: { page: "home" | "chat" | "agenda"; label: string }[];
  current?: string;
  onNavigate: (route: Route) => void;
  onExit: () => void;
  children: ReactNode;
}

function Shell({ session, tabs = [], current, onNavigate, onExit, children }: ShellProps) {
  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" type="button" onClick={() => onNavigate({ page: "home" })}>
          {APP_NAME}
        </button>
        <nav aria-label="Seções">
          {tabs.map((t) => (
            <button
              key={t.page}
              type="button"
              className={current === t.page ? "tab is-active" : "tab"}
              aria-current={current === t.page ? "page" : undefined}
              onClick={() => onNavigate({ page: t.page })}
            >
              {t.label}
            </button>
          ))}
        </nav>
        {USING_MOCKS && (
          <span className="tag">
            {API_MODE === "partial" ? "Demonstração · agenda e chat reais" : "Dados de demonstração"}
          </span>
        )}
        <button className="who" type="button" onClick={onExit} title="Trocar de perfil">
          <Avatar name={session.name} size="sm" />
          <span className="who-text">
            <span className="who-name">{session.name}</span>
            <span className="who-action">Trocar de perfil</span>
          </span>
        </button>
      </header>
      <main className="page">{children}</main>
    </div>
  );
}

const CLIENT_TABS = [
  { page: "home" as const, label: "Minha carteira" },
  { page: "agenda" as const, label: "Agenda" },
  { page: "chat" as const, label: "Conversar" },
];

const ADVISOR_TABS = [
  { page: "home" as const, label: "Painel" },
  { page: "agenda" as const, label: "Agenda" },
];

const STORAGE_KEY = "xpinc.session";

interface Saved {
  session: LoginProfile;
  route: Route;
}

// O navegador lembra quem entrou e em qual tela estava, para o F5 não deslogar.
function readSaved(): Saved | null {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
  } catch {
    return null;
  }
}

function writeSaved(saved: Saved | null) {
  try {
    if (saved) localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Sem armazenamento (aba anônima): a sessão só não sobrevive ao F5.
  }
}

export function App() {
  const [saved] = useState(readSaved);
  const [session, setSession] = useState<LoginProfile | null>(null);
  const [route, setRoute] = useState<Route>(saved?.route ?? { page: "home" });
  // Confere no backend se o usuário salvo ainda existe antes de restaurar.
  const [restoring, setRestoring] = useState(saved !== null);

  useEffect(() => {
    if (!saved) return;
    api
      .listProfiles()
      .then((profiles) => {
        const found = profiles.find(
          (p) => p.id === saved.session.id && p.role === saved.session.role,
        );
        if (found) setSession(found);
        if (found?.needs_onboarding) setRoute({ page: "onboarding" });
      })
      .finally(() => setRestoring(false));
  }, [saved]);

  useEffect(() => {
    if (!restoring) writeSaved(session ? { session, route } : null);
  }, [session, route, restoring]);

  function enter(profile: LoginProfile) {
    setSession(profile);
    setRoute({ page: profile.needs_onboarding ? "onboarding" : "home" });
  }

  if (restoring) {
    return (
      <p className="state" role="status">
        Carregando sua sessão…
      </p>
    );
  }

  if (!session) return <ProfilePicker onEnter={enter} />;

  const exit = () => setSession(null);

  if (route.page === "onboarding") {
    return (
      <Onboarding
        profile={session}
        onEnter={() => {
          setSession({ ...session, needs_onboarding: false });
          setRoute({ page: "home" });
        }}
        onExit={exit}
      />
    );
  }

  if (session.role === "ADVISOR") {
    return (
      <Shell
        session={session}
        tabs={ADVISOR_TABS}
        current={route.page === "client" ? "home" : route.page}
        onNavigate={setRoute}
        onExit={exit}
      >
        {route.page === "client" ? (
          <AdvisorClient
            key={route.id}
            advisorId={session.id}
            clientId={route.id}
            onBack={() => setRoute({ page: "home" })}
          />
        ) : route.page === "agenda" ? (
          <Agenda profile={session} onOpenClient={(id) => setRoute({ page: "client", id })} />
        ) : (
          <AdvisorHome
            advisor={session}
            onOpenClient={(id) => setRoute({ page: "client", id })}
          />
        )}
      </Shell>
    );
  }

  return (
    <Shell
      session={session}
      tabs={CLIENT_TABS}
      current={route.page}
      onNavigate={setRoute}
      onExit={exit}
    >
      {route.page === "chat" ? (
        <CopilotChat clientId={session.id} clientName={session.name} />
      ) : route.page === "agenda" ? (
        <Agenda profile={session} />
      ) : (
        <ClientHome
          profile={session}
          onOpenProfile={() => setRoute({ page: "onboarding" })}
          onOpenChat={() => setRoute({ page: "chat" })}
        />
      )}
    </Shell>
  );
}
