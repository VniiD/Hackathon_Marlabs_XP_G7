import { api, type LoginProfile, type Meeting } from "../api";
import { Load } from "../components/ui";
import { MeetingAgenda, isUpcoming, needsMyConfirmation } from "../components/MeetingAgenda";
import { useAsync } from "../lib";

async function loadAgenda(profile: LoginProfile) {
  const [meetings, profiles] = await Promise.all([
    profile.role === "ADVISOR" ? api.getMeetings(profile.id) : api.getClientMeetings(profile.id),
    api.listProfiles(),
  ]);
  return { meetings, names: new Map(profiles.map((p) => [p.id, p.name])) };
}

const isOpen = (m: Meeting) => isUpcoming(m) && (m.status === "PENDING" || m.status === "CONFIRMED");

interface Props {
  profile: LoginProfile;
  onOpenClient?: (clientId: number) => void;
}

/** Agenda completa de quem está logado, com as reuniões que esperam sua confirmação no topo. */
export function Agenda({ profile, onOpenClient }: Props) {
  const state = useAsync(() => loadAgenda(profile), [profile.id, profile.role]);

  return (
    <Load state={state} label="a agenda">
      {({ meetings, names }) => {
        const open = meetings.filter(isOpen);
        const mine = open.filter((m) => needsMyConfirmation(m, profile.role)).length;
        const waiting = open.filter((m) => m.status === "PENDING").length - mine;
        return (
          <>
            <header className="page-head">
              <h1>Agenda</h1>
              <p className="muted">
                {mine > 0
                  ? `${mine} ${mine === 1 ? "reunião espera" : "reuniões esperam"} a sua confirmação.`
                  : "Nada esperando a sua confirmação."}{" "}
                {waiting > 0 &&
                  `${waiting} ${waiting === 1 ? "aguarda" : "aguardam"} a confirmação da outra parte.`}
              </p>
            </header>

            <section className="panel">
              <h2>Próximas reuniões</h2>
              <MeetingAgenda
                meetings={meetings}
                viewer={{ id: profile.id, role: profile.role }}
                nameOf={(m) =>
                  names.get(profile.role === "ADVISOR" ? m.client_id : m.advisor_id) ?? "Reunião"
                }
                onOpenClient={profile.role === "ADVISOR" ? onOpenClient : undefined}
              />
            </section>
          </>
        );
      }}
    </Load>
  );
}
