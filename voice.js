/* Browser speech only: no audio uploads or speech API calls from this app. */
(() => {
  const languages = {
    spanish: 'es-ES', español: 'es-ES', mandarin: 'zh-CN', chinese: 'zh-CN',
    'mandarin chinese': 'zh-CN', 'chinese (mandarin)': 'zh-CN',
    中文: 'zh-CN', english: 'en-US', french: 'fr-FR', german: 'de-DE',
    hindi: 'hi-IN', japanese: 'ja-JP'
  };
  const defaults = {
    'lead-alex-rivera': 'es-ES', 'lead-mei-chen': 'zh-CN',
    'lead-hana-okonkwo': 'en-US', 'lead-luis-ortega': 'en-US'
  };
  class HelioVoice {
    constructor({onTranscript, onState, onStatus}) {
      this.Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      this.synth = window.speechSynthesis;
      this.Utterance = window.SpeechSynthesisUtterance;
      this.onTranscript = onTranscript;
      this.onState = onState;
      this.onStatus = onStatus;
      this.locales = new Map();
      this.listening = false;
      this.speaking = false;
      this.savedReply = null;
    }
    get canListen() { return !!this.Recognition; }
    get canSpeak() { return !!(this.synth && this.Utterance); }
    locale(language) {
      if (!language || language === 'auto') return this.locales.get(this.leadId) || defaults[this.leadId] || 'en-US';
      const key = language.trim().toLowerCase();
      return languages[key] || (/^[a-z]{2}(?:-[a-z]{2})?$/i.test(key) ? language : this.locale());
    }
    setLead(id, language) {
      this.stopListening();
      this.clearReply();
      this.leadId = id;
      if (language && !this.locales.has(id)) this.locales.set(id, this.locale(language));
      this.onState();
    }
    useFacts(facts) {
      // Prefer the latest explicit remembered preference over the initial defaults.
      // Unknown language or a name alone never establishes a preference.
      const ordered = [...(facts.results || [])].sort((a, b) => (b.mentioned_at || '').localeCompare(a.mentioned_at || ''));
      for (const fact of ordered) {
        const match = (fact.text || '').match(/(?:prefers?|preferred language(?: is)?|language preference(?: is)?|(?:requested|asked|wants) to (?:continue|speak|communicate) in)\s*[:=-]?\s*(?:to (?:speak|communicate) in\s+)?(Spanish|Mandarin|Chinese|English|French|German|Hindi|Japanese)\b/i);
        if (match) { this.locales.set(this.leadId, this.locale(match[1])); return; }
      }
    }
    listen(language, initialText) {
      if (this.listening) { this.stopListening(); return; }
      if (!this.canListen) { this.onStatus('Listening is unavailable in this browser. You can still type a reply.'); return; }
      this.stopSpeaking();
      const recognition = new this.Recognition();
      recognition.lang = this.locale(language);
      recognition.interimResults = true;
      recognition.continuous = false;
      this.recognition = recognition;
      recognition.onresult = event => {
        if (this.recognition !== recognition) return;
        const transcript = Array.from(event.results).map(result => result[0].transcript).join(' ').trim();
        this.onTranscript([initialText.trim(), transcript].filter(Boolean).join(' '));
      };
      recognition.onerror = event => {
        if (this.recognition !== recognition) return;
        const messages = {
          'not-allowed': 'Microphone permission was denied. Allow it in your browser or type a reply.',
          'audio-capture': 'No microphone is available. You can still type a reply.',
          'no-speech': 'No speech was detected. Try Listen again or type a reply.',
          network: 'Browser speech recognition is unavailable. Try again or type a reply.'
        };
        this.onStatus(messages[event.error] || 'Listening stopped. You can still type a reply.');
      };
      recognition.onend = () => {
        if (this.recognition !== recognition) return;
        this.recognition = null;
        this.listening = false;
        this.onState();
      };
      try {
        this.listening = true;
        this.onState();
        recognition.start();
        this.onStatus('Listening in ' + recognition.lang + '… Review the transcript, then Generate & remember reply.');
      } catch (_) {
        this.recognition = null;
        this.listening = false;
        this.onState();
        this.onStatus('Could not start the microphone. Check browser permission or type a reply.');
      }
    }
    stopListening() {
      const recognition = this.recognition;
      this.recognition = null;
      this.listening = false;
      if (recognition) recognition.abort();
      this.onState();
    }
    clearReply() {
      this.stopSpeaking();
      this.savedReply = null;
      this.onState();
    }
    rememberSaved(result) {
      this.savedReply = null;
      if (result.saved === true && result.reply && result.language) {
        const locale = this.locale(result.language);
        this.locales.set(this.leadId, locale);
        this.savedReply = {text: result.reply, locale, leadId: this.leadId};
      }
      this.onState();
    }
    stopSpeaking() {
      this.utterance = null;
      this.speaking = false;
      if (this.synth) this.synth.cancel();
      this.onState();
    }
    speak() {
      if (this.speaking) { this.stopSpeaking(); return; }
      if (!this.canSpeak) { this.onStatus('Speech playback is unavailable in this browser. The saved reply is shown below.'); return; }
      if (!this.savedReply || this.savedReply.leadId !== this.leadId) {
        this.onStatus('Generate & remember a reply successfully before using Speak.'); return;
      }
      this.stopListening();
      this.synth.cancel();
      const utterance = new this.Utterance(this.savedReply.text);
      utterance.lang = this.savedReply.locale;
      const voices = this.synth.getVoices();
      const matching = voices.find(voice => voice.lang.toLowerCase() === utterance.lang.toLowerCase()) ||
        voices.find(voice => voice.lang.split('-')[0] === utterance.lang.split('-')[0]);
      if (matching) utterance.voice = matching;
      this.utterance = utterance;
      this.speaking = true;
      this.onState();
      utterance.onend = () => {
        if (this.utterance !== utterance) return;
        this.speaking = false; this.utterance = null; this.onState();
        this.onStatus('Saved reply spoken in ' + utterance.lang + '. Use Speak to replay.');
      };
      utterance.onerror = () => {
        if (this.utterance !== utterance) return;
        this.speaking = false; this.utterance = null; this.onState();
        this.onStatus('Browser could not play speech. Check available voices and audio, then click Speak to retry.');
      };
      this.onStatus('Speaking the saved reply in ' + utterance.lang + '…');
      try { this.synth.speak(utterance); } catch (_) { utterance.onerror(); }
    }
  }
  window.HelioVoice = HelioVoice;
})();
