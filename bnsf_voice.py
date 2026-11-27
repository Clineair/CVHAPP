"""Hands-free BNSF not-sprayed voice commands.

The state machine is pure Python so tests can run it without a microphone.
The browser piece uses the Web Speech API and speechSynthesis. No paid
speech service is required. The manual Not sprayed buttons stay available.
"""
from __future__ import annotations

import re

import bnsf_daily_report as dr

VOICE_PHASES = ("off", "listening", "armed", "tracking", "reason")
_FILLERS = {"please", "the", "a", "uh", "um", "hey", "ok", "okay", "now"}
_MP_WORDS = {"milepost", "mile", "post", "mp"}

# Shown in the app and kept honest on purpose. Continuous listening on an
# iPhone is not something this page can promise.
VOICE_COMMAND_HELP = """
Voice commands use the phone's own speech recognition and spoken prompts. No extra account is required. The helmet mic is used only when the phone is already routing the microphone to the PMA8000BT in TEL mode. Spoken prompts come back through whatever speaker the phone is using, which is the helmet when that Bluetooth headset is the active audio route. This page cannot force that route.

The screen has to stay on and this page has to stay in front. The phone asks for the microphone the first time. After one tap on Voice commands, say "Activate milepost", then "Start", then "Stop", then the reason, and pause. "Cancel" drops the stretch you are on. If listening stalls, the buttons below still work.

iPhone Safari: continuous listening is not reliable. Safari usually ends recognition after each phrase, and starting it again can fail until you tap Voice commands again. A home-screen icon often cannot use the microphone; open this app in Safari itself. The screen Wake Lock works on iOS 16.4 and newer only while Safari is visible. If the mic drops, use Not sprayed (voice) or Mark MP.

Android Chrome: this is the reliable path. Listening stays up, and if Chrome ends a pause it starts again on its own. The Wake Lock holds the screen on while this page is open. Allow the microphone when Chrome asks. A connected Bluetooth headset is used when Android treats it as the default mic.

Samsung Internet: the same path as Chrome when that browser exposes speech recognition. If it does not, this page says so and the two buttons below are the fallback. Wake Lock depends on the Samsung Internet version.

Other browsers: if speech recognition is missing, voice commands stay off and the buttons below are how you log a stretch.
""".strip()

UNSUPPORTED_BROWSER_MESSAGE = (
    "This browser cannot run voice commands. Use Not sprayed (voice) or Mark MP."
)


def voice_support_message(info):
    """Message when the browser cannot listen. Blank when recognition exists."""
    info = info or {}
    if info.get("recognition"):
        if info.get("platform") == "ios-safari" and info.get("standalone"):
            return (
                "A home-screen icon on iPhone often cannot use the microphone. "
                "Open this page in Safari. The buttons below work either way."
            )
        return ""
    browser = info.get("platform") or "this browser"
    return "%s (%s)." % (UNSUPPORTED_BROWSER_MESSAGE[:-1], browser)


def new_voice_session():
    return {"phase": "off", "start": None, "end": None, "log": []}


def _words(text):
    cleaned = re.sub(r"[^a-z0-9\s]", " ", dr._cell(text).lower().replace("-", " "))
    return [word for word in cleaned.split() if word]


def match_voice_command(text):
    """Return activate, start, stop, cancel, or None.

    Close variants count ("activate mile post"). A long noisy sentence that
    merely contains one of the words does not.
    """
    words = _words(text)
    if not words:
        return None
    content = [word for word in words if word not in _FILLERS]
    if not content:
        return None
    if content[0] == "cancel" and len(content) <= 4:
        return "cancel"
    if content[:2] == ["never", "mind"] or content[:2] == ["scratch", "that"]:
        return "cancel"
    if "activate" in words:
        tail = " ".join(words[words.index("activate") + 1:])
        if re.search(r"\bmilepost\b|\bmile post\b|\bmp\b", tail):
            return "activate"
    if content[0] == "start" and len(content) <= 3 and all(word in {"start"} | _MP_WORDS for word in content):
        return "start"
    if content[0] == "stop" and len(content) <= 3 and all(word in {"stop"} | _MP_WORDS for word in content):
        return "stop"
    return None


def _clone(session):
    session = session or new_voice_session()
    start = dict(session["start"]) if isinstance(session.get("start"), dict) else None
    end = dict(session["end"]) if isinstance(session.get("end"), dict) else None
    return {
        "phase": session.get("phase") or "off",
        "start": start,
        "end": end,
        "log": list(session.get("log") or []),
    }


def _speak_mp(prefix, mp):
    if mp:
        return "%s, milepost %s." % (prefix, mp)
    return "%s, no milepost." % (prefix,)


def _capture(lat, lon, now, aircraft, points):
    if lat is None or lon is None:
        return dr.capture_not_sprayed_fix(now=now, aircraft=aircraft)
    return dr.capture_not_sprayed_fix(lat=lat, lon=lon, now=now, aircraft=aircraft, points=points)


def build_stretch_row(start, end, reason, transcript, aircraft=""):
    """One pending not-sprayed row from a start fix and an end fix.

    Both posts are the GPS tenth-mile snaps. A milepost spoken in the reason
    replaces the start post and is taken out of the reason text.
    """
    start = start or {}
    end = end or {}
    gps_start = dr.format_not_sprayed_mp(start.get("MP"))
    gps_end = dr.format_not_sprayed_mp(end.get("MP"))
    start_mp, end_mp = gps_start, gps_end
    source = "GPS" if (start_mp or end_mp) else ""
    spoken = dr.parse_not_sprayed_speech(reason)
    if spoken.get("mp") is not None:
        start_mp = dr.format_not_sprayed_mp(spoken["mp"])
        reason = spoken.get("reason") or ""
        source = "Spoken"
    if start_mp and end_mp:
        span = "%s to %s" % (start_mp, end_mp)
    else:
        span = start_mp or end_mp
    gps_span = "%s to %s" % (gps_start, gps_end) if gps_start and gps_end else (gps_start or gps_end)
    row = {
        "id": start.get("id") or dr.new_entry_id("NS"),
        "Date": start.get("Date") or end.get("Date") or "",
        "Date display": start.get("Date display") or end.get("Date display") or "",
        "Time": start.get("Time") or "",
        "Time Start": start.get("Time") or "",
        "Time End": end.get("Time") or "",
        "Timestamp": start.get("Timestamp") or end.get("Timestamp") or "",
        "MP": span,
        "MP Start": start_mp,
        "MP End": end_mp,
        "MP source": source,
        "GPS MP": gps_span,
        "Subdivision": start.get("Subdivision") or end.get("Subdivision") or "",
        "Division": start.get("Division") or end.get("Division") or "",
        "Reason": dr._cell(reason),
        "Aircraft": dr.aircraft_id(aircraft or start.get("Aircraft") or end.get("Aircraft")),
        "Transcript": dr._cell(transcript),
        "Status": dr.NOT_SPRAYED_STATUS,
    }
    return dr.normalize_not_sprayed([row])[0]


def apply_voice_command(session, text, kind="utterance", now=None, lat=None, lon=None, points=None, aircraft=""):
    """Advance the cockpit flow by one thing the pilot said.

    kind is "utterance", "pause" (end of the reason), "power-on", or "power-off".
    Returns (session, outcome). outcome has speak, row, and ignored.
    Commands that arrive in the wrong phase do not save a row.
    """
    state = _clone(session)
    outcome = {"speak": "", "row": None, "ignored": False, "phase": state["phase"]}
    kind = kind or "utterance"
    heard = dr._cell(text)

    if kind == "power-off":
        state = new_voice_session()
        outcome["phase"] = "off"
        outcome["speak"] = "Voice commands off."
        return state, outcome

    if kind == "power-on":
        state = new_voice_session()
        state["phase"] = "listening"
        outcome["phase"] = "listening"
        outcome["speak"] = "Voice commands on. Say activate milepost."
        return state, outcome

    if state["phase"] == "off":
        outcome["ignored"] = True
        return state, outcome

    if kind == "pause":
        if state["phase"] != "reason" or not state.get("start") or not state.get("end"):
            outcome["ignored"] = True
            outcome["phase"] = state["phase"]
            return state, outcome
        reason = heard
        transcript = " | ".join([item for item in state["log"] + [reason] if item])
        row = build_stretch_row(state["start"], state["end"], reason, transcript, aircraft=aircraft)
        state = new_voice_session()
        state["phase"] = "listening"
        outcome["speak"] = "Saved."
        outcome["row"] = row
        outcome["phase"] = "listening"
        return state, outcome

    command = match_voice_command(heard)
    phase = state["phase"]

    if command == "cancel":
        if phase in {"armed", "tracking", "reason"}:
            state = new_voice_session()
            state["phase"] = "listening"
            outcome["speak"] = "Cancelled."
            outcome["phase"] = "listening"
            return state, outcome
        outcome["ignored"] = True
        outcome["phase"] = phase
        return state, outcome

    if command == "activate":
        state = new_voice_session()
        state["phase"] = "armed"
        state["log"] = [heard]
        outcome["speak"] = "Milepost armed."
        outcome["phase"] = "armed"
        return state, outcome

    if phase == "reason":
        # "Stop" alone while the reason is expected drops the stretch.
        # Anything else waits for the pause event that carries the reason.
        if command == "stop":
            state = new_voice_session()
            state["phase"] = "listening"
            outcome["speak"] = "Cancelled."
            outcome["phase"] = "listening"
            return state, outcome
        outcome["ignored"] = True
        outcome["phase"] = phase
        return state, outcome

    if command == "start":
        if phase != "armed":
            outcome["ignored"] = True
            outcome["speak"] = "Say activate milepost." if phase == "listening" else ""
            outcome["phase"] = phase
            return state, outcome
        fix = _capture(lat, lon, now, aircraft, points)
        state["start"] = fix
        state["end"] = None
        state["phase"] = "tracking"
        state["log"] = list(state["log"]) + [heard]
        outcome["speak"] = _speak_mp("Start", fix.get("MP"))
        outcome["phase"] = "tracking"
        return state, outcome

    if command == "stop":
        if phase != "tracking" or not state.get("start"):
            outcome["ignored"] = True
            outcome["speak"] = "Say start." if phase == "armed" else "Say activate milepost."
            outcome["phase"] = phase
            return state, outcome
        fix = _capture(lat, lon, now, aircraft, points)
        state["end"] = fix
        state["phase"] = "reason"
        state["log"] = list(state["log"]) + [heard]
        outcome["speak"] = _speak_mp("Stop", fix.get("MP")) + " Why not sprayed?"
        outcome["phase"] = "reason"
        return state, outcome

    outcome["ignored"] = True
    outcome["phase"] = phase
    return state, outcome


def voice_phase_label(phase):
    return {
        "off": "Voice commands are off.",
        "listening": "Listening. Say activate milepost.",
        "armed": "Milepost armed. Say start.",
        "tracking": "Tracking. Say stop at the end of the stretch.",
        "reason": "Say why it was not sprayed, then pause.",
    }.get(phase or "off", "Voice commands are off.")


_VOICE_COMPONENT = None

_VOICE_JS = r"""
export default function(component) {
  const { data, setTriggerValue, setStateValue, parentElement } = component;
  const incoming = data || {};
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  const ua = navigator.userAgent || "";
  const standalone = window.navigator.standalone === true ||
    (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches);
  let platform = "other";
  if (/iPhone|iPad|iPod/i.test(ua)) platform = "ios-safari";
  else if (/SamsungBrowser/i.test(ua)) platform = "samsung-internet";
  else if (/Android/i.test(ua) && /Chrome/i.test(ua)) platform = "android-chrome";
  else if (/Android/i.test(ua)) platform = "android-other";

  const support = {
    recognition: !!Recognition,
    speechSynthesis: typeof window.speechSynthesis !== "undefined",
    wakeLock: !!(navigator.wakeLock && navigator.wakeLock.request),
    platform: platform,
    standalone: !!standalone,
    continuous: platform === "android-chrome" || platform === "samsung-internet"
  };

  const root = document.createElement("div");
  root.className = "cvh-voice";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "cvh-voice-btn";
  const status = document.createElement("div");
  status.className = "cvh-voice-status";
  const heard = document.createElement("div");
  heard.className = "cvh-voice-heard";
  root.appendChild(button);
  root.appendChild(status);
  root.appendChild(heard);
  parentElement.appendChild(root);

  let recognition = null;
  let listening = false;
  let watchId = null;
  let wakeLock = null;
  let lastLat = null;
  let lastLon = null;
  let reasonBuffer = "";
  let pauseTimer = null;
  let restartTimer = null;
  let seq = Number(sessionStorage.getItem("cvh-voice-seq") || "0");
  const spokenKey = "cvh-voice-spoken-id";

  function nextSeq() {
    seq += 1;
    sessionStorage.setItem("cvh-voice-seq", String(seq));
    return seq;
  }

  function setStatus(text) {
    status.textContent = text || "";
  }

  function phaseLabel(phase) {
    if (!incoming.enabled) return "Available while spraying.";
    if (!Recognition) return "This browser has no speech recognition. Use the buttons below.";
    if (phase === "armed") return "Milepost armed. Say start.";
    if (phase === "tracking") return "Tracking. Say stop at the end of the stretch.";
    if (phase === "reason") return "Say why it was not sprayed, then pause.";
    if (phase === "listening" || listening) return "Listening. Say activate milepost.";
    return "Tap once. Then say activate milepost, start, and stop.";
  }

  function send(payload) {
    payload.seq = nextSeq();
    payload.lat = lastLat;
    payload.lon = lastLon;
    try {
      setTriggerValue("heard", payload);
    } catch (err) {
      setStatus("Could not send that command. Tap Voice commands again.");
    }
  }

  function clearPause() {
    if (pauseTimer) {
      clearTimeout(pauseTimer);
      pauseTimer = null;
    }
  }

  async function requestWake() {
    if (!navigator.wakeLock || !navigator.wakeLock.request) return;
    try {
      wakeLock = await navigator.wakeLock.request("screen");
    } catch (err) {
      wakeLock = null;
    }
  }

  function releaseWake() {
    if (wakeLock) {
      wakeLock.release().catch(function() {});
      wakeLock = null;
    }
  }

  function stopWatch() {
    if (watchId !== null && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchId);
      watchId = null;
    }
  }

  function startWatch() {
    if (!navigator.geolocation || watchId !== null) return;
    watchId = navigator.geolocation.watchPosition(
      function(pos) {
        lastLat = pos.coords.latitude;
        lastLon = pos.coords.longitude;
      },
      function() {},
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 8000 }
    );
  }

  function stopRec() {
    listening = false;
    clearPause();
    if (restartTimer) {
      clearTimeout(restartTimer);
      restartTimer = null;
    }
    if (recognition) {
      try { recognition.onend = null; recognition.stop(); } catch (err) {}
    }
  }

  function scheduleRestart() {
    if (!listening || !incoming.enabled) return;
    if (restartTimer) clearTimeout(restartTimer);
    restartTimer = setTimeout(function() {
      if (listening) startRec();
    }, 350);
  }

  function startRec() {
    if (!Recognition || !incoming.enabled) {
      setStatus(phaseLabel(incoming.phase));
      return;
    }
    if (!recognition) {
      recognition = new Recognition();
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.continuous = true;
      recognition.onresult = function(event) {
        let text = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) text += event.results[i][0].transcript;
        }
        text = (text || "").trim();
        if (!text) return;
        heard.textContent = text;
        const phase = incoming.phase;
        const lower = text.toLowerCase();
        const commandLike = /^\s*(cancel|activate(\s+the)?\s+mile\s*post|activate\s+mp|stop)\b/i.test(lower);
        if (phase === "reason" && !commandLike) {
          reasonBuffer = (reasonBuffer ? reasonBuffer + " " : "") + text;
          clearPause();
          pauseTimer = setTimeout(function() {
            const reason = reasonBuffer.trim();
            reasonBuffer = "";
            if (reason) send({ kind: "pause", text: reason });
          }, 2200);
          return;
        }
        if (commandLike && phase === "reason") {
          clearPause();
          reasonBuffer = "";
        }
        send({ kind: "utterance", text: text });
      };
      recognition.onerror = function(event) {
        const code = event && event.error ? event.error : "";
        if (code === "not-allowed" || code === "service-not-allowed") {
          listening = false;
          setStatus("Microphone blocked. Tap Voice commands again, or use the buttons below.");
        }
      };
      recognition.onend = function() {
        if (listening) scheduleRestart();
      };
    }
    try {
      recognition.start();
      listening = true;
      setStatus(phaseLabel(incoming.phase));
    } catch (err) {
      if (String(err && err.name) === "InvalidStateError") {
        listening = true;
        return;
      }
      setStatus("Listening did not start. Tap Voice commands again. On iPhone this is common after a pause.");
    }
  }

  function speak(text, speakId) {
    if (!text || !window.speechSynthesis) return;
    if (String(sessionStorage.getItem(spokenKey) || "") === String(speakId)) return;
    sessionStorage.setItem(spokenKey, String(speakId));
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      utterance.rate = 1;
      window.speechSynthesis.speak(utterance);
      const kick = setInterval(function() {
        if (!window.speechSynthesis.speaking) {
          clearInterval(kick);
          return;
        }
        window.speechSynthesis.resume();
      }, 400);
      setTimeout(function() { clearInterval(kick); }, 8000);
    } catch (err) {}
  }

  button.textContent = incoming.phase && incoming.phase !== "off" ? "Voice commands on" : "Voice commands";
  button.disabled = !incoming.enabled;
  setStatus(phaseLabel(incoming.phase));
  if (incoming.speakText) heard.textContent = incoming.speakText;
  speak(incoming.speakText || "", incoming.speakId || 0);

  button.onclick = function() {
    if (!incoming.enabled) return;
    if (!Recognition) {
      setStatus("This browser has no speech recognition. Use the buttons below.");
      return;
    }
    if (listening || (incoming.phase && incoming.phase !== "off")) {
      stopRec();
      stopWatch();
      releaseWake();
      send({ kind: "power-off", text: "" });
      setStatus("Voice commands are off.");
      return;
    }
    requestWake();
    startWatch();
    startRec();
    send({ kind: "power-on", text: "" });
  };

  if (incoming.enabled && incoming.phase && incoming.phase !== "off") {
    requestWake();
    startWatch();
    startRec();
  } else {
    stopRec();
    stopWatch();
    releaseWake();
  }

  document.addEventListener("visibilitychange", onVisible);
  function onVisible() {
    if (document.visibilityState === "visible" && listening) requestWake();
  }

  if (!sessionStorage.getItem("cvh-voice-support-sent")) {
    sessionStorage.setItem("cvh-voice-support-sent", "1");
    try { setStateValue("support", support); } catch (err) {}
  }

  return function() {
    document.removeEventListener("visibilitychange", onVisible);
    stopRec();
    stopWatch();
    releaseWake();
    if (root.parentNode) root.parentNode.removeChild(root);
  };
}
"""

_VOICE_CSS = """
.cvh-voice { font-family: inherit; }
.cvh-voice-btn {
  width: 100%;
  min-height: 4.4rem;
  font-size: 1.35rem;
  font-weight: 700;
  border: 0;
  border-radius: 0.5rem;
  background: #007bff;
  color: white;
  cursor: pointer;
}
.cvh-voice-btn:disabled {
  background: #d5d8de;
  color: #5c6570;
  cursor: not-allowed;
}
.cvh-voice-status, .cvh-voice-heard {
  margin-top: 0.45rem;
  font-size: 1rem;
  line-height: 1.35;
}
"""


def _voice_component():
    global _VOICE_COMPONENT
    if _VOICE_COMPONENT is None:
        import streamlit as st
        _VOICE_COMPONENT = st.components.v2.component(
            "cvh.bnsf_voice_commands",
            js=_VOICE_JS,
            css=_VOICE_CSS,
        )
    return _VOICE_COMPONENT


def render_voice_commands(enabled, session, speak, aircraft="", now=None, points=None, on_save=None):
    """Mount the listener. Returns (session, speak, saved_row).

    speak is {"id": int, "text": str}. A new id asks the phone to say the text.
    """
    import streamlit as st

    session = _clone(session)
    speak = dict(speak or {"id": 0, "text": ""})
    saved = None
    if not enabled and session.get("phase") not in {None, "off"}:
        session = new_voice_session()
        speak = {"id": int(speak.get("id") or 0) + 1, "text": ""}

    try:
        component = _voice_component()
        result = component(
            key="bnsf_voice_commands",
            data={
                "enabled": bool(enabled),
                "phase": session.get("phase") or "off",
                "speakId": int(speak.get("id") or 0),
                "speakText": speak.get("text") or "",
            },
            on_heard_change=lambda: None,
            on_support_change=lambda: None,
        )
    except Exception as exc:
        st.error("Voice commands did not start (%s). Use Not sprayed (voice) or Mark MP." % exc)
        return session, speak, None

    support = None
    event = None
    if result is not None:
        support = result.get("support") if hasattr(result, "get") else None
        event = result.get("heard") if hasattr(result, "get") else None
    message = voice_support_message(support)
    if message:
        st.warning(message)

    if isinstance(event, dict) and enabled:
        seq = event.get("seq")
        last = st.session_state.get("bnsf_voice_last_seq")
        if seq is not None and seq != last:
            st.session_state.bnsf_voice_last_seq = seq
            lat = event.get("lat")
            lon = event.get("lon")
            session, outcome = apply_voice_command(
                session,
                event.get("text") or "",
                kind=event.get("kind") or "utterance",
                now=now,
                lat=lat,
                lon=lon,
                points=points,
                aircraft=aircraft,
            )
            if outcome.get("speak"):
                speak = {"id": int(speak.get("id") or 0) + 1, "text": outcome["speak"]}
            saved = outcome.get("row")
            st.session_state.bnsf_voice_session = session
            st.session_state.bnsf_voice_speak = speak
            if saved and on_save:
                on_save(saved)
            if saved or outcome.get("speak"):
                st.rerun()
    return session, speak, saved
