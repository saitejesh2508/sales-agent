const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '..');

function environment() {
  const spoken = [], recognitions = [], statuses = [], transcripts = [];
  class Recognition {
    constructor() { recognitions.push(this); }
    start() { this.started = true; }
    abort() { this.aborted = true; }
  }
  class Utterance { constructor(text) { this.text = text; } }
  const voices = [{lang: 'en-US'}, {lang: 'es-ES'}, {lang: 'zh-CN'}];
  const window = {
    SpeechRecognition: Recognition, SpeechSynthesisUtterance: Utterance,
    speechSynthesis: {speak: value => spoken.push(value), cancel() {}, getVoices: () => voices},
    addEventListener() {}
  };
  const context = vm.createContext({window, console});
  vm.runInContext(fs.readFileSync(path.join(root, 'voice.js'), 'utf8'), context);
  const voice = new window.HelioVoice({onState() {}, onStatus: value => statuses.push(value), onTranscript: value => transcripts.push(value)});
  return {context, window, voice, spoken, recognitions, statuses, transcripts};
}

test('each lead uses the requested browser locale', () => {
  const {voice} = environment();
  for (const [id, expected] of Object.entries({'lead-alex-rivera': 'es-ES', 'lead-mei-chen': 'zh-CN', 'lead-hana-okonkwo': 'en-US', 'lead-luis-ortega': 'en-US'})) {
    voice.setLead(id); assert.equal(voice.locale(), expected);
  }
});

test('Listen inserts a transcript, never speaks or saves', () => {
  const {voice, recognitions, transcripts, spoken} = environment();
  voice.setLead('lead-alex-rivera'); voice.listen('auto', 'Hola.');
  assert.equal(recognitions[0].lang, 'es-ES');
  recognitions[0].onresult({results: [[{transcript: 'Quiero hablar en español.'}]]});
  assert.equal(transcripts[0], 'Hola. Quiero hablar en español.');
  assert.equal(spoken.length, 0); assert.equal(voice.savedReply, null);
  voice.stopListening(); assert.equal(recognitions[0].aborted, true);
});

test('Spanish speech uses the saved assistant text and a Spanish voice', () => {
  const {voice, spoken} = environment(); voice.setLead('lead-alex-rivera');
  voice.rememberSaved({saved: true, reply: 'Claro, continuemos en español.', language: 'Spanish'});
  assert.equal(spoken.length, 0); voice.speak();
  assert.equal(spoken[0].text, 'Claro, continuemos en español.');
  assert.equal(spoken[0].lang, 'es-ES'); assert.equal(spoken[0].voice.lang, 'es-ES');
});

test('failed retention or missing save acknowledgement can never be spoken', () => {
  const {voice, spoken} = environment(); voice.setLead('lead-alex-rivera');
  for (const saved of [false, undefined, 'true']) {
    voice.rememberSaved({saved, reply: 'Hola', language: 'Spanish'}); voice.speak();
    assert.equal(voice.savedReply, null);
  }
  assert.equal(spoken.length, 0);
});

test('switching leads clears playback and aborts microphone capture', () => {
  const {voice, recognitions, spoken} = environment(); voice.setLead('lead-alex-rivera');
  voice.rememberSaved({saved: true, reply: 'Hola', language: 'Spanish'});
  voice.listen('auto', ''); voice.setLead('lead-mei-chen');
  assert.equal(recognitions[0].aborted, true); voice.speak(); assert.equal(spoken.length, 0);
});

test('Luis stays English until an explicit remembered or saved language update', () => {
  const {voice} = environment(); voice.setLead('lead-luis-ortega');
  voice.useFacts({results: [{text: 'Language preference is unknown.'}]}); assert.equal(voice.locale(), 'en-US');
  voice.useFacts({results: [{text: 'Luis Ortega prefers Spanish.'}]}); assert.equal(voice.locale(), 'es-ES');
  voice.rememberSaved({saved: true, reply: 'Bonjour', language: 'French'}); assert.equal(voice.locale(), 'fr-FR');
  const fresh = environment().voice; fresh.setLead('lead-luis-ortega');
  fresh.useFacts({results: [{text: 'Luis Ortega asked to continue in Spanish.'}]});
  assert.equal(fresh.locale(), 'es-ES');
});

test('unsupported speech APIs leave a typed workflow available', () => {
  const {window, statuses} = environment();
  delete window.SpeechRecognition; delete window.speechSynthesis;
  const voice = new window.HelioVoice({onState() {}, onStatus: value => statuses.push(value), onTranscript() {}});
  assert.equal(voice.canListen, false); assert.equal(voice.canSpeak, false);
  voice.listen('English', ''); voice.speak(); assert.equal(statuses.length, 2);
});

// Exercise the real page submit handler with a deferred API response. This checks
// that typing Spanish cannot trigger speech before the save acknowledgement.
async function pageEnvironment() {
  const env = environment(), elements = new Map();
  class Element {
    constructor() { this.value = ''; this.dataset = {}; this.children = []; this.classList = {remove() {}, toggle() {}}; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute() {}
    reset() { this.wasReset = true; }
  }
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const document = {getElementById: get, createElement: () => new Element(), querySelectorAll: () => []};
  const facts = {results: [{text: 'Alex Rivera prefers Spanish.'}]};
  let resolveReply, posted, created;
  const leads = [{id: 'lead-alex-rivera', name: 'Alex Rivera', company: 'Clínica Norte', stage: 'Meeting'}];
  let transcripts = [], imported;
  const counts = () => Object.fromEntries(['New','Contacted','Responded','Meeting','Won'].map(stage => [stage, leads.filter(lead => lead.stage===stage).length]));
  const briefRequests = [];
  env.context.document = document;
  env.context.fetch = async (url, options) => {
    if (url === '/api/leads' && options?.method === 'POST') {
      created = JSON.parse(options.body);
      const lead = {id: 'lead-priya-nair-test', name: created.name, company: created.company, language: created.language, stage: 'New'};
      leads.push(lead);
      facts.results = [{text: created.note}];
      return {ok: true, json: async () => ({lead, saved: true, note: created.note})};
    }
    if (url === '/api/leads') return {ok: true, json: async () => ({leads, counts: counts()})};
    if (url === '/api/activity') {const lead=leads.find(item=>item.id===JSON.parse(options.body).lead_id);return {ok:true,json:async()=>({stage:lead.stage,transcripts,counts:counts()})};}
    if (url === '/api/insights') return {ok:true,json:async()=>({key_notes:{objection:'Unknown',language:'Spanish',next_step:'Follow up',next_time:'Ask a specific question'}})};
    if (url === '/api/queue') {
      const data=JSON.parse(options.body),lead=leads.find(item=>item.id===data.lead_id);lead.stage='Contacted';transcripts.push({id:'outbound-test',kind:'outbound',channel:data.channel,text:data.text,created_at:'2026-11-07T12:00:00Z'});
      return {ok:true,json:async()=>({saved:true,stage:lead.stage,transcripts,counts:counts()})};
    }
    if (url === '/api/import') {
      imported=JSON.parse(options.body).csv;
      const created=[1,2,3].map(n=>({id:'csv-lead-'+n,name:'CSV Lead '+n,company:'Import Check',language:'English',stage:'New'}));leads.push(...created);
      return {ok:true,json:async()=>({created,errors:[],counts:counts()})};
    }
    if (url === '/api/brief') { briefRequests.push(JSON.parse(options.body).lead_id); return {ok: true, json: async () => ({facts, brief_html: '<p>Brief from selected memory.</p>', generic: {brief_html: '<p>Unknown.</p>', facts: {results: []}}})}; }
    if (url === '/api/outbound') return {ok: true, json: async () => ({facts, drafts: {email: 'Hola', linkedin: 'Hola', x: 'Hola'}})};
    if (url === '/api/reply') {
      posted = JSON.parse(options.body);
      return new Promise(resolve => { resolveReply = result => {
        if(result.saved){leads[0].stage='Responded';transcripts.push({kind:'conversation',channel:'call',text:posted.message+'\n'+result.reply,created_at:'2026-11-07T12:00:01Z'})}
        resolve({ok:true,json:async()=>({...result,facts,stage:leads[0].stage,transcripts,counts:counts()})});
      }; });
    }
    throw Error('Unexpected route');
  };
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const inline = html.split('<script>')[1].split('</script>')[0];
  vm.runInContext(inline, env.context);
  await new Promise(setImmediate);
  return {...env, get, getPosted: () => posted, finish: result => resolveReply(result), getCreated: () => created, briefRequests,getImport:()=>imported};
}

test('typed Alex Spanish submission speaks only after Generate receives saved=true', async () => {
  const env = await pageEnvironment(); env.get('message').value = '¿Podemos continuar en español?';
  env.get('reply-form').onsubmit({preventDefault() {}});
  await new Promise(setImmediate);
  assert.equal(env.getPosted().message, '¿Podemos continuar en español?');
  assert.equal(env.getPosted().lead_id, 'lead-alex-rivera'); assert.equal(env.spoken.length, 0);
  env.finish({saved: true, reply: 'Sí, podemos continuar en español.', language: 'Spanish'});
  await new Promise(setImmediate);
  assert.equal(env.spoken.length, 1); assert.equal(env.spoken[0].lang, 'es-ES');
  assert.equal(env.get('message').value, ''); assert.equal(env.get('speak').disabled, false);
});

test('page preserves input and disables Speak when the save fails', async () => {
  const env = await pageEnvironment(); env.get('message').value = 'Hola';
  env.get('reply-form').onsubmit({preventDefault() {}}); await new Promise(setImmediate);
  env.finish({saved: false, reply: 'Hola Alex', language: 'Spanish', warning: 'Could not save.'});
  await new Promise(setImmediate);
  assert.equal(env.spoken.length, 0); assert.equal(env.get('message').value, 'Hola');
  assert.equal(env.get('speak').disabled, true);
});

test('Add lead form saves the note, lists Priya, and loads her new bank', async () => {
  const env = await pageEnvironment();
  env.get('new-name').value = 'Priya Nair'; env.get('new-company').value = 'Harbour Dental';
  env.get('new-language').value = 'English'; env.get('new-note').value = 'Asked for pricing after 5pm';
  env.get('add-lead-form').onsubmit({preventDefault() {}});
  await new Promise(setImmediate);
  assert.equal(env.getCreated().note, 'Asked for pricing after 5pm');
  assert.equal(env.get('lead-name').textContent, 'Priya Nair');
  assert.equal(env.get('lead-list').children.length, 2);
  assert.equal(env.briefRequests.at(-1), 'lead-priya-nair-test');
  assert.equal(env.get('fact-lines').children[0].textContent, 'Asked for pricing after 5pm');
  assert.equal(env.get('add-lead-form').wasReset, true);
  assert.equal(env.get('listen').disabled, false);
});

test('queueing an email updates Contacted and shows internal outbound text', async () => {
  const env=await pageEnvironment();env.get('queue-email').onclick();await new Promise(setImmediate);
  assert.equal(env.get('stage').value,'Contacted');assert.equal(env.get('count-Contacted').textContent,1);
  assert.equal(env.get('transcripts').children[0].children[0].textContent,'Queued email · Helio only');
  assert.equal(env.get('transcripts').children[0].children[2].textContent,'Hola');
});

test('CSV upload posts file contents and updates New counts and list', async () => {
  const env=await pageEnvironment();const csv=fs.readFileSync(path.join(root,'sample-leads.csv'),'utf8');
  env.get('csv-file').files=[{size:csv.length,text:async()=>csv}];env.get('upload-form').onsubmit({preventDefault(){}});await new Promise(setImmediate);
  assert.equal(env.getImport(),csv);assert.equal(env.get('count-New').textContent,3);
  assert.equal(env.get('lead-list').children.length,4);assert.match(env.get('upload-status').textContent,/3 leads imported as New/);
});
