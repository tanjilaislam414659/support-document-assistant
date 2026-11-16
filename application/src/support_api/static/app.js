"use strict";
const $ = id => document.getElementById(id);
const state = {ticket:null, selected:new Map(), dirty:false, dirtyFields:new Set(), busy:false, metadata:null, ready:false};
function node(tag,text,className) { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(className)n.className=className; return n; }
function notice(text,error=false) { const n=$("notice"); n.textContent=text; n.classList.toggle("error",error); n.setAttribute("role",error?"alert":"status"); n.hidden=!text; }
async function api(path,method="GET",body) {
  const r=await fetch(path,{method,headers:body?{"Content-Type":"application/json"}:{},body:body?JSON.stringify(body):undefined});
  let v;try{v=await r.json();}catch{throw new Error("The service returned an unreadable response.");}
  if(!r.ok){const e=new Error(v.error?.message||v.detail||"Request failed.");e.code=v.error?.code;e.status=r.status;throw e;}return v;
}
function errorMessage(e) {
  if(e.status===409&&e.code==="stale_revision") { $("reload-ticket").hidden=false; notice("This draft changed elsewhere. Your unsaved edits are still here. Reload the latest revision before editing or reviewing again.",true); }
  else notice(e.message==="Failed to fetch"?"The local service is unavailable. Check that it is running, then try again.":e.message,true);
}
function safeLink(url,text) {
  const a=node("a",text);try{const parsed=new URL(url);if(parsed.protocol==="https:"){a.href=parsed.href;a.target="_blank";a.rel="noopener noreferrer";}}catch{}return a;
}
function updateControls() {
  const saved=!!state.ticket, pending=state.busy, clean=saved&&!state.dirty; for(const field of document.querySelectorAll("#draft-form input, #draft-form textarea, [data-passage]"))field.disabled=pending; $("load-button").disabled=pending;$("reload-ticket").disabled=pending;
  $("save-button").textContent=saved?"Save new revision":"Create local draft";
  $("save-button").disabled=pending||(saved&&!state.dirty)||(state.metadata&&!state.metadata.capabilities.deterministic_ticket_drafts);
  $("review-button").disabled=pending||!clean||!$("confirm-review").checked;
  $("confirm-review").disabled=pending||!clean;
  $("copy-button").disabled=!clean;
  $("new-draft").disabled=pending;
  $("clear-selection").disabled=pending||!state.selected.size;
  $("selected-count").textContent=state.selected.size+" passage"+(state.selected.size===1?"":"s")+" selected";
  $("review-badge").textContent=!saved?"Not saved":state.dirty?"Unsaved edits":state.ticket.review_state==="review_recorded"?"Review recorded":"Unreviewed";
  $("review-badge").classList.toggle("reviewed",clean&&state.ticket.review_state==="review_recorded");
  if(saved)$("ticket-state").textContent="Draft "+state.ticket.ticket_id+" · revision "+state.ticket.revision+(state.dirty?" · unsaved changes; save before review or copy.":" · "+state.ticket.review_state+".");
}
function changed(field="selected_sources"){state.dirtyFields.add(field);state.dirty=true;$("confirm-review").checked=false;updateControls();}
function selectionView(){
  const list=$("selected-list");list.replaceChildren();
  for(const [id,p] of state.selected){
    const row=node("div",undefined,"selected-item");row.append(node("span",p.source_path+" · lines "+p.source_lines.join("–")));
    const b=node("button","Remove","text-button");b.type="button";b.disabled=state.busy;b.setAttribute("aria-label","Remove passage "+id);b.addEventListener("click",()=>toggleSelection(p,false));row.append(b);list.append(row);
  }
  for(const c of document.querySelectorAll("[data-passage]"))c.checked=state.selected.has(c.dataset.passage);
  updateControls();
}
function toggleSelection(p,checked) {
  if(checked&&state.selected.size>=10&&!state.selected.has(p.passage_id)){notice("Select at most 10 passages for one draft.",true);selectionView();return;}
  checked?state.selected.set(p.passage_id,p):state.selected.delete(p.passage_id);changed();selectionView();
}
function showResults(value){
  const list=$("results");list.replaceChildren();$("result-count").textContent=value.results.length+" ranked result"+(value.results.length===1?"":"s");
  if(!value.results.length){list.append(node("div","No matching passages. Try different wording; an empty result does not establish a factual answer.","empty-state"));return;}
  for(const hit of value.results) {
    const article=node("article",undefined,"result");const heading=node("h4",undefined,"result-title");heading.append(node("span","#"+hit.rank,"rank"),document.createTextNode(hit.section_titles.join(" › ")||"Documentation"));article.append(heading);
    article.append(node("p","BM25 "+hit.score.toFixed(4)+" · ranking score only","result-meta"));
    article.append(node("span",hit.chunk_id,"source-id"));
    for(const p of hit.passages) {
      const block=node("section",undefined,"passage");const label=node("label",undefined,"check-label");const box=node("input");box.type="checkbox";box.dataset.passage=p.passage_id;box.checked=state.selected.has(p.passage_id);box.setAttribute("aria-label","Select "+p.source_path+" lines "+p.source_lines.join(" to ")+" passage "+p.passage_id);box.addEventListener("change",()=>toggleSelection(p,box.checked));
      label.append(box,node("span","Select quoted documentation · Python "+p.product_version));block.append(label);
      block.append(safeLink(p.source_url,p.source_path+" · lines "+p.source_lines.join("–")+" ↗"));
      block.append(node("pre",p.text));block.append(node("span",p.passage_id,"source-id"));article.append(block);
    }list.append(article);
  }
}
function environment(){
  const result={};for(const line of $("environment").value.split("\n")){if(!line.trim())continue;const colon=line.indexOf(":");if(colon<1)throw new Error("Use name: value on each environment line.");const key=line.slice(0,colon).trim();if(Object.hasOwn(result,key))throw new Error("Environment detail names must be unique.");Object.defineProperty(result,key,{value:line.slice(colon+1).trim(),enumerable:true,writable:true,configurable:true});}return result;
}
function draftBody(){return {title:$("title").value,issue:$("issue").value,environment:environment(),human_notes:$("human-notes").value,
  missing_information:$("missing").value.split("\n").map(x=>x.trim()).filter(Boolean),
  selected_sources:[...state.selected.values()].map(p=>({source_id:p.source_id,passage_id:p.passage_id}))};}
function showTicket(t){
  state.ticket=t;state.dirty=false;state.dirtyFields.clear();state.selected=new Map(t.documentation.map(p=>[p.passage_id,p]));
  $("title").value=t.content.title;$("issue").value=t.content.issue;$("environment").value=Object.entries(t.content.environment).map(([k,v])=>k+": "+v).join("\n");
  $("human-notes").value=t.content.human_notes;$("missing").value=t.content.missing_information.join("\n");$("ticket-id").value=t.ticket_id;
  $("saved-text").textContent=t.rendered_text;$("confirm-review").checked=false;$("reload-ticket").hidden=true;
  const history=$("history");history.replaceChildren();
  for(const rev of t.history){const p=node("p");p.append(node("strong","Revision "+rev.revision+" · "+rev.created_at),document.createTextNode("Content SHA-256 "+rev.content_sha256));history.append(p);}
  for(const event of t.review_events){const p=node("p");p.append(node("strong","Review of revision "+event.revision+(event.current_revision?" · current":" · superseded")),document.createTextNode(event.reviewer_label+" · "+event.recorded_at+" · "+(event.note||"(no note)")+". Identity is not authenticated."));history.append(p);}
  selectionView();updateControls();
}
async function metadata(){
  $("connection").textContent="Checking local service…";$("retry").hidden=true;
  try{
    const [m,r]=await Promise.all([api("/metadata"),fetch("/ready").then(r=>r.json())]);
    state.metadata=m;state.ready=r.ready;
    $("app-version").textContent="Application "+m.application_version;
    $("connection").textContent=r.ready?"● Local service ready":"○ Required artifacts unavailable";
    const gen=m.experimental_generation;$("generation-state").textContent=gen.state+" · "+(gen.reason||"Explicitly enabled native experimental generator.");
    $("generate-button").hidden=!gen.enabled;$("generate-button").disabled=!gen.available;
    $("search-button").disabled=!m.capabilities.search;
    if(!r.ready){notice("The service is running, but required corpus or storage artifacts are unavailable. Search may be unavailable; existing user-only drafts may still be accessible.",true);$("retry").hidden=false;}
    updateControls();
  }catch(e){$("connection").textContent="○ Local service unavailable";$("generation-state").textContent="Availability could not be checked.";$("generate-button").hidden=true;$("retry").hidden=false;errorMessage(e);}
}
$("search-form").addEventListener("submit",async e=>{
  e.preventDefault();const button=$("search-button");button.disabled=true;button.textContent="Searching…";$("results").setAttribute("aria-busy","true");notice("Searching the pinned corpus…");
  try{showResults(await api("/search","POST",{question:$("question").value,top_k:Number($("top-k").value)}));notice("Search complete. Read the passages before selecting them.");}catch(error){$("results").replaceChildren(node("p","Search unavailable. No results were substituted.","empty-state"));errorMessage(error);}
  finally{button.disabled=state.metadata?!state.metadata.capabilities.search:false;button.textContent="Search documents ↗";$("results").removeAttribute("aria-busy");}
});
$("draft-form").addEventListener("input",event=>changed(({"human-notes":"human_notes",missing:"missing_information"})[event.target.id]||event.target.id));
$("draft-form").addEventListener("submit",async e=>{
  e.preventDefault();if(state.busy)return;state.busy=true;updateControls();notice("Saving local draft…");
  try{const body=state.ticket?Object.fromEntries([...state.dirtyFields].map(field=>[field,field==="environment"?environment():field==="selected_sources"?[...state.selected.values()].map(p=>({source_id:p.source_id,passage_id:p.passage_id})):field==="missing_information"?$("missing").value.split("\n").map(x=>x.trim()).filter(Boolean):$(field==="human_notes"?"human-notes":field).value])):draftBody();const t=state.ticket?await api("/tickets/"+state.ticket.ticket_id,"PATCH",{expected_revision:state.ticket.revision,...body}):await api("/tickets/draft","POST",body);showTicket(t);notice("Saved revision "+t.revision+". Review applies only after your explicit confirmation.");}catch(error){errorMessage(error);}finally{state.busy=false;selectionView();updateControls();}
});
$("confirm-review").addEventListener("change",updateControls);
$("review-button").addEventListener("click",async()=>{
  if(state.busy||state.dirty||!state.ticket||!$("confirm-review").checked)return;
  state.busy=true;updateControls();notice("Recording review of the saved revision…");
  try{const t=await api("/tickets/"+state.ticket.ticket_id+"/review","POST",{expected_revision:state.ticket.revision,confirm_review:true,reviewer_label:$("reviewer").value,note:$("review-note").value});showTicket(t);notice("Review recorded for revision "+t.revision+". This records your action, not a guarantee of correctness.");}catch(error){errorMessage(error);}finally{state.busy=false;selectionView();updateControls();}
});
$("copy-button").addEventListener("click",async()=>{
  if(!state.ticket||state.dirty)return;
  const t=state.ticket;const text="LOCAL DRAFT "+t.ticket_id+"\nRevision: "+t.revision+"\nReview state: "+t.review_state+" (local user action; not verified truth)\n\n"+t.rendered_text;
  try{await navigator.clipboard.writeText(text);notice("Copied saved draft with revision and review state.");}catch{notice("Clipboard access is unavailable. The saved text is selectable; include the displayed revision and review state when copying manually.",true);$("saved-details").open=true;}
});
async function loadTicket(id){if(state.busy)return;state.busy=true;updateControls();try{showTicket(await api("/tickets/"+id));notice("Opened saved current revision.");}catch(error){errorMessage(error);}finally{state.busy=false;selectionView();updateControls();}}
$("load-form").addEventListener("submit",e=>{e.preventDefault();loadTicket($("ticket-id").value);});
$("reload-ticket").addEventListener("click",()=>{if(state.ticket)loadTicket(state.ticket.ticket_id);});
$("clear-selection").addEventListener("click",()=>{state.selected.clear();changed();selectionView();});
$("new-draft").addEventListener("click",()=>{
  state.ticket=null;state.dirty=false;state.dirtyFields.clear();state.selected.clear();$("draft-form").reset();$("ticket-id").value="";$("saved-text").textContent="Save a draft to see its exact text.";$("history").replaceChildren(node("p","No saved revisions yet.","muted"));$("confirm-review").checked=false;$("reload-ticket").hidden=true;$("ticket-state").textContent="Drafts stay in this application's local SQLite storage.";selectionView();notice("New unsaved draft. Existing saved drafts remain in local storage.");$("issue").focus();
});
$("generate-button").addEventListener("click",async()=>{
  if(!$("question").value.trim()){notice("Enter a question in the documentation search field first.",true);$("question").focus();return;}
  const b=$("generate-button");b.disabled=true;b.textContent="Generating unverified output…";$("model-output").hidden=false;$("model-output").textContent="Waiting for experimental output. Search and draft tools remain available.";
  try{const v=await api("/experimental/answer","POST",{question:$("question").value});$("model-output").textContent="UNVERIFIED EXPERIMENTAL OUTPUT\nModel status: "+JSON.stringify(v.model_status)+"\nApplication outcome: "+v.application_validation_outcome+"\n\n"+(v.raw_output??"(no raw output)")+"\n\nAcceptance is not factual correctness. No content was inserted into a ticket.";notice("Experimental output is unverified and separate from your draft.");}
  catch(error){$("model-output").textContent="Experimental request failed. No answer or abstention was approved.";errorMessage(error);}
  finally{b.textContent="Generate unverified answer for search question";await metadata();}
});
for(const name of ["workspace","limitations"])$(name+"-tab").addEventListener("click",()=>{
  for(const view of ["workspace","limitations"]){const active=name===view;$(view+"-view").hidden=!active;$(view+"-tab").classList.toggle("active",active);if(active)$(view+"-tab").setAttribute("aria-current","page");else $(view+"-tab").removeAttribute("aria-current");}
});
$("retry").addEventListener("click",metadata);
metadata();
