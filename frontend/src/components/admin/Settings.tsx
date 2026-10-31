import { useEffect, useState } from "react";
import {
  base64ToAudioUrl,
  fetchSpeakKannada,
  fetchVoiceSettings,
  updateVoiceSpeaker,
  type VoiceOption,
} from "../../api/client";
import { unlockAudio } from "../../utils/playAudio";
import { Badge, Card, ErrorNote, Icon, Loading } from "./shared";
import { SpeechEngines } from "./SpeechEngines";

const PREVIEW_TEXT = "ನಮಸ್ಕಾರ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?";

interface SettingsProps {
  apiOnline: boolean | null;
  username: string;
  onSignOut: () => void;
}

export function Settings({ apiOnline, username, onSignOut }: SettingsProps) {
  const [options, setOptions] = useState<VoiceOption[]>([]);
  const [speaker, setSpeaker] = useState("");
  const [saving, setSaving] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    fetchVoiceSettings()
      .then((d) => {
        setOptions(d.options);
        setSpeaker(d.speaker);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Voice settings unavailable"));
  }, []);

  const choose = async (id: string) => {
    if (id === speaker || saving) return;
    setSaving(id);
    setError(null);
    try {
      setSpeaker(await updateVoiceSpeaker(id));
      setSaved(`${id} is now the assistant voice`);
      window.setTimeout(() => setSaved(null), 2600);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save voice");
    } finally {
      setSaving(null);
    }
  };

  const preview = async (id: string) => {
    if (apiOnline === false || previewing) return;
    setPreviewing(id);
    setError(null);
    try {
      await unlockAudio();
      const url = base64ToAudioUrl(await fetchSpeakKannada(PREVIEW_TEXT, undefined, id as "Suresh" | "Anu"));
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewing(null);
    }
  };

  return (
    <div className="ac-page">
      {error && <ErrorNote message={error} />}
      {saved && <p className="ac-toast">{saved}</p>}

      <Card title="Assistant voice" titleKn="ಸಹಾಯಕ ಧ್ವನಿ">
        <p className="ac-lead">
          The Kannada voice customers hear for greetings, questions and answers. Changes apply to the next thing the
          assistant says.
        </p>
        {!options.length ? (
          <Loading label="Loading voices…" />
        ) : (
          <div className="ac-voices">
            {options.map((o) => {
              const active = o.id === speaker;
              return (
                <article key={o.id} className={`ac-voice ${active ? "is-active" : ""}`}>
                  <span className="ac-voice-avatar kn" aria-hidden>
                    {o.label_kn.charAt(0)}
                  </span>
                  <div className="ac-voice-text">
                    <h3>
                      <span className="kn">{o.label_kn}</span> · {o.label_en}
                      {active && <Badge tone="gold">In use</Badge>}
                    </h3>
                    <p>{o.description_en}</p>
                    <p className="kn ac-sub">{o.description_kn}</p>
                  </div>
                  <div className="ac-voice-actions">
                    <button
                      type="button"
                      className="ac-btn ac-btn--outline ac-btn--sm"
                      disabled={previewing !== null || apiOnline === false}
                      onClick={() => void preview(o.id)}
                    >
                      <Icon name="play" size={14} /> {previewing === o.id ? "Playing…" : "Play sample"}
                    </button>
                    {!active && (
                      <button
                        type="button"
                        className="ac-btn ac-btn--gold ac-btn--sm"
                        disabled={saving !== null}
                        onClick={() => void choose(o.id)}
                      >
                        {saving === o.id ? "Saving…" : "Use this voice"}
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </Card>

      <SpeechEngines apiOnline={apiOnline} />

      <div className="ac-grid ac-grid--2">
        <Card title="Your session" titleKn="ನಿಮ್ಮ ಲಾಗಿನ್">
          <dl className="ac-kv">
            <div>
              <dt>Signed in as</dt>
              <dd>
                <strong>{username}</strong>
              </dd>
            </div>
            <div>
              <dt>Session</dt>
              <dd className="ac-muted">Ends when the kiosk service restarts — just sign in again.</dd>
            </div>
          </dl>
          <button type="button" className="ac-btn ac-btn--outline" onClick={onSignOut}>
            <Icon name="logout" size={16} /> Sign out
          </button>
        </Card>
      </div>
    </div>
  );
}
