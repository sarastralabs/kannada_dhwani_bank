import { useEffect, useState } from "react";
import {
  base64ToAudioUrl,
  fetchCloudSettings,
  testCloudKey,
  updateCloudSettings,
  type CloudProvider,
  type CloudSettings,
  type CloudSettingsUpdate,
  type CloudStage,
  type CloudStageStatus,
} from "../../api/client";
import { unlockAudio } from "../../utils/playAudio";
import { Badge, Card, ErrorNote, Loading } from "./shared";

const STAGES: { id: CloudStage; en: string; kn: string; local: string }[] = [
  { id: "stt", en: "Listening", kn: "ಕೇಳುವುದು", local: "Whisper on this PC" },
  { id: "translation", en: "Understanding", kn: "ಅರ್ಥಮಾಡಿಕೊಳ್ಳುವುದು", local: "IndicTrans2 on this PC" },
  { id: "tts", en: "Speaking", kn: "ಮಾತನಾಡುವುದು", local: "Parler voice server" },
];

const ERROR_TEXT: Record<string, string> = {
  quota: "Free credits used up",
  auth: "Key not accepted",
  rate_limit: "Too many requests",
  network: "No internet",
  server: "Sarvam service error",
  bad_request: "Request rejected",
};

function stageBadge(s: CloudStageStatus, keySet: boolean) {
  if (s.provider === "local") return null;
  if (!keySet) return <Badge tone="amber">No key · using local</Badge>;
  if (s.ok === false) {
    const label = ERROR_TEXT[s.error_kind ?? ""] ?? "Error";
    return <Badge tone="red">{s.using_local_now ? `${label} · using local` : label}</Badge>;
  }
  if (s.ok) return <Badge tone="green">Working{s.ms ? ` · ${s.ms} ms` : ""}</Badge>;
  return <Badge tone="blue">Ready · not used yet</Badge>;
}

export function SpeechEngines({ apiOnline }: { apiOnline: boolean | null }) {
  const [cfg, setCfg] = useState<CloudSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [keyDraft, setKeyDraft] = useState("");

  const load = () =>
    fetchCloudSettings()
      .then(setCfg)
      .catch((err) => setError(err instanceof Error ? err.message : "Speech engine settings unavailable"));

  useEffect(() => {
    if (apiOnline === false) return;
    void load();
    // Re-check so "Open-source" Speaking unlocks once the voice server comes up.
    const id = window.setInterval(() => {
      fetchCloudSettings()
        .then(setCfg)
        .catch(() => undefined);
    }, 20000);
    return () => window.clearInterval(id);
  }, [apiOnline]);

  const flash = (text: string) => {
    setNotice(text);
    window.setTimeout(() => setNotice(null), 3200);
  };

  const save = async (changes: CloudSettingsUpdate, label: string, message: string) => {
    setBusy(label);
    setError(null);
    try {
      setCfg(await updateCloudSettings(changes));
      flash(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy(null);
    }
  };

  const play = async (b64?: string) => {
    if (!b64) return;
    await unlockAudio();
    const url = base64ToAudioUrl(b64);
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    await audio.play();
  };

  /** Test the pasted key first; save it only when Sarvam accepts it. */
  const saveKey = async () => {
    const key = keyDraft.trim();
    if (!key) return;
    setBusy("key");
    setError(null);
    try {
      const result = await testCloudKey({ sarvam_api_key: key });
      if (!result.ok) {
        setError(`Key not saved — ${result.message}`);
        return;
      }
      setCfg(await updateCloudSettings({ sarvam_api_key: key }));
      setKeyDraft("");
      flash("Key saved and working — you should hear a sample now");
      await play(result.audio_b64);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not test the key");
    } finally {
      setBusy(null);
    }
  };

  const testSaved = async (voice?: string) => {
    setBusy(voice ? `voice:${voice}` : "test");
    setError(null);
    try {
      const result = await testCloudKey(voice ? { sarvam_voice: voice } : {});
      await load();
      if (!result.ok) {
        setError(result.message);
        return;
      }
      flash(voice ? `Playing ${voice}` : "Sarvam is working");
      await play(result.audio_b64);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setBusy(null);
    }
  };

  if (!cfg) {
    return (
      <Card title="Speech engines" titleKn="ಧ್ವನಿ ಎಂಜಿನ್‌ಗಳು">
        {error ? <ErrorNote message={error} /> : <Loading label="Loading speech engines…" />}
      </Card>
    );
  }

  const voiceOnline = cfg.open_source_voice_online !== false;
  const anySarvam = STAGES.some((s) => cfg.stages[s.id].provider === "sarvam");
  const keyProblem = STAGES.map((s) => cfg.stages[s.id]).find(
    (s) => s.provider === "sarvam" && (s.error_kind === "quota" || s.error_kind === "auth"),
  );

  return (
    <Card title="Speech engines" titleKn="ಧ್ವನಿ ಎಂಜಿನ್‌ಗಳು">
      <p className="ac-lead">
        For each step, use the open-source models (free, private, no internet needed) or {cfg.provider_name} in the
        cloud (one API key with free credits). Changes apply to the next customer turn — no restart.
      </p>

      {keyProblem && (
        <p className="ac-error" role="alert">
          {keyProblem.error_kind === "quota"
            ? "Sarvam free credits are used up. Paste a new API key below."
            : "Sarvam did not accept the API key. Paste a valid key below."}
          {cfg.fallback_local ? " The kiosk is using the open-source models meanwhile." : ""}
        </p>
      )}
      {error && <ErrorNote message={error} />}
      {notice && <p className="ac-toast">{notice}</p>}

      <ul className="ac-engines">
        {STAGES.map((stage) => {
          const s = cfg.stages[stage.id];
          return (
            <li key={stage.id} className="ac-engine">
              <div className="ac-engine-name">
                <strong>{stage.en}</strong>
                <span className="kn ac-sub">{stage.kn}</span>
              </div>
              <div className="ac-seg" role="radiogroup" aria-label={`${stage.en} engine`}>
                {(["local", "sarvam"] as CloudProvider[]).map((p) => (
                  <button
                    key={p}
                    type="button"
                    role="radio"
                    aria-checked={s.provider === p}
                    className={s.provider === p ? "is-on" : ""}
                    disabled={busy !== null || (stage.id === "tts" && p === "local" && !voiceOnline && s.provider !== p)}
                    title={
                      stage.id === "tts" && p === "local" && !voiceOnline
                        ? "Voice server is offline — start it to use the open-source voice"
                        : undefined
                    }
                    onClick={() =>
                      s.provider !== p &&
                      void save(
                        { [stage.id]: p },
                        stage.id,
                        `${stage.en} now uses ${p === "local" ? "the open-source model" : cfg.provider_name}`,
                      )
                    }
                  >
                    {p === "local" ? "Open-source" : cfg.provider_name}
                  </button>
                ))}
              </div>
              <div className="ac-engine-status">
                {stageBadge(s, cfg.key_set)}
                {stage.id === "tts" && !voiceOnline ? (
                  <Badge tone={cfg.key_set ? "amber" : "red"}>
                    {s.provider === "local"
                      ? cfg.key_set
                        ? `Voice server offline · using ${cfg.provider_name}`
                        : "Voice server offline · no voice"
                      : "Voice server offline"}
                  </Badge>
                ) : (
                  s.provider === "local" && <span className="ac-muted">{stage.local}</span>
                )}
              </div>
              {s.provider === "sarvam" && s.ok === false && s.error && <p className="ac-engine-error">{s.error}</p>}
            </li>
          );
        })}
      </ul>

      <div className="ac-engine-grid">
        <section className="ac-engine-box" aria-label="Sarvam API key">
          <h3>{cfg.provider_name} API key</h3>
          <p className="ac-muted">
            {cfg.key_set
              ? `Key ${cfg.key_hint} is in use${cfg.key_source === "env" ? " (from the .env file)" : ""}.`
              : "No key yet. Create one free at dashboard.sarvam.ai."}{" "}
            When credits run out, paste a new key here — it is tested before it is saved.
          </p>
          <div className="ac-key-row">
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder={cfg.key_set ? "Paste a new key to replace it" : "Paste API key"}
              value={keyDraft}
              onChange={(e) => setKeyDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void saveKey()}
              aria-label="Sarvam API key"
            />
            <button
              type="button"
              className="ac-btn ac-btn--gold ac-btn--sm"
              disabled={!keyDraft.trim() || busy !== null}
              onClick={() => void saveKey()}
            >
              {busy === "key" ? "Testing…" : "Test & save"}
            </button>
          </div>
          <div className="ac-key-actions">
            <button
              type="button"
              className="ac-btn ac-btn--outline ac-btn--sm"
              disabled={!cfg.key_set || busy !== null}
              onClick={() => void testSaved()}
            >
              {busy === "test" ? "Testing…" : "Test current key"}
            </button>
            {cfg.key_source === "settings" && (
              <button
                type="button"
                className="ac-btn ac-btn--ghost ac-btn--sm"
                disabled={busy !== null}
                onClick={() => void save({ sarvam_api_key: "" }, "remove", "Saved key removed")}
              >
                Remove key
              </button>
            )}
          </div>
        </section>

        <section className="ac-engine-box" aria-label="Sarvam voice">
          <h3>{cfg.provider_name} voice</h3>
          <p className="ac-muted">
            Used when <strong>Speaking</strong> is set to {cfg.provider_name}. The Suresh / Anu choice above applies
            to the open-source voice.
          </p>
          <div className="ac-key-row">
            <select
              value={cfg.sarvam_voice}
              disabled={busy !== null}
              aria-label="Sarvam voice"
              onChange={(e) => void save({ sarvam_voice: e.target.value }, "voice", `Sarvam voice set to ${e.target.value}`)}
            >
              {cfg.voices.map((v) => (
                <option key={v} value={v}>
                  {v.charAt(0).toUpperCase() + v.slice(1)}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="ac-btn ac-btn--outline ac-btn--sm"
              disabled={!cfg.key_set || busy !== null}
              onClick={() => void testSaved(cfg.sarvam_voice)}
            >
              {busy?.startsWith("voice:") ? "Playing…" : "Play sample"}
            </button>
          </div>
          <label className="ac-check">
            <input
              type="checkbox"
              checked={cfg.fallback_local}
              disabled={busy !== null}
              onChange={(e) =>
                void save(
                  { fallback_local: e.target.checked },
                  "fallback",
                  e.target.checked ? "Open-source backup turned on" : "Open-source backup turned off",
                )
              }
            />
            <span>
              If {cfg.provider_name} fails (no credits, no internet), use the open-source models automatically
              <span className="ac-muted"> — recommended</span>
            </span>
          </label>
        </section>
      </div>

      {anySarvam && !cfg.key_set && (
        <p className="ac-muted ac-engine-foot">
          {cfg.provider_name} is selected but no key is set, so the open-source models are answering.
        </p>
      )}
    </Card>
  );
}
